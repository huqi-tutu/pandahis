"use strict";
/**
 * 史略详情朗读：优先微信同声传译插件 TTS + InnerAudioContext 原生播放；
 * 插件不可用时回退服务端合成 MP3。
 *
 * 机制：按字分片 → 字符轴进度 → 按需合成 + 预取缓存 → 跨片 seek。
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.setPlaybackRate = exports.seekNarrationPct = exports.seekNarration = exports.toggleNarrationPlayback = exports.startNarration = exports.resumeNarration = exports.pauseNarration = exports.stopNarration = exports.getNarrationState = exports.buildBoxNarrationScript = exports.chunkTextForTts = void 0;
const api_1 = require("./api");
const CHUNK_MAX = 180;
const TEXT_MAX = 6000;
/** 估算语速：字/秒，仅用于总时长展示与 ±Ns 换算 */
const CHARS_PER_SEC = 4.5;
/** TTS 文本预取超前片数 */
const PREFETCH_AHEAD = 3;
let chunks = [];
/** 各片起始字符偏移（相对全文） */
let chunkStarts = [];
let totalChars = 0;
let chunkIndex = 0;
let aborted = false;
/** 会话世代：stop/start 递增，防止旧合成写入新缓存 */
let sessionId = 0;
let state = 'idle';
let onStateChange = null;
let onProgressChange = null;
let wechatSIChecked = false;
let wechatSIAvailable = false;
const chunkCache = new Map();
/** 进行中的合成 Promise，避免同片重复请求 */
const inflightSynth = new Map();
let prefetchTail = Promise.resolve();
let seekGeneration = 0;
/** 跨片 seek 进行中时，用目标字位置作为进度/±15s 基准，避免旧片 timeUpdate 干扰 */
let pendingCharPos = null;
/** 同一 src 只触发一次 play，避免 onCanplay 与兜底双触发 */
let playToken = 0;
let activePlaySrc = '';
/** 当前正在播的分片下标 */
let playingChunkIndex = -1;
/** 已真正 start 的 playToken；仅该 token 的 onEnded 可推进分片 */
let armedPlayToken = 0;
let playbackRate = 1;
/** 双缓冲：当前播 + 待机预加载，消除换 src 空隙 */
let audioPool = [];
let activeSlot = 0;
let standbyChunkIndex = -1;
let standbySrc = '';
let standbyReady = false;
let standbyLoadToken = 0;
/** 卡死检测：playing 但 currentTime 长时间不动则重建当前片 */
let lastHeardCurrentTime = -1;
let lastHeardAt = 0;
let hasHeardProgress = false;
let stallWatchTimer = null;
let seamlessSwitchCount = 0;
let stallRecovering = false;
function formatMmSs(sec) {
    if (!Number.isFinite(sec) || sec < 0)
        return '0:00';
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m}:${s < 10 ? '0' : ''}${s}`;
}
function rebuildCharAxis(parts) {
    chunks = parts;
    chunkStarts = [];
    let acc = 0;
    for (const p of parts) {
        chunkStarts.push(acc);
        acc += p.length;
    }
    totalChars = acc;
}
function estimatedTotalDurationSec() {
    if (totalChars <= 0)
        return 0;
    return totalChars / CHARS_PER_SEC;
}
function charOffsetFromProgress(currentSec, durationSec) {
    var _a;
    if (!chunks.length || totalChars <= 0)
        return 0;
    const idx = Math.max(0, Math.min(chunkIndex, chunks.length - 1));
    const start = chunkStarts[idx] || 0;
    const len = ((_a = chunks[idx]) === null || _a === void 0 ? void 0 : _a.length) || 0;
    if (len <= 0)
        return start;
    const ratio = durationSec > 0 ? Math.min(1, Math.max(0, currentSec / durationSec)) : 0;
    return start + ratio * len;
}
function emitProgressFromChar(charPos) {
    if (totalChars <= 0) {
        onProgressChange === null || onProgressChange === void 0 ? void 0 : onProgressChange({ progress: 0, current: '0:00', duration: '0:00' });
        return;
    }
    const clamped = Math.max(0, Math.min(totalChars, charPos));
    const progress = Math.min(100, Math.max(0, Math.round((clamped / totalChars) * 100)));
    const estTotal = estimatedTotalDurationSec();
    const estCurrent = (clamped / totalChars) * estTotal;
    onProgressChange === null || onProgressChange === void 0 ? void 0 : onProgressChange({
        progress,
        current: formatMmSs(estCurrent),
        duration: formatMmSs(estTotal),
    });
}
function emitProgress(currentSec = 0, durationSec = 0) {
    if (pendingCharPos != null) {
        emitProgressFromChar(pendingCharPos);
        return;
    }
    emitProgressFromChar(charOffsetFromProgress(currentSec, durationSec));
}
function mapCharToChunk(charPos) {
    if (!chunks.length)
        return { index: 0, ratio: 0 };
    const clamped = Math.max(0, Math.min(totalChars, charPos));
    let index = chunks.length - 1;
    for (let i = 0; i < chunks.length; i++) {
        const start = chunkStarts[i];
        const end = start + chunks[i].length;
        if (clamped < end || i === chunks.length - 1) {
            index = i;
            const len = chunks[i].length || 1;
            const ratio = Math.min(1, Math.max(0, (clamped - start) / len));
            // 落在片末边界时，若不是最后一片，交给下一片开头，避免片尾 seek 立刻 onEnded
            if (ratio >= 1 && i < chunks.length - 1 && clamped >= end) {
                return { index: i + 1, ratio: 0 };
            }
            return { index, ratio };
        }
    }
    return { index, ratio: 0 };
}
function setState(next) {
    state = next;
    onStateChange === null || onStateChange === void 0 ? void 0 : onStateChange(next);
}
function friendlyTtsError(raw) {
    const msg = String(raw || '');
    if (/REQUEST_FAIL|timeout|connect/i.test(msg)) {
        return '无法连接朗读服务，请检查网络或稍后重试';
    }
    if (/插件|WechatSI|requirePlugin/i.test(msg)) {
        return '请在微信公众平台为小程序添加「微信同声传译」插件后重试';
    }
    if (/INTERNAL_ERROR|语音合成|-20003/i.test(msg)) {
        return '语音合成失败，请缩短内容或稍后重试';
    }
    return msg.length > 32 ? `${msg.slice(0, 30)}…` : msg || '朗读失败';
}
function checkWechatSI() {
    if (wechatSIChecked)
        return wechatSIAvailable;
    wechatSIChecked = true;
    try {
        const plugin = requirePlugin('WechatSI');
        wechatSIAvailable = Boolean(plugin && typeof plugin.textToSpeech === 'function');
    }
    catch {
        wechatSIAvailable = false;
    }
    return wechatSIAvailable;
}
function textToSpeechNative(content) {
    return new Promise((resolve, reject) => {
        let plugin;
        try {
            plugin = requirePlugin('WechatSI');
        }
        catch (e) {
            reject(new Error('未加载微信同声传译插件'));
            return;
        }
        plugin.textToSpeech({
            lang: 'zh_CN',
            tts: true,
            content,
            success: (res) => {
                var _a;
                const file = res === null || res === void 0 ? void 0 : res.filename;
                if (file)
                    resolve(file);
                else
                    reject(new Error(`语音合成失败(${(_a = res === null || res === void 0 ? void 0 : res.retcode) !== null && _a !== void 0 ? _a : 'unknown'})`));
            },
            fail: (res) => {
                var _a;
                reject(new Error((res === null || res === void 0 ? void 0 : res.msg) || `语音合成失败(${(_a = res === null || res === void 0 ? void 0 : res.retcode) !== null && _a !== void 0 ? _a : 'fail'})`));
            },
        });
    });
}
function newLocalMp3Path() {
    return `${wx.env.USER_DATA_PATH}/tts_${Date.now()}_${Math.random().toString(36).slice(2, 8)}.mp3`;
}
function writeMp3TempFile(base64) {
    const fs = wx.getFileSystemManager();
    const path = newLocalMp3Path();
    return new Promise((resolve, reject) => {
        fs.writeFile({
            filePath: path,
            data: base64,
            encoding: 'base64',
            success: () => resolve(path),
            fail: (err) => reject(new Error((err === null || err === void 0 ? void 0 : err.errMsg) || '写入语音文件失败')),
        });
    });
}
/**
 * 微信同声传译返回的是远程临时 URL（文档约 3 小时过期）。
 * 直接播远程链在长会话/双缓冲切换后常出现「时间在走但无声」；合成后立刻落本地。
 */
function saveTempToUserData(tempFilePath, dest) {
    return new Promise((resolve) => {
        try {
            wx.getFileSystemManager().saveFile({
                tempFilePath,
                filePath: dest,
                success: () => resolve(dest),
                fail: () => resolve(tempFilePath),
            });
        }
        catch {
            resolve(tempFilePath);
        }
    });
}
function downloadRemoteAudioToLocal(url) {
    const dest = newLocalMp3Path();
    return new Promise((resolve, reject) => {
        let settled = false;
        const done = (err, path) => {
            if (settled)
                return;
            settled = true;
            clearTimeout(timer);
            if (err || !path)
                reject(err || new Error('下载语音失败'));
            else
                resolve(path);
        };
        const timer = setTimeout(() => done(new Error('下载语音超时')), 8000);
        const finish = async (res) => {
            if (res.statusCode !== 200) {
                done(new Error(`下载语音失败(${res.statusCode})`));
                return;
            }
            const local = res.filePath || res.tempFilePath;
            if (!local) {
                done(new Error('下载语音失败：无本地文件'));
                return;
            }
            try {
                const info = wx.getFileSystemManager().statSync(local);
                const size = typeof info === 'object' && info && 'size' in info ? Number(info.size) : 0;
                if (size > 0 && size < 128) {
                    done(new Error('下载语音文件过小'));
                    return;
                }
            }
            catch {
                /* stat 失败不阻断，继续用该路径 */
            }
            if (res.filePath) {
                done(undefined, res.filePath);
                return;
            }
            done(undefined, await saveTempToUserData(res.tempFilePath, dest));
        };
        // 先不带 filePath：兼容性更好；成功后再落到 USER_DATA
        wx.downloadFile({
            url,
            success: (res) => void finish(res),
            fail: (e) => done(new Error((e === null || e === void 0 ? void 0 : e.errMsg) || '下载语音失败')),
        });
    });
}
async function materializePlayablePath(urlOrPath) {
    const src = String(urlOrPath || '');
    if (!src)
        throw new Error('语音地址为空');
    // 远程 URL：尽量落本地；失败时回退直链（downloadFile 域名未配时仍可 InnerAudio 播放）
    if (/^https?:\/\//i.test(src)) {
        try {
            const path = await downloadRemoteAudioToLocal(src);
            return { path, isLocalTemp: true };
        }
        catch (e) {
            console.warn('[narration] 语音落本地失败，回退远程直链', e);
            return { path: src, isLocalTemp: false };
        }
    }
    return { path: src, isLocalTemp: false };
}
async function textToSpeechBackend(content) {
    var _a;
    const res = await (0, api_1.request)('/narration/synthesize', {
        method: 'POST',
        data: { text: content },
    });
    const b64 = (_a = res.data) === null || _a === void 0 ? void 0 : _a.audioBase64;
    if (!b64)
        throw new Error('语音合成结果为空');
    const path = await writeMp3TempFile(b64);
    return { path, isLocalTemp: true };
}
async function synthesizeChunk(content) {
    if (checkWechatSI()) {
        try {
            const remote = await textToSpeechNative(content);
            return await materializePlayablePath(remote);
        }
        catch {
            /* 插件失败时回退服务端 */
        }
    }
    return textToSpeechBackend(content);
}
function unlinkLocalTemp(path) {
    try {
        wx.getFileSystemManager().unlink({ filePath: path, fail: () => undefined });
    }
    catch {
        /* ignore */
    }
}
function clearChunkCache() {
    for (const entry of chunkCache.values()) {
        if (entry.isLocalTemp)
            unlinkLocalTemp(entry.path);
    }
    chunkCache.clear();
    inflightSynth.clear();
}
/** 确保第 index 片已合成并缓存 */
async function ensureChunk(index) {
    const sid = sessionId;
    if (aborted)
        throw new Error('aborted');
    if (index < 0 || index >= chunks.length)
        throw new Error('分片越界');
    const hit = chunkCache.get(index);
    if (hit)
        return hit;
    const pending = inflightSynth.get(index);
    if (pending)
        return pending;
    const content = chunks[index];
    const run = (async () => {
        let path = '';
        let isLocalTemp = false;
        try {
            const synthesized = await synthesizeChunk(content);
            path = synthesized.path;
            isLocalTemp = synthesized.isLocalTemp;
            // 会话已切换：丢弃结果并清理本地临时文件
            if (aborted || sid !== sessionId) {
                if (isLocalTemp && path)
                    unlinkLocalTemp(path);
                throw new Error('aborted');
            }
            const entry = { path, isLocalTemp };
            chunkCache.set(index, entry);
            return entry;
        }
        catch (e) {
            // 未成功入缓存的本地临时文件要删掉，避免 USER_DATA_PATH 堆积
            if (isLocalTemp && path) {
                const cached = chunkCache.get(index);
                if (!cached || cached.path !== path)
                    unlinkLocalTemp(path);
            }
            throw e;
        }
    })();
    inflightSynth.set(index, run);
    try {
        return await run;
    }
    finally {
        if (inflightSynth.get(index) === run)
            inflightSynth.delete(index);
    }
}
/** 串行预取后续片，避免打爆 TTS 配额 */
function schedulePrefetch(fromIndex) {
    const sid = sessionId;
    const start = fromIndex + 1;
    const end = Math.min(chunks.length - 1, fromIndex + PREFETCH_AHEAD);
    if (start > end)
        return;
    prefetchTail = prefetchTail
        .then(async () => {
        if (aborted || sid !== sessionId)
            return;
        for (let i = start; i <= end; i++) {
            if (aborted || sid !== sessionId)
                return;
            if (chunkCache.has(i) || inflightSynth.has(i))
                continue;
            try {
                await ensureChunk(i);
            }
            catch {
                /* 预取失败不打断当前播放 */
                return;
            }
        }
    })
        .catch(() => undefined);
}
function getActiveAudio() {
    return audioPool[activeSlot] || null;
}
function clearStandby() {
    standbyLoadToken += 1;
    standbyChunkIndex = -1;
    standbySrc = '';
    standbyReady = false;
    const standby = audioPool[1 - activeSlot];
    if (!standby)
        return;
    try {
        standby.stop();
    }
    catch {
        /* ignore */
    }
}
/** 停掉当前音频，使旧 onEnded 失效（配合 seekGeneration / armedPlayToken） */
function haltCurrentAudio() {
    playToken += 1;
    armedPlayToken = 0;
    activePlaySrc = '';
    playingChunkIndex = -1;
    clearStandby();
    const audio = getActiveAudio();
    if (!audio)
        return;
    try {
        audio.stop();
    }
    catch {
        /* ignore */
    }
}
function markStandbyReady(loadToken, nextIndex, path, ctx) {
    if (aborted || loadToken !== standbyLoadToken)
        return;
    if (standbyChunkIndex !== nextIndex || standbySrc !== path)
        return;
    // 必须能读到时长，避免「假就绪」后 play 无声但时间轴假走
    if (!(ctx.duration > 0))
        return;
    standbyReady = true;
}
/** 把下一片预载进待机槽，ended 时直接 play，避免换 src 卡顿 */
async function prepareStandby(nextIndex) {
    var _a;
    const sid = sessionId;
    const loadToken = ++standbyLoadToken;
    if (nextIndex < 0 || nextIndex >= chunks.length) {
        clearStandby();
        return;
    }
    try {
        const entry = await ensureChunk(nextIndex);
        if (aborted || sid !== sessionId || loadToken !== standbyLoadToken)
            return;
        const standby = audioPool[1 - activeSlot];
        if (!standby)
            return;
        standbyReady = false;
        standbyChunkIndex = nextIndex;
        standbySrc = entry.path;
        try {
            (_a = standby.offCanplay) === null || _a === void 0 ? void 0 : _a.call(standby);
        }
        catch {
            /* ignore */
        }
        standby.onCanplay(() => {
            markStandbyReady(loadToken, nextIndex, entry.path, standby);
        });
        try {
            standby.volume = 1;
            standby.playbackRate = playbackRate;
        }
        catch {
            /* ignore */
        }
        standby.src = entry.path;
        // 部分机型无 onCanplay：轮询 duration，就绪才放行（不再盲目 280ms 置 ready）
        let tries = 0;
        const poll = () => {
            if (aborted || loadToken !== standbyLoadToken)
                return;
            if (standbyReady)
                return;
            markStandbyReady(loadToken, nextIndex, entry.path, standby);
            if (standbyReady || tries >= 40)
                return;
            tries += 1;
            setTimeout(poll, 50);
        };
        setTimeout(poll, 80);
    }
    catch {
        /* 预载失败不打断当前播放 */
    }
}
function stopStallWatch() {
    if (stallWatchTimer != null) {
        clearInterval(stallWatchTimer);
        stallWatchTimer = null;
    }
}
function notePlaybackHeartbeat(currentTime) {
    if (!Number.isFinite(currentTime))
        return;
    if (Math.abs(currentTime - lastHeardCurrentTime) > 0.01) {
        lastHeardCurrentTime = currentTime;
        lastHeardAt = Date.now();
        if (currentTime > 0.05)
            hasHeardProgress = true;
    }
}
function startStallWatch() {
    stopStallWatch();
    lastHeardAt = Date.now();
    lastHeardCurrentTime = -1;
    hasHeardProgress = false;
    stallRecovering = false;
    stallWatchTimer = setInterval(() => {
        if (aborted || state !== 'playing' || stallRecovering)
            return;
        const audio = getActiveAudio();
        if (!audio)
            return;
        // 尚未真正推进过进度时不误判（首包缓冲）
        if (!hasHeardProgress)
            return;
        // 超过 2.8s currentTime 不动：缓冲/焦点异常，重建当前片
        if (Date.now() - lastHeardAt < 2800)
            return;
        const idx = chunkIndex;
        const entry = chunkCache.get(idx);
        if (!entry)
            return;
        const ratio = audio.duration > 0 ? Math.min(0.98, Math.max(0, (audio.currentTime || 0) / audio.duration)) : 0;
        console.warn('[narration] stall detected, reload chunk', idx);
        stallRecovering = true;
        clearStandby();
        playToken += 1;
        armedPlayToken = 0;
        try {
            audio.stop();
        }
        catch {
            /* ignore */
        }
        playFile(entry.path, ratio);
    }, 1000);
}
/** 按句号/换行切分，单段不超过 CHUNK_MAX 字 */
function chunkTextForTts(text, maxLen = CHUNK_MAX) {
    const normalized = String(text || '')
        .replace(/\r\n/g, '\n')
        .replace(/[#*_`>\[\]()]/g, '')
        .replace(/\s+/g, ' ')
        .trim();
    if (!normalized)
        return [];
    const parts = [];
    let seg = '';
    for (const ch of normalized) {
        seg += ch;
        if ('。！？；\n'.includes(ch)) {
            const t = seg.trim();
            if (t)
                parts.push(t);
            seg = '';
        }
    }
    const tail = seg.trim();
    if (tail)
        parts.push(tail);
    const out = [];
    let buf = '';
    const flush = () => {
        if (buf.trim())
            out.push(buf.trim());
        buf = '';
    };
    for (const part of parts) {
        if (part.length > maxLen) {
            flush();
            for (let i = 0; i < part.length; i += maxLen) {
                out.push(part.slice(i, i + maxLen));
            }
            continue;
        }
        if (buf.length + part.length <= maxLen) {
            buf += part;
        }
        else {
            flush();
            buf = part;
        }
    }
    flush();
    return out;
}
exports.chunkTextForTts = chunkTextForTts;
function buildBoxNarrationScript(opts) {
    const parts = [];
    const title = String(opts.title || '').trim();
    if (title)
        parts.push(title);
    const meta = String(opts.meta || '')
        .replace(/\s*·\s*/g, '，')
        .replace(/\s*—\s*/g, '至')
        .trim();
    if (meta)
        parts.push(meta);
    const paras = (opts.paragraphs || []).map((p) => String(p || '').trim()).filter(Boolean);
    if (paras.length)
        parts.push(...paras);
    else {
        const blurb = String(opts.blurb || '').trim();
        if (blurb)
            parts.push(blurb);
    }
    let text = parts.join('。');
    if (text && !/[。！？]$/.test(text))
        text += '。';
    if (text.length > TEXT_MAX)
        text = `${text.slice(0, TEXT_MAX)}……`;
    return text;
}
exports.buildBoxNarrationScript = buildBoxNarrationScript;
function destroyAudio() {
    stopStallWatch();
    clearStandby();
    for (const ctx of audioPool) {
        try {
            ctx.stop();
            ctx.destroy();
        }
        catch {
            /* ignore */
        }
    }
    audioPool = [];
    activeSlot = 0;
    activePlaySrc = '';
    playingChunkIndex = -1;
    armedPlayToken = 0;
    seamlessSwitchCount = 0;
}
function bindSlotListeners(ctx, slot) {
    ctx.onEnded(() => {
        var _a;
        if (aborted || slot !== activeSlot)
            return;
        if (!armedPlayToken || armedPlayToken !== playToken)
            return;
        if (pendingCharPos != null)
            return;
        if (playingChunkIndex < 0 || playingChunkIndex !== chunkIndex)
            return;
        const endedSeekGen = seekGeneration;
        const endedSession = sessionId;
        const endedIndex = playingChunkIndex;
        const nextIndex = endedIndex + 1;
        armedPlayToken = 0;
        playingChunkIndex = -1;
        // 待机槽已预载好下一片：先 play 再停旧槽，避免部分机型抢焦点后静音
        if (nextIndex < chunks.length &&
            standbyReady &&
            standbyChunkIndex === nextIndex &&
            standbySrc &&
            (((_a = audioPool[1 - activeSlot]) === null || _a === void 0 ? void 0 : _a.duration) || 0) > 0) {
            const prevSlot = activeSlot;
            const nextCtx = audioPool[1 - activeSlot];
            const token = ++playToken;
            try {
                nextCtx.volume = 1;
                nextCtx.playbackRate = playbackRate;
            }
            catch {
                /* ignore */
            }
            try {
                // 从片头开播，防止复用上下文残留进度
                try {
                    nextCtx.seek(0);
                }
                catch {
                    /* ignore */
                }
                nextCtx.play();
                activeSlot = 1 - activeSlot;
                chunkIndex = nextIndex;
                playingChunkIndex = nextIndex;
                activePlaySrc = standbySrc;
                standbyReady = false;
                standbyChunkIndex = -1;
                standbySrc = '';
                armedPlayToken = token;
                setState('playing');
                pendingCharPos = null;
                notePlaybackHeartbeat(0);
                startStallWatch();
                seamlessSwitchCount += 1;
                // 延迟停旧槽，给新槽抢到音频焦点
                setTimeout(() => {
                    var _a;
                    if (aborted)
                        return;
                    try {
                        (_a = audioPool[prevSlot]) === null || _a === void 0 ? void 0 : _a.stop();
                    }
                    catch {
                        /* ignore */
                    }
                }, 60);
                schedulePrefetch(chunkIndex);
                void prepareStandby(chunkIndex + 1);
                emitProgress(nextCtx.currentTime || 0, nextCtx.duration || 0);
            }
            catch (e) {
                console.error('[narration] standby play()', e);
                chunkIndex = nextIndex;
                void playNextChunk().catch((err) => {
                    if (aborted || endedSeekGen !== seekGeneration || endedSession !== sessionId)
                        return;
                    const raw = err instanceof Error ? err.message : String(err);
                    stopNarration();
                    wx.showToast({ title: friendlyTtsError(raw).slice(0, 28), icon: 'none', duration: 2800 });
                });
            }
            return;
        }
        chunkIndex = nextIndex;
        void playNextChunk().catch((e) => {
            if (aborted || endedSeekGen !== seekGeneration || endedSession !== sessionId)
                return;
            const raw = e instanceof Error ? e.message : String(e);
            stopNarration();
            wx.showToast({ title: friendlyTtsError(raw).slice(0, 28), icon: 'none', duration: 2800 });
        });
    });
    ctx.onTimeUpdate(() => {
        if (aborted || slot !== activeSlot)
            return;
        if (pendingCharPos != null)
            return;
        const cur = ctx.currentTime || 0;
        const dur = ctx.duration || 0;
        notePlaybackHeartbeat(cur);
        if (dur > 0) {
            const entry = chunkCache.get(chunkIndex);
            if (entry && !entry.durationSec) {
                chunkCache.set(chunkIndex, { ...entry, durationSec: dur });
            }
        }
        emitProgress(cur, dur);
    });
    ctx.onError((err) => {
        if (aborted || slot !== activeSlot)
            return;
        console.error('[narration] play error', err);
        // 单片播放失败：尝试跳过/重载，避免整页直接被 idle 关掉
        const idx = chunkIndex;
        const entry = chunkCache.get(idx);
        clearStandby();
        if (entry && activePlaySrc !== entry.path) {
            playFile(entry.path, 0);
            return;
        }
        if (idx + 1 < chunks.length) {
            chunkIndex = idx + 1;
            void playNextChunk(0).catch(() => {
                stopNarration();
                wx.showToast({ title: '播放失败', icon: 'none' });
            });
            return;
        }
        stopNarration();
        wx.showToast({ title: '播放失败', icon: 'none' });
    });
}
function ensureAudioPool() {
    if (audioPool.length >= 2)
        return;
    while (audioPool.length < 2) {
        const ctx = wx.createInnerAudioContext();
        ctx.obeyMuteSwitch = false;
        ctx.autoplay = false;
        try {
            ctx.playbackRate = playbackRate;
        }
        catch {
            /* ignore */
        }
        const slot = audioPool.length;
        bindSlotListeners(ctx, slot);
        audioPool.push(ctx);
    }
}
function playFile(filename, seekRatio = 0) {
    var _a;
    ensureAudioPool();
    const audio = getActiveAudio();
    if (!audio || aborted)
        return;
    // 主动播放会占用当前槽；清掉可能过期的待机，稍后重新预载
    clearStandby();
    const token = ++playToken;
    armedPlayToken = 0;
    activePlaySrc = filename;
    playingChunkIndex = chunkIndex;
    let started = false;
    const armEnded = () => {
        if (token === playToken)
            armedPlayToken = token;
    };
    const afterPlayStarted = () => {
        pendingCharPos = null;
        notePlaybackHeartbeat(audio.currentTime || 0);
        startStallWatch();
        schedulePrefetch(chunkIndex);
        void prepareStandby(chunkIndex + 1);
        emitProgress(audio.currentTime || 0, audio.duration || 0);
    };
    const playNow = () => {
        if (aborted || token !== playToken || activePlaySrc !== filename)
            return;
        if (started)
            return;
        started = true;
        const applySeekAndPlay = () => {
            if (aborted || token !== playToken)
                return;
            if (seekRatio > 0) {
                const dur = audio.duration || 0;
                if (dur > 0) {
                    try {
                        audio.seek(Math.min(dur * 0.999, Math.max(0, dur * seekRatio)));
                    }
                    catch {
                        /* ignore */
                    }
                }
            }
            setState('playing');
            try {
                audio.volume = 1;
                audio.playbackRate = playbackRate;
            }
            catch {
                /* ignore */
            }
            try {
                audio.play();
                armEnded();
            }
            catch (e) {
                console.error('[narration] play()', e);
                stopNarration();
                wx.showToast({ title: '播放失败', icon: 'none' });
                return;
            }
            afterPlayStarted();
        };
        if (seekRatio > 0 && !(audio.duration > 0)) {
            setState('playing');
            try {
                audio.volume = 1;
                audio.play();
                armEnded();
            }
            catch (e) {
                console.error('[narration] play()', e);
                stopNarration();
                wx.showToast({ title: '播放失败', icon: 'none' });
                return;
            }
            notePlaybackHeartbeat(0);
            startStallWatch();
            schedulePrefetch(chunkIndex);
            void prepareStandby(chunkIndex + 1);
            let tries = 0;
            const waitDur = () => {
                if (aborted || token !== playToken)
                    return;
                const dur = audio.duration || 0;
                if (dur > 0 || tries >= 40) {
                    if (dur > 0) {
                        try {
                            audio.seek(Math.min(dur * 0.999, Math.max(0, dur * seekRatio)));
                        }
                        catch {
                            /* ignore */
                        }
                        pendingCharPos = null;
                        emitProgress(seekRatio * dur, dur);
                    }
                    else {
                        emitProgress(0, 0);
                    }
                    return;
                }
                tries += 1;
                setTimeout(waitDur, 50);
            };
            setTimeout(waitDur, 50);
            return;
        }
        applySeekAndPlay();
    };
    try {
        (_a = audio.offCanplay) === null || _a === void 0 ? void 0 : _a.call(audio);
    }
    catch {
        /* ignore */
    }
    audio.onCanplay(playNow);
    audio.src = filename;
    setTimeout(() => {
        if (!aborted && token === playToken && !started) {
            playNow();
        }
    }, 400);
}
async function playNextChunk(seekRatio = 0) {
    const sid = sessionId;
    const seekGen = seekGeneration;
    if (aborted)
        return;
    if (chunkIndex >= chunks.length) {
        stopNarration();
        return;
    }
    const cached = chunkCache.get(chunkIndex);
    // 已预取命中时不闪 loading，保证片间无感衔接
    if (!cached)
        setState('loading');
    try {
        const entry = cached || (await ensureChunk(chunkIndex));
        if (aborted || sid !== sessionId || seekGen !== seekGeneration)
            return;
        playFile(entry.path, seekRatio);
    }
    catch (e) {
        if (aborted || sid !== sessionId || seekGen !== seekGeneration)
            return;
        stopNarration();
        const raw = e instanceof Error ? e.message : String(e);
        throw new Error(friendlyTtsError(raw));
    }
}
async function jumpToChar(charPos) {
    var _a;
    if (!chunks.length || (state !== 'playing' && state !== 'paused' && state !== 'loading'))
        return;
    const gen = ++seekGeneration;
    const sid = sessionId;
    const targetChar = Math.max(0, Math.min(totalChars, charPos));
    const { index, ratio } = mapCharToChunk(targetChar);
    pendingCharPos = targetChar;
    emitProgressFromChar(targetChar);
    // 同片内且已有音频：直接 seek（最快路径）
    const active = getActiveAudio();
    if (index === chunkIndex && active && (state === 'playing' || state === 'paused') && activePlaySrc) {
        const dur = active.duration || ((_a = chunkCache.get(index)) === null || _a === void 0 ? void 0 : _a.durationSec) || 0;
        if (dur > 0) {
            try {
                active.seek(Math.min(dur * 0.999, Math.max(0, dur * ratio)));
                pendingCharPos = null;
                emitProgress(ratio * dur, dur);
            }
            catch {
                pendingCharPos = null;
            }
            return;
        }
    }
    // 跨片：先停旧音频，避免片尾 onEnded 改写 chunkIndex
    haltCurrentAudio();
    const cached = chunkCache.get(index);
    if (!cached)
        setState('loading');
    chunkIndex = index;
    try {
        const entry = cached || (await ensureChunk(index));
        if (aborted || gen !== seekGeneration || sid !== sessionId)
            return;
        playFile(entry.path, ratio);
    }
    catch (e) {
        if (aborted || gen !== seekGeneration || sid !== sessionId)
            return;
        pendingCharPos = null;
        const raw = e instanceof Error ? e.message : String(e);
        wx.showToast({ title: friendlyTtsError(raw).slice(0, 28), icon: 'none', duration: 2800 });
        const cur = chunkCache.get(chunkIndex);
        if (cur)
            playFile(cur.path, 0);
        else
            stopNarration();
    }
}
function getNarrationState() {
    return state;
}
exports.getNarrationState = getNarrationState;
function stopNarration(opts) {
    aborted = true;
    sessionId += 1;
    seekGeneration += 1;
    playToken += 1;
    pendingCharPos = null;
    chunks = [];
    chunkStarts = [];
    totalChars = 0;
    chunkIndex = 0;
    clearChunkCache();
    prefetchTail = Promise.resolve();
    destroyAudio();
    const stateCb = onStateChange;
    onStateChange = null;
    onProgressChange = null;
    state = 'idle';
    // 重启朗读时 silent，避免旧回调把浮层立刻关掉
    if (!(opts === null || opts === void 0 ? void 0 : opts.silent))
        stateCb === null || stateCb === void 0 ? void 0 : stateCb('idle');
}
exports.stopNarration = stopNarration;
function pauseNarration() {
    const audio = getActiveAudio();
    if (!audio || state !== 'playing')
        return;
    try {
        audio.pause();
    }
    catch {
        /* ignore */
    }
    stopStallWatch();
    setState('paused');
}
exports.pauseNarration = pauseNarration;
function resumeNarration() {
    const audio = getActiveAudio();
    if (!audio || state !== 'paused')
        return;
    try {
        audio.volume = 1;
        audio.play();
    }
    catch {
        /* ignore */
    }
    notePlaybackHeartbeat(audio.currentTime || 0);
    startStallWatch();
    setState('playing');
}
exports.resumeNarration = resumeNarration;
async function startNarration(text, stateCb, progressCb) {
    // 先摘掉旧回调再 stop，防止 idle 把刚打开的浮层关掉
    onStateChange = null;
    onProgressChange = null;
    stopNarration({ silent: true });
    // stop 已递增 sessionId；新会话在此复活
    aborted = false;
    onStateChange = stateCb;
    onProgressChange = progressCb || null;
    const parts = chunkTextForTts(text);
    if (!parts.length)
        throw new Error('暂无正文可朗读');
    rebuildCharAxis(parts);
    chunkIndex = 0;
    pendingCharPos = null;
    setState('loading');
    // 进浮层即按字数轴给出总时长/进度基线
    emitProgressFromChar(0);
    await playNextChunk(0);
}
exports.startNarration = startNarration;
function toggleNarrationPlayback() {
    if (state === 'playing') {
        pauseNarration();
    }
    else if (state === 'paused') {
        resumeNarration();
    }
    return state;
}
exports.toggleNarrationPlayback = toggleNarrationPlayback;
/**
 * 按估算时长偏移秒数跨片 seek（正数快进、负数快退）
 */
