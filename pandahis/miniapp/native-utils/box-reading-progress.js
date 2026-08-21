"use strict";
/** 史略详情阅读进度：登录用户持久化。
 * 锚点优先 scrollTopPx（有栏坐标系下的 scroll-view 偏移），progressPct 作跨端兜底。
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.persistBoxReadingProgress = exports.resolveBoxReadingProgress = exports.saveRemoteBoxReadingProgress = exports.fetchRemoteBoxReadingProgress = exports.writeLocalBoxReadingProgress = exports.readLocalBoxReadingProgress = exports.writeLocalBoxReadingProgressMap = exports.readLocalBoxReadingProgressMap = exports.upsertProgressMap = exports.pickNewerProgress = exports.readProgressMap = exports.normalizeProgressRecord = exports.resolveRestoreScrollTop = exports.normalizeScrollTopPx = exports.originalViewportFallbackPx = exports.originalReadingProgressId = exports.ORIGINAL_READING_PROGRESS_SUFFIX = exports.detailViewportFallbackPx = exports.maxScrollFromMetrics = exports.scrollTopFromProgressPct = exports.progressPctFromScroll = exports.clampProgressPct = exports.isRestorableProgressPct = exports.readingProgressScopeKey = exports.BOX_READING_PROGRESS_STORAGE_KEY = exports.MAX_RESTORABLE_PROGRESS_PCT = exports.MIN_RESTORABLE_PROGRESS_PCT = void 0;
const api_1 = require("./api");
const encode_path_segment_1 = require("./encode-path-segment");
exports.MIN_RESTORABLE_PROGRESS_PCT = 5;
exports.MAX_RESTORABLE_PROGRESS_PCT = 95;
exports.BOX_READING_PROGRESS_STORAGE_KEY = 'boxReadingProgressByUser';
/** 按登录令牌分桶，避免换账号串本地进度 */
function readingProgressScopeKey(token = (0, api_1.getToken)()) {
    const raw = String(token || '').trim();
    if (!raw)
        return null;
    let hash = 0;
    for (let i = 0; i < raw.length; i += 1) {
        hash = ((hash << 5) - hash + raw.charCodeAt(i)) | 0;
    }
    return `s${hash}`;
}
exports.readingProgressScopeKey = readingProgressScopeKey;
function isRestorableProgressPct(pct) {
    return typeof pct === 'number'
        && Number.isFinite(pct)
        && pct >= exports.MIN_RESTORABLE_PROGRESS_PCT
        && pct <= exports.MAX_RESTORABLE_PROGRESS_PCT;
}
exports.isRestorableProgressPct = isRestorableProgressPct;
function clampProgressPct(pct) {
    if (typeof pct !== 'number' || !Number.isFinite(pct))
        return 0;
    return Math.min(100, Math.max(0, Math.round(pct)));
}
exports.clampProgressPct = clampProgressPct;
function progressPctFromScroll(scrollTop, maxScroll) {
    if (!(maxScroll > 0) || !(scrollTop >= 0))
        return 0;
    return clampProgressPct((scrollTop / maxScroll) * 100);
}
exports.progressPctFromScroll = progressPctFromScroll;
function scrollTopFromProgressPct(pct, maxScroll) {
    if (!isRestorableProgressPct(pct) || !(maxScroll > 0))
        return 0;
    return Math.max(0, Math.round((pct / 100) * maxScroll));
}
exports.scrollTopFromProgressPct = scrollTopFromProgressPct;
function maxScrollFromMetrics(scrollHeight, viewportH) {
    return Math.max((Number(scrollHeight) || 0) - (Number(viewportH) || 0), 0);
}
exports.maxScrollFromMetrics = maxScrollFromMetrics;
/** 详情 Tab 栏为绝对定位 overlay，视口回退用 tabTop（勿用 bodyTop，会多扣 Tab 高） */
function detailViewportFallbackPx(windowHeight, tabTop) {
    return Math.max((Number(windowHeight) || 0) - (Number(tabTop) || 0), 0);
}
exports.detailViewportFallbackPx = detailViewportFallbackPx;
exports.ORIGINAL_READING_PROGRESS_SUFFIX = '__original';
/** 原文半屏进度与详情隔离：同一 box 使用独立存储键 */
function originalReadingProgressId(boxId) {
    const id = String(boxId || '').trim();
    if (!id)
        return '';
    if (id.endsWith(exports.ORIGINAL_READING_PROGRESS_SUFFIX))
        return id;
    return `${id}${exports.ORIGINAL_READING_PROGRESS_SUFFIX}`;
}
exports.originalReadingProgressId = originalReadingProgressId;
/** 原文半屏 body 约 62vh；测不到 DOM 时作百分比换算回退 */
function originalViewportFallbackPx(windowHeight) {
    return Math.max(Math.round((Number(windowHeight) || 0) * 0.62), 0);
}
exports.originalViewportFallbackPx = originalViewportFallbackPx;
function normalizeScrollTopPx(raw) {
    if (typeof raw !== 'number' || !Number.isFinite(raw))
        return null;
    const n = Math.round(raw);
    if (n < 0 || n > 2000000)
        return null;
    return n;
}
exports.normalizeScrollTopPx = normalizeScrollTopPx;
/** 恢复目标：有 scrollTop 用 scrollTop（夹到 maxScroll）；否则用百分比 */
function resolveRestoreScrollTop(record, maxScroll) {
    if (!record || !isRestorableProgressPct(record.progressPct))
        return 0;
    const safeMax = Math.max(0, maxScroll);
    const scrollTop = normalizeScrollTopPx(record.scrollTopPx);
    if (scrollTop != null && scrollTop > 0) {
        return Math.min(scrollTop, safeMax);
    }
    return scrollTopFromProgressPct(record.progressPct, safeMax);
}
exports.resolveRestoreScrollTop = resolveRestoreScrollTop;
function normalizeProgressRecord(raw) {
    if (!raw || typeof raw !== 'object' || Array.isArray(raw))
        return null;
    const obj = raw;
    const progressPct = clampProgressPct(obj.progressPct);
    if (!isRestorableProgressPct(progressPct))
        return null;
    const updatedAt = typeof obj.updatedAt === 'string' && obj.updatedAt.trim()
        ? obj.updatedAt.trim()
        : '';
    if (!updatedAt || !Number.isFinite(Date.parse(updatedAt)))
        return null;
    return {
        progressPct,
        scrollTopPx: normalizeScrollTopPx(obj.scrollTopPx),
        updatedAt,
    };
}
exports.normalizeProgressRecord = normalizeProgressRecord;
function readProgressMap(raw) {
    if (!raw || typeof raw !== 'object' || Array.isArray(raw))
        return {};
    const out = {};
    for (const [boxId, value] of Object.entries(raw)) {
        const id = String(boxId || '').trim();
        if (!id)
            continue;
        const record = normalizeProgressRecord(value);
        if (record)
            out[id] = record;
    }
    return out;
}
exports.readProgressMap = readProgressMap;
/** 取本地/远端中较新的一条；均无效则 null */
function pickNewerProgress(local, remote) {
    const a = normalizeProgressRecord(local);
    const b = normalizeProgressRecord(remote);
    if (!a)
        return b;
    if (!b)
        return a;
    return Date.parse(b.updatedAt) > Date.parse(a.updatedAt) ? b : a;
}
exports.pickNewerProgress = pickNewerProgress;
function upsertProgressMap(map, boxId, input, updatedAt = new Date().toISOString()) {
    const id = String(boxId || '').trim();
    const prev = readProgressMap(map);
    if (!id)
        return prev;
    const next = { ...prev };
    const progressPct = clampProgressPct(input.progressPct);
    if (!isRestorableProgressPct(progressPct)) {
        if (Object.prototype.hasOwnProperty.call(next, id)) {
            delete next[id];
        }
        return next;
    }
    next[id] = {
        progressPct,
        scrollTopPx: normalizeScrollTopPx(input.scrollTopPx),
        updatedAt: String(updatedAt || new Date().toISOString()),
    };
    return next;
}
exports.upsertProgressMap = upsertProgressMap;
function readScopedStore() {
    try {
        const raw = wx.getStorageSync(exports.BOX_READING_PROGRESS_STORAGE_KEY);
        if (!raw || typeof raw !== 'object' || Array.isArray(raw))
            return {};
        const out = {};
        for (const [scope, value] of Object.entries(raw)) {
            const key = String(scope || '').trim();
            if (!key)
                continue;
            out[key] = readProgressMap(value);
        }
        return out;
    }
    catch {
        return {};
    }
}
function writeScopedStore(store) {
    try {
        wx.setStorageSync(exports.BOX_READING_PROGRESS_STORAGE_KEY, store);
    }
    catch {
        // ignore
    }
}
function readLocalBoxReadingProgressMap() {
    const scope = readingProgressScopeKey();
    if (!scope)
        return {};
    return readProgressMap(readScopedStore()[scope]);
}
exports.readLocalBoxReadingProgressMap = readLocalBoxReadingProgressMap;
function writeLocalBoxReadingProgressMap(map) {
    const scope = readingProgressScopeKey();
    if (!scope)
        return;
    const store = { ...readScopedStore(), [scope]: readProgressMap(map) };
    writeScopedStore(store);
}
exports.writeLocalBoxReadingProgressMap = writeLocalBoxReadingProgressMap;
function readLocalBoxReadingProgress(boxId) {
    const id = String(boxId || '').trim();
    if (!id)
        return null;
    return normalizeProgressRecord(readLocalBoxReadingProgressMap()[id]);
}
exports.readLocalBoxReadingProgress = readLocalBoxReadingProgress;
function writeLocalBoxReadingProgress(boxId, input, updatedAt = new Date().toISOString()) {
    const scope = readingProgressScopeKey();
    if (!scope)
        return null;
    const next = upsertProgressMap(readLocalBoxReadingProgressMap(), boxId, input, updatedAt);
    writeLocalBoxReadingProgressMap(next);
    const id = String(boxId || '').trim();
    return id ? normalizeProgressRecord(next[id]) : null;
}
exports.writeLocalBoxReadingProgress = writeLocalBoxReadingProgress;
async function fetchRemoteBoxReadingProgress(boxId) {
    var _a, _b, _c;
    if (!(0, api_1.hasToken)())
        return null;
    const id = String(boxId || '').trim();
    if (!id)
        return null;
    try {
        const res = await (0, api_1.request)(`/me/boxes/${(0, encode_path_segment_1.encodePathSegment)(id)}/reading-progress`, { method: 'GET', auth: true });
        return normalizeProgressRecord({
            progressPct: (_a = res.data) === null || _a === void 0 ? void 0 : _a.progressPct,
            scrollTopPx: (_b = res.data) === null || _b === void 0 ? void 0 : _b.scrollTopPx,
            updatedAt: (_c = res.data) === null || _c === void 0 ? void 0 : _c.updatedAt,
        });
    }
    catch {
        return null;
    }
}
exports.fetchRemoteBoxReadingProgress = fetchRemoteBoxReadingProgress;
async function saveRemoteBoxReadingProgress(boxId, input) {
    var _a, _b, _c;
    if (!(0, api_1.hasToken)())
        return null;
    const id = String(boxId || '').trim();
    if (!id)
        return null;
    try {
        const res = await (0, api_1.request)(`/me/boxes/${(0, encode_path_segment_1.encodePathSegment)(id)}/reading-progress`, {
            method: 'PUT',
            auth: true,
            data: {
                progressPct: clampProgressPct(input.progressPct),
                scrollTopPx: normalizeScrollTopPx(input.scrollTopPx),
            },
        });
        return normalizeProgressRecord({
            progressPct: (_a = res.data) === null || _a === void 0 ? void 0 : _a.progressPct,
            scrollTopPx: (_b = res.data) === null || _b === void 0 ? void 0 : _b.scrollTopPx,
            updatedAt: (_c = res.data) === null || _c === void 0 ? void 0 : _c.updatedAt,
        });
    }
    catch {
        return null;
    }
}
exports.saveRemoteBoxReadingProgress = saveRemoteBoxReadingProgress;
/** 登录用户：合并本地与远端进度；未登录恒为 null */
async function resolveBoxReadingProgress(boxId) {
    if (!(0, api_1.hasToken)())
        return null;
    const local = readLocalBoxReadingProgress(boxId);
    const remote = await fetchRemoteBoxReadingProgress(boxId);
    const picked = pickNewerProgress(local, remote);
    if (picked) {
        writeLocalBoxReadingProgress(boxId, { progressPct: picked.progressPct, scrollTopPx: picked.scrollTopPx }, picked.updatedAt);
    }
    return picked;
}
exports.resolveBoxReadingProgress = resolveBoxReadingProgress;
/** 登录用户：写本地并尽力同步远端；未登录 no-op */
async function persistBoxReadingProgress(boxId, input) {
    if (!(0, api_1.hasToken)())
        return;
    writeLocalBoxReadingProgress(boxId, input);
    await saveRemoteBoxReadingProgress(boxId, input);
}
exports.persistBoxReadingProgress = persistBoxReadingProgress;
