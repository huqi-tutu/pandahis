"use strict";
/**
 * 史略详情朗读：优先微信同声传译插件 TTS + InnerAudioContext 原生播放；
 * 插件不可用时回退服务端合成 MP3。
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.setPlaybackRate = exports.seekNarrationPct = exports.seekNarration = exports.toggleNarrationPlayback = exports.startNarration = exports.resumeNarration = exports.pauseNarration = exports.stopNarration = exports.getNarrationState = exports.buildBoxNarrationScript = exports.chunkTextForTts = void 0;
const api_1 = require("./api");
const CHUNK_MAX = 180;
const TEXT_MAX = 6000;
let audio = null;
let chunks = [];
let chunkIndex = 0;
let aborted = false;
let state = 'idle';
let onStateChange = null;
let onProgressChange = null;
let wechatSIChecked = false;
let wechatSIAvailable = false;
function formatMmSs(sec) {
    if (!Number.isFinite(sec) || sec < 0)
        return '0:00';
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m}:${s < 10 ? '0' : ''}${s}`;
}
function emitProgress(currentSec = 0, durationSec = 0) {
    const dur = durationSec > 0 ? durationSec : 1;
    const chunkPart = chunks.length ? chunkIndex / chunks.length : 0;
    const innerPart = Math.min(1, currentSec / dur) / (chunks.length || 1);
    const progress = Math.min(100, Math.round((chunkPart + innerPart) * 100));
    onProgressChange === null || onProgressChange === void 0 ? void 0 : onProgressChange({
        progress,
        current: formatMmSs(currentSec),
        duration: formatMmSs(durationSec),
    });
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
function writeMp3TempFile(base64) {
    const fs = wx.getFileSystemManager();
    const path = `${wx.env.USER_DATA_PATH}/tts_${Date.now()}_${Math.random().toString(36).slice(2, 8)}.mp3`;
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
async function textToSpeechBackend(content) {
    var _a;
    const res = await (0, api_1.request)('/narration/synthesize', {
        method: 'POST',
        data: { text: content },
    });
    const b64 = (_a = res.data) === null || _a === void 0 ? void 0 : _a.audioBase64;
    if (!b64)
        throw new Error('语音合成结果为空');
    return writeMp3TempFile(b64);
}
async function synthesizeChunk(content) {
    if (checkWechatSI()) {
        try {
            return await textToSpeechNative(content);
        }
        catch {
            /* 插件失败时回退服务端 */
        }
    }
    return textToSpeechBackend(content);
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
    if (!audio)
        return;
    try {
        audio.stop();
        audio.destroy();
    }
    catch {
        /* ignore */
    }
    audio = null;
}
function ensureAudio() {
    if (audio)
        return;
    audio = wx.createInnerAudioContext();
    audio.obeyMuteSwitch = false;
    audio.autoplay = false;
    audio.onEnded(() => {
        if (aborted)
            return;
        chunkIndex += 1;
        void playNextChunk();
    });
    audio.onTimeUpdate(() => {
        if (aborted || !audio)
            return;
        emitProgress(audio.currentTime || 0, audio.duration || 0);
    });
    audio.onError((err) => {
        if (aborted)
            return;
        console.error('[narration] play error', err);
        stopNarration();
        wx.showToast({ title: '播放失败', icon: 'none' });
    });
}
function playFile(filename) {
    var _a;
    ensureAudio();
    if (!audio || aborted)
        return;
    const playNow = () => {
        if (aborted || !audio)
            return;
        setState('playing');
        try {
            audio.play();
        }
        catch (e) {
            console.error('[narration] play()', e);
            stopNarration();
            wx.showToast({ title: '播放失败', icon: 'none' });
        }
    };
    (_a = audio.offCanplay) === null || _a === void 0 ? void 0 : _a.call(audio);
    audio.onCanplay(playNow);
    audio.src = filename;
    // 部分机型 onCanplay 不触发，兜底直接 play
    setTimeout(() => {
        if (!aborted && state === 'loading' && audio) {
            playNow();
        }
    }, 400);
}
async function playNextChunk() {
    if (aborted)
        return;
    if (chunkIndex >= chunks.length) {
        stopNarration();
        return;
    }
    setState('loading');
    const content = chunks[chunkIndex];
    try {
        const filename = await synthesizeChunk(content);
        if (aborted)
            return;
        playFile(filename);
    }
    catch (e) {
        stopNarration();
        const raw = e instanceof Error ? e.message : String(e);
        throw new Error(friendlyTtsError(raw));
    }
}
function getNarrationState() {
    return state;
}
exports.getNarrationState = getNarrationState;
function stopNarration() {
    aborted = true;
    chunks = [];
    chunkIndex = 0;
    destroyAudio();
    onProgressChange = null;
    setState('idle');
}
exports.stopNarration = stopNarration;
function pauseNarration() {
    if (!audio || state !== 'playing')
        return;
    try {
        audio.pause();
    }
    catch {
        /* ignore */
    }
    setState('paused');
}
exports.pauseNarration = pauseNarration;
function resumeNarration() {
    if (!audio || state !== 'paused')
        return;
    try {
        audio.play();
    }
    catch {
        /* ignore */
    }
    setState('playing');
}
exports.resumeNarration = resumeNarration;
async function startNarration(text, stateCb, progressCb) {
    stopNarration();
    aborted = false;
    onStateChange = stateCb;
    onProgressChange = progressCb || null;
    chunks = chunkTextForTts(text);
    if (!chunks.length)
        throw new Error('暂无正文可朗读');
    chunkIndex = 0;
    setState('loading');
    await playNextChunk();
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
 * 在当前音频片段内 seek 偏移（秒），正数快进、负数快退
 * 超出当前片段范围时取边界值
 */
function seekNarration(offsetSec) {
    if (!audio || (state !== 'playing' && state !== 'paused'))
        return;
    try {
        const cur = audio.currentTime || 0;
        const dur = audio.duration || 0;
        const target = Math.max(0, Math.min(dur, cur + offsetSec));
        audio.seek(target);
    }
    catch {
        // seek 失败静默处理
    }
}
exports.seekNarration = seekNarration;
/**
 * 在当前音频片段内 seek 到指定百分比（0-100）
 */
function seekNarrationPct(pct) {
    if (!audio || (state !== 'playing' && state !== 'paused'))
        return;
    try {
        const dur = audio.duration || 0;
        const target = Math.max(0, Math.min(dur, (pct / 100) * dur));
        audio.seek(target);
    }
    catch {
        // seek 失败静默处理
    }
}
exports.seekNarrationPct = seekNarrationPct;
/** 设置播放速度（需基础库 2.11.0+） */
function setPlaybackRate(rate) {
    if (!audio)
        return;
    try {
        audio.playbackRate = rate;
    }
    catch {
        // 低版本基础库不支持，静默忽略
    }
}
exports.setPlaybackRate = setPlaybackRate;
