"use strict";
/**
 * 史略详情朗读：服务端 Edge TTS（可拼接连续 MP3）+ 本地双 InnerAudio 无缝续播。
 *
 * 目标：片间接近零静默（待机槽预载 + 片尾提前切源），避免「少换源但仍可感知卡顿」。
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.setPlaybackRate = exports.seekNarrationPct = exports.seekNarration = exports.toggleNarrationPlayback = exports.startNarration = exports.resumeNarration = exports.pauseNarration = exports.stopNarration = exports.getNarrationState = exports.buildBoxNarrationScript = exports.chunkTextForTts = void 0;
const api_1 = require("./api");
/**
 * 有微信同声传译时按官方 ≤50 字分片（插件主路径）；
 * 仅服务端时用 450，兼容 Edge 单次上限与旧 @Size(500)。
 */
const CHUNK_MAX_BACKEND = 450;
const WECHAT_SI_CHUNK_MAX = 50;
const TEXT_MAX = 6000;
const CHARS_PER_SEC = 4.5;
const PREFETCH_AHEAD = 2;
const MAX_CONSECUTIVE_SKIPS = 5;
const STALL_MS = 8000;
const MAX_STALL_RECOVER_PER_CHUNK = 1;
/** 剩余不足该秒数时提前切到待机槽，抢在 onEnded 前消除空隙 */
const EARLY_SWITCH_REMAIN_SEC = 0.18;
/** 首片开播最长等待；超时视为失败，避免一直 loading 无反馈 */
const FIRST_PLAY_TIMEOUT_MS = 45000;
/** 本会话实际分片上限（start 时按插件可用性选定） */
let sessionChunkMax = CHUNK_MAX_BACKEND;
let chunks = [];
let chunkStarts = [];
let totalChars = 0;
let chunkIndex = 0;
let aborted = false;
let sessionId = 0;
let state = 'idle';
let onStateChange = null;
let onProgressChange = null;
let wechatSIChecked = false;
let wechatSIAvailable = false;
const chunkCache = new Map();
const inflightSynth = new Map();
let prefetchTail = Promise.resolve();
let seekGeneration = 0;
let pendingCharPos = null;
let playToken = 0;
let activePlaySrc = '';
let playingChunkIndex = -1;
let armedPlayToken = 0;
let playbackRate = 1;
let consecutiveSkips = 0;
let skipRecovering = false;
/** 双缓冲：仅播本地文件，待机槽预载下一片 */
let audioPool = [];
let activeSlot = 0;
let standbyChunkIndex = -1;
let standbySrc = '';
let standbyReady = false;
let standbyLoadToken = 0;
let seamlessLock = false;
let lastHeardCurrentTime = -1;
let lastHeardAt = 0;
let hasHeardProgress = false;
let stallWatchTimer = null;
let stallRecovering = false;
let stallRecoverCountForChunk = 0;
let stallRecoverChunkIndex = -1;
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
    if (/REQUEST_FAIL|timeout|connect|下载语音/i.test(msg)) {
        return '无法连接朗读服务，请检查网络后重试';
    }
    if (/插件|WechatSI|requirePlugin/i.test(msg)) {
        return '请在微信公众平台为小程序添加「微信同声传译」插件后重试';
    }
    if (/-40001|频率|limit/i.test(msg)) {
        return '朗读调用过于频繁，请稍后再试';
    }
    if (/-20003|INTERNAL_ERROR/i.test(msg)) {
        return '语音合成服务繁忙，请稍后重试';
    }
    if (/语音合成/i.test(msg)) {
        return '朗读服务暂时不可用，请稍后重试';
    }
    return msg.length > 32 ? `${msg.slice(0, 30)}…` : msg || '朗读失败';
}
function isLocalAudioPath(path) {
    const p = String(path || '');
    if (!p)
        return false;
    if (/^https?:\/\//i.test(p))
        return false;
    return true;
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
        catch {
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
function saveTempToUserData(tempFilePath, dest) {
    return new Promise((resolve, reject) => {
        try {
            wx.getFileSystemManager().saveFile({
                tempFilePath,
                filePath: dest,
                success: () => resolve(dest),
                fail: () => reject(new Error('语音落本地失败')),
            });
        }
        catch {
            reject(new Error('语音落本地失败'));
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
            if (res.filePath) {
                done(undefined, res.filePath);
                return;
            }
            try {
                done(undefined, await saveTempToUserData(res.tempFilePath, dest));
            }
            catch (e) {
                done(e instanceof Error ? e : new Error('语音落本地失败'));
            }
        };
        wx.downloadFile({
            url,
            success: (res) => void finish(res),
            fail: (e) => done(new Error((e === null || e === void 0 ? void 0 : e.errMsg) || '下载语音失败')),
        });
    });
}
/** 远程链尽量落本地；失败时回退直链（真机 downloadFile 域名未配时仍可 InnerAudio 播放） */
async function materializePlayablePath(urlOrPath) {
    const src = String(urlOrPath || '');
    if (!src)
        throw new Error('语音地址为空');
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
function concatArrayBuffers(buffers) {
    const total = buffers.reduce((n, b) => n + b.byteLength, 0);
    const out = new Uint8Array(total);
    let offset = 0;
    for (const b of buffers) {
        out.set(new Uint8Array(b), offset);
        offset += b.byteLength;
    }
    return out.buffer;
}
function readFileArrayBuffer(path) {
    const data = wx.getFileSystemManager().readFileSync(path);
    if (data instanceof ArrayBuffer)
        return data;
    // 部分基础库可能返回其他类型；尽量转成二进制
    if (typeof data === 'string') {
        const bytes = new Uint8Array(data.length);
        for (let i = 0; i < data.length; i++)
            bytes[i] = data.charCodeAt(i) & 0xff;
        return bytes.buffer;
    }
    throw new Error('读取语音文件失败');
}
function writeArrayBufferTempFile(buf) {
    const path = newLocalMp3Path();
    wx.getFileSystemManager().writeFileSync(path, buf);
    return path;
}
/** 后端失败时：WechatSI 按 ≤50 字多段合成后本地拼成一条 MP3 */
async function synthesizeViaWechatSIJoined(content) {
    const parts = chunkTextForTts(content, WECHAT_SI_CHUNK_MAX);
    if (!parts.length)
        throw new Error('语音合成文本为空');
    const buffers = [];
    const tempPaths = [];
    try {
        for (const part of parts) {
            const remote = await textToSpeechNative(part);
            const local = await materializePlayablePath(remote);
            if (!isLocalAudioPath(local.path)) {
                // 无法落本地则不宜拼接，直接抛出让上层按短片播放
                throw new Error('语音落本地失败，无法拼接');
            }
            tempPaths.push(local.path);
            buffers.push(readFileArrayBuffer(local.path));
        }
        const merged = concatArrayBuffers(buffers);
        const path = writeArrayBufferTempFile(merged);
        return { path, isLocalTemp: true };
    }
    finally {
        for (const p of tempPaths)
            unlinkLocalTemp(p);
    }
}
async function textToSpeechBackend(content) {
    var _a;
    const res = await (0, api_1.request)('/narration/synthesize', {
        method: 'POST',
        data: { text: content },
        timeout: 90000,
    });
    const b64 = (_a = res.data) === null || _a === void 0 ? void 0 : _a.audioBase64;
    if (!b64)
        throw new Error('语音合成结果为空');
    const path = await writeMp3TempFile(b64);
    return { path, isLocalTemp: true };
}
async function synthesizeChunk(content) {
    const text = String(content || '').trim();
    if (!text)
        throw new Error('语音合成文本为空');
    // 主路径：微信同声传译（真机可用且不依赖服务端 Edge）
    if (checkWechatSI() && text.length <= WECHAT_SI_CHUNK_MAX) {
        try {
            const remote = await textToSpeechNative(text);
            return await materializePlayablePath(remote);
        }
        catch (e) {
            console.warn('[narration] WechatSI failed, try backend', e);
            try {
                return await textToSpeechBackend(text);
            }
            catch (backendErr) {
                // 保留更贴近用户的插件错误（如 -20003 / -40001）
                const pluginMsg = e instanceof Error ? e.message : String(e);
                const backendMsg = backendErr instanceof Error ? backendErr.message : String(backendErr);
                throw new Error(pluginMsg || backendMsg || '语音合成失败');
            }
        }
    }
    // 无插件或长片：走服务端；失败再尝试插件短片拼接
    try {
        return await textToSpeechBackend(text);
    }
    catch (backendErr) {
        console.warn('[narration] backend synth failed', backendErr);
        if (checkWechatSI()) {
            if (text.length <= WECHAT_SI_CHUNK_MAX) {
                const remote = await textToSpeechNative(text);
                return await materializePlayablePath(remote);
            }
            try {
                return await synthesizeViaWechatSIJoined(text);
            }
            catch (pluginErr) {
                console.warn('[narration] WechatSI joined fallback failed', pluginErr);
            }
        }
        throw backendErr;
    }
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
function schedulePrefetch(fromIndex) {
    const sid = sessionId;
    const ahead = sessionChunkMax <= WECHAT_SI_CHUNK_MAX ? 1 : PREFETCH_AHEAD;
    const start = fromIndex + 1;
    const end = Math.min(chunks.length - 1, fromIndex + ahead);
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
                if (i === fromIndex + 1)
                    void prepareStandby(i);
            }
            catch {
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
function haltCurrentAudio() {
    playToken += 1;
    armedPlayToken = 0;
    activePlaySrc = '';
    playingChunkIndex = -1;
    seamlessLock = false;
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
    if (!(ctx.duration > 0))
        return;
    if (!isLocalAudioPath(path))
        return;
    standbyReady = true;
}
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
        if (!isLocalAudioPath(entry.path))
            return;
        ensureAudioPool();
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
        let tries = 0;
        const poll = () => {
            if (aborted || loadToken !== standbyLoadToken)
                return;
            if (standbyReady)
                return;
            markStandbyReady(loadToken, nextIndex, entry.path, standby);
            if (standbyReady || tries >= 60)
                return;
            tries += 1;
            setTimeout(poll, 40);
        };
        setTimeout(poll, 40);
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
        if (aborted || state !== 'playing' || stallRecovering || seamlessLock || skipRecovering)
            return;
        const audio = getActiveAudio();
        if (!audio)
            return;
        if (!hasHeardProgress)
            return;
        if (Date.now() - lastHeardAt < STALL_MS)
            return;
        const idx = chunkIndex;
        if (stallRecoverChunkIndex !== idx) {
            stallRecoverChunkIndex = idx;
            stallRecoverCountForChunk = 0;
        }
        if (stallRecoverCountForChunk >= MAX_STALL_RECOVER_PER_CHUNK) {
            console.warn('[narration] stall skip chunk after recover limit', idx);
            void recoverBySkipping(idx, 'stall');
            return;
        }
        const entry = chunkCache.get(idx);
        if (!entry)
            return;
        const ratio = audio.duration > 0 ? Math.min(0.98, Math.max(0, (audio.currentTime || 0) / audio.duration)) : 0;
        console.warn('[narration] stall detected, reload chunk', idx);
        stallRecovering = true;
        stallRecoverCountForChunk += 1;
        playToken += 1;
        armedPlayToken = 0;
        activePlaySrc = '';
        playingChunkIndex = -1;
        clearStandby();
        try {
            audio.stop();
        }
        catch {
            /* ignore */
        }
        playFile(entry.path, ratio);
    }, 1000);
}
function recoverBySkipping(failedIndex, reason, detail) {
    var _a;
    if (aborted || skipRecovering)
        return;
    skipRecovering = true;
    stallRecovering = false;
    seamlessLock = false;
    consecutiveSkips += 1;
    playToken += 1;
    armedPlayToken = 0;
    activePlaySrc = '';
    playingChunkIndex = -1;
    clearStandby();
    try {
        (_a = getActiveAudio()) === null || _a === void 0 ? void 0 : _a.stop();
    }
    catch {
        /* ignore */
    }
    console.error('[narration] recover skip', {
        failedIndex,
        reason,
        consecutiveSkips,
        detail,
    });
    const finishHardFail = (title = '播放失败') => {
        skipRecovering = false;
        stopNarration();
        wx.showToast({ title, icon: 'none' });
    };
    if (consecutiveSkips > MAX_CONSECUTIVE_SKIPS) {
        finishHardFail();
        return;
    }
    const next = failedIndex + 1;
    if (next >= chunks.length) {
        skipRecovering = false;
        stopNarration();
        return;
    }
    chunkIndex = next;
    void playNextChunk(0)
        .then(() => {
        skipRecovering = false;
    })
        .catch((e) => {
        if (aborted) {
            skipRecovering = false;
            return;
        }
        const raw = e instanceof Error ? e.message : String(e);
        finishHardFail(friendlyTtsError(raw).slice(0, 28));
    });
}
/** 待机槽无缝切换；成功返回 true */
function trySeamlessToNext(fromIndex) {
    const nextIndex = fromIndex + 1;
    if (nextIndex >= chunks.length)
        return false;
    if (seamlessLock || skipRecovering || stallRecovering)
        return false;
    if (!standbyReady ||
        standbyChunkIndex !== nextIndex ||
        !standbySrc ||
        !isLocalAudioPath(standbySrc)) {
        return false;
    }
    const nextCtx = audioPool[1 - activeSlot];
    if (!nextCtx || !(nextCtx.duration > 0))
        return false;
    seamlessLock = true;
    const prevSlot = activeSlot;
    const token = ++playToken;
    try {
        nextCtx.volume = 1;
        nextCtx.playbackRate = playbackRate;
    }
    catch {
        /* ignore */
    }
    try {
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
        consecutiveSkips = 0;
        pendingCharPos = null;
        setState('playing');
        notePlaybackHeartbeat(0);
        startStallWatch();
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
            seamlessLock = false;
        }, 80);
        schedulePrefetch(chunkIndex);
        void prepareStandby(chunkIndex + 1);
        emitProgress(nextCtx.currentTime || 0, nextCtx.duration || 0);
        return true;
    }
    catch (e) {
        console.error('[narration] seamless play()', e);
        seamlessLock = false;
        return false;
    }
}
function chunkTextForTts(text, maxLen = CHUNK_MAX_BACKEND) {
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
    seamlessLock = false;
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
    consecutiveSkips = 0;
    skipRecovering = false;
    stallRecoverCountForChunk = 0;
    stallRecoverChunkIndex = -1;
}
function bindSlotListeners(ctx, slot) {
    ctx.onEnded(() => {
        if (aborted || slot !== activeSlot)
            return;
        if (seamlessLock)
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
        armedPlayToken = 0;
        playingChunkIndex = -1;
        consecutiveSkips = 0;
        if (trySeamlessToNext(endedIndex))
            return;
        chunkIndex = endedIndex + 1;
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
        if (seamlessLock)
            return;
        const cur = ctx.currentTime || 0;
        const dur = ctx.duration || 0;
        notePlaybackHeartbeat(cur);
        if (dur > 0) {
            const entry = chunkCache.get(chunkIndex);
            if (entry && !entry.durationSec) {
                chunkCache.set(chunkIndex, { ...entry, durationSec: dur });
            }
            // 过半预热下一片到待机槽
            if (cur / dur >= 0.35 && chunkIndex + 1 < chunks.length) {
                if (!standbyReady || standbyChunkIndex !== chunkIndex + 1) {
                    void prepareStandby(chunkIndex + 1);
                }
            }
            // 片尾提前无缝切，消除 onEnded 空隙
            if (playingChunkIndex === chunkIndex &&
                armedPlayToken === playToken &&
                dur - cur <= EARLY_SWITCH_REMAIN_SEC &&
                dur - cur >= 0) {
                if (trySeamlessToNext(chunkIndex))
                    return;
            }
        }
        emitProgress(cur, dur);
    });
    ctx.onError((err) => {
        if (aborted || skipRecovering || stallRecovering || seamlessLock)
            return;
        if (slot !== activeSlot)
            return;
        const idx = playingChunkIndex;
        if (idx < 0 || idx !== chunkIndex)
            return;
        console.error('[narration] play error', err);
        const entry = chunkCache.get(idx);
        if (entry && activePlaySrc !== entry.path && isLocalAudioPath(entry.path)) {
            playFile(entry.path, 0);
            return;
        }
        recoverBySkipping(idx, 'onError', err);
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
    // 远程链不做待机双缓冲，避免真机长会话抢焦点
    clearStandby();
    seamlessLock = false;
    const token = ++playToken;
    armedPlayToken = 0;
    activePlaySrc = filename;
    playingChunkIndex = chunkIndex;
    let started = false;
    const isRemote = /^https?:\/\//i.test(filename);
    const armEnded = () => {
        if (token === playToken)
            armedPlayToken = token;
    };
    const afterPlayStarted = () => {
        consecutiveSkips = 0;
        pendingCharPos = null;
        notePlaybackHeartbeat(audio.currentTime || 0);
        startStallWatch();
        schedulePrefetch(chunkIndex);
        // 仅本地文件预载待机槽；远程直链走顺序换源
        if (!isRemote)
            void prepareStandby(chunkIndex + 1);
        emitProgress(audio.currentTime || 0, audio.duration || 0);
    };
    const failPlay = (e) => {
        console.error('[narration] play()', e);
        recoverBySkipping(chunkIndex, 'play()', e);
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
                failPlay(e);
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
                failPlay(e);
                return;
            }
            consecutiveSkips = 0;
            notePlaybackHeartbeat(0);
            startStallWatch();
            schedulePrefetch(chunkIndex);
            if (!isRemote)
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
    if (!isRemote) {
        setTimeout(playNow, 0);
    }
    setTimeout(() => {
        if (!aborted && token === playToken && !started)
            playNow();
    }, isRemote ? 280 : 80);
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
    let didStart = false;
    while (chunkIndex < chunks.length) {
        if (aborted || sid !== sessionId || seekGen !== seekGeneration)
            return;
        const idx = chunkIndex;
        const cached = chunkCache.get(idx);
        if (!cached)
            setState('loading');
        try {
            const entry = cached || (await ensureChunk(idx));
            if (aborted || sid !== sessionId || seekGen !== seekGeneration)
                return;
            playFile(entry.path, seekRatio);
            didStart = true;
            return;
        }
        catch (e) {
            if (aborted || sid !== sessionId || seekGen !== seekGeneration)
                return;
            consecutiveSkips += 1;
            console.error('[narration] synth skip', idx, e);
            if (idx + 1 >= chunks.length) {
                stopNarration();
                const raw = e instanceof Error ? e.message : String(e);
                throw new Error(friendlyTtsError(raw));
            }
            if (consecutiveSkips > MAX_CONSECUTIVE_SKIPS) {
                stopNarration();
                const raw = e instanceof Error ? e.message : String(e);
                throw new Error(friendlyTtsError(raw));
            }
            chunkIndex = idx + 1;
            seekRatio = 0;
        }
    }
    stopNarration();
    if (!didStart)
        throw new Error('语音合成失败，请稍后重试');
}
function waitForPlaying(timeoutMs) {
    if (state === 'playing' || state === 'paused')
        return Promise.resolve();
    const sid = sessionId;
    return new Promise((resolve, reject) => {
        const startedAt = Date.now();
        const timer = setInterval(() => {
            if (aborted || sid !== sessionId) {
                clearInterval(timer);
                reject(new Error('朗读已取消'));
                return;
            }
            if (state === 'playing' || state === 'paused') {
                clearInterval(timer);
                resolve();
                return;
            }
            if (Date.now() - startedAt >= timeoutMs) {
                clearInterval(timer);
                reject(new Error('朗读启动超时，请检查网络后重试'));
            }
        }, 100);
    });
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
    onStateChange = null;
    onProgressChange = null;
    stopNarration({ silent: true });
    aborted = false;
    consecutiveSkips = 0;
    skipRecovering = false;
    onStateChange = stateCb;
    onProgressChange = progressCb || null;
    // 有同声传译插件：按官方 50 字分片，真机主路径不依赖服务端 Edge
    sessionChunkMax = checkWechatSI() ? WECHAT_SI_CHUNK_MAX : CHUNK_MAX_BACKEND;
    const parts = chunkTextForTts(text, sessionChunkMax);
    if (!parts.length)
        throw new Error('暂无正文可朗读');
    rebuildCharAxis(parts);
    chunkIndex = 0;
    pendingCharPos = null;
    setState('loading');
    emitProgressFromChar(0);
    if (parts.length > 1) {
        void ensureChunk(1).catch(() => undefined);
    }
    try {
        await playNextChunk(0);
        await waitForPlaying(FIRST_PLAY_TIMEOUT_MS);
    }
    catch (e) {
        // 保证失败后不卡在 loading，允许用户再次点击
        if (state === 'loading') {
            stopNarration({ silent: true });
        }
        throw e;
    }
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
function seekNarrationPct(pct) {
    if (!chunks.length || (state !== 'playing' && state !== 'paused' && state !== 'loading'))
        return;
    const p = Math.max(0, Math.min(100, pct));
    const targetChar = (p / 100) * totalChars;
    void jumpToChar(targetChar);
}
exports.seekNarrationPct = seekNarrationPct;
function setPlaybackRate(rate) {
    playbackRate = rate;
    for (const ctx of audioPool) {
        try {
            ctx.playbackRate = rate;
        }
        catch {
            /* ignore */
        }
    }
}
exports.setPlaybackRate = setPlaybackRate;