function seekNarration(offsetSec) {
    if (!chunks.length || (state !== 'playing' && state !== 'paused' && state !== 'loading'))
        return;
    const audio = getActiveAudio();
    const curSec = (audio === null || audio === void 0 ? void 0 : audio.currentTime) || 0;
    const curDur = (audio === null || audio === void 0 ? void 0 : audio.duration) || 0;
    const charPos = pendingCharPos != null ? pendingCharPos : charOffsetFromProgress(curSec, curDur);
    const deltaChars = offsetSec * CHARS_PER_SEC;
    const next = Math.max(0, Math.min(totalChars, charPos + deltaChars));
    void jumpToChar(next);
}
exports.seekNarration = seekNarration;
/**
 * 按全文字数轴百分比（0-100）跨片 seek
 */
function seekNarrationPct(pct) {
    if (!chunks.length || (state !== 'playing' && state !== 'paused' && state !== 'loading'))
        return;
    const p = Math.max(0, Math.min(100, pct));
    const targetChar = (p / 100) * totalChars;
    void jumpToChar(targetChar);
}
exports.seekNarrationPct = seekNarrationPct;
/** 设置播放速度（需基础库 2.11.0+） */
function setPlaybackRate(rate) {
    playbackRate = rate;
    for (const ctx of audioPool) {
        try {
            ctx.playbackRate = rate;
        }
        catch {
            // 低版本基础库不支持，静默忽略
        }
    }
}
exports.setPlaybackRate = setPlaybackRate;
