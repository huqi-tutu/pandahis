"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.navigateToNoteSource = exports.resolveNoteSourceNav = exports.fetchNoteHighlights = exports.fetchNotesByDynasty = exports.fetchNoteDynasties = exports.fetchNoteDetail = exports.deleteNote = exports.updateNote = exports.submitNote = exports.requireLoginForNote = exports.promptLoginForNote = exports.excerptText = exports.noteRemarkLabel = exports.formatNoteTime = exports.noteSourceLabel = exports.NOTE_SOURCE_LABEL = exports.NOTE_TEXT_MAX = exports.EMPTY_NOTE_LABEL = void 0;
const api_1 = require("./api");
const encode_path_segment_1 = require("./encode-path-segment");
const router_1 = require("./router");
exports.EMPTY_NOTE_LABEL = '仅划线';
exports.NOTE_TEXT_MAX = 2000;
exports.NOTE_SOURCE_LABEL = {
    box_detail_selection: '史略详情',
    critique_detail_selection: '评述',
    relic_detail_selection: '见证',
    relation_graph_selection: '关系图谱',
};
function noteSourceLabel(sourceType) {
    return exports.NOTE_SOURCE_LABEL[sourceType] || sourceType || '';
}
exports.noteSourceLabel = noteSourceLabel;
function formatNoteTime(iso) {
    if (!iso)
        return '';
    const d = new Date(iso);
    if (Number.isNaN(d.getTime()))
        return iso.replace('T', ' ').slice(0, 19);
    const pad = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
exports.formatNoteTime = formatNoteTime;
function noteRemarkLabel(noteText) {
    const text = String(noteText || '').trim();
    return text || exports.EMPTY_NOTE_LABEL;
}
exports.noteRemarkLabel = noteRemarkLabel;
function excerptText(text, max = 80) {
    const t = String(text || '').replace(/\s+/g, ' ').trim();
    if (t.length <= max)
        return t;
    return `${t.slice(0, max)}…`;
}
exports.excerptText = excerptText;
function toNullableNumber(raw) {
    if (raw === undefined || raw === null || raw === '')
        return null;
    const n = Number(raw);
    return Number.isFinite(n) && n > 0 ? n : null;
}
function normalizeDetail(raw) {
    var _a, _b, _c, _d, _e, _f, _g, _h, _j, _k, _l, _m, _o, _p, _q, _r, _s, _t, _u, _v, _w, _x, _y, _z, _0, _1, _2, _3, _4, _5, _6, _7;
    return {
        id: Number((_a = raw.id) !== null && _a !== void 0 ? _a : 0),
        boxId: String((_c = (_b = raw.boxId) !== null && _b !== void 0 ? _b : raw['box_id']) !== null && _c !== void 0 ? _c : ''),
        boxTitle: String((_e = (_d = raw.boxTitle) !== null && _d !== void 0 ? _d : raw['box_title']) !== null && _e !== void 0 ? _e : ''),
        boxCategoryKey: String((_g = (_f = raw.boxCategoryKey) !== null && _f !== void 0 ? _f : raw['box_category_key']) !== null && _g !== void 0 ? _g : ''),
        boxCategoryName: String((_j = (_h = raw.boxCategoryName) !== null && _h !== void 0 ? _h : raw['box_category_name']) !== null && _j !== void 0 ? _j : ''),
        unitId: ((_l = (_k = raw.unitId) !== null && _k !== void 0 ? _k : raw['unit_id']) !== null && _l !== void 0 ? _l : null),
        civilizationName: String((_o = (_m = raw.civilizationName) !== null && _m !== void 0 ? _m : raw['civilization_name']) !== null && _o !== void 0 ? _o : ''),
        dynastyName: String((_q = (_p = raw.dynastyName) !== null && _p !== void 0 ? _p : raw['dynasty_name']) !== null && _q !== void 0 ? _q : ''),
        regimeName: String((_s = (_r = raw.regimeName) !== null && _r !== void 0 ? _r : raw['regime_name']) !== null && _s !== void 0 ? _s : ''),
        emperorName: String((_u = (_t = raw.emperorName) !== null && _t !== void 0 ? _t : raw['emperor_name']) !== null && _u !== void 0 ? _u : ''),
        coordinateText: String((_w = (_v = raw.coordinateText) !== null && _v !== void 0 ? _v : raw['coordinate_text']) !== null && _w !== void 0 ? _w : ''),
        sourceType: String((_y = (_x = raw.sourceType) !== null && _x !== void 0 ? _x : raw['source_type']) !== null && _y !== void 0 ? _y : ''),
        sourceRefId: toNullableNumber((_z = raw.sourceRefId) !== null && _z !== void 0 ? _z : raw['source_ref_id']),
        selectedText: String((_1 = (_0 = raw.selectedText) !== null && _0 !== void 0 ? _0 : raw['selected_text']) !== null && _1 !== void 0 ? _1 : ''),
        noteText: ((_3 = (_2 = raw.noteText) !== null && _2 !== void 0 ? _2 : raw['note_text']) !== null && _3 !== void 0 ? _3 : null),
        createdAt: String((_5 = (_4 = raw.createdAt) !== null && _4 !== void 0 ? _4 : raw['created_at']) !== null && _5 !== void 0 ? _5 : ''),
        updatedAt: ((_7 = (_6 = raw.updatedAt) !== null && _6 !== void 0 ? _6 : raw['updated_at']) !== null && _7 !== void 0 ? _7 : null),
    };
}
function normalizeDynasty(raw) {
    var _a, _b, _c, _d, _e, _f, _g, _h, _j, _k;
    return {
        dynastyId: String((_b = (_a = raw.dynastyId) !== null && _a !== void 0 ? _a : raw['dynasty_id']) !== null && _b !== void 0 ? _b : ''),
        dynastyName: String((_d = (_c = raw.dynastyName) !== null && _c !== void 0 ? _c : raw['dynasty_name']) !== null && _d !== void 0 ? _d : ''),
        civilizationName: String((_f = (_e = raw.civilizationName) !== null && _e !== void 0 ? _e : raw['civilization_name']) !== null && _f !== void 0 ? _f : ''),
        noteCount: Number((_h = (_g = raw.noteCount) !== null && _g !== void 0 ? _g : raw['note_count']) !== null && _h !== void 0 ? _h : 0),
        startYear: ((_k = (_j = raw.startYear) !== null && _j !== void 0 ? _j : raw['start_year']) !== null && _k !== void 0 ? _k : null),
    };
}
function normalizeListItem(raw) {
    var _a, _b, _c, _d, _e, _f, _g, _h, _j, _k, _l;
    return {
        id: Number((_a = raw.id) !== null && _a !== void 0 ? _a : 0),
        boxId: String((_c = (_b = raw.boxId) !== null && _b !== void 0 ? _b : raw['box_id']) !== null && _c !== void 0 ? _c : ''),
        boxTitle: String((_e = (_d = raw.boxTitle) !== null && _d !== void 0 ? _d : raw['box_title']) !== null && _e !== void 0 ? _e : ''),
        selectedText: String((_g = (_f = raw.selectedText) !== null && _f !== void 0 ? _f : raw['selected_text']) !== null && _g !== void 0 ? _g : ''),
        noteText: ((_j = (_h = raw.noteText) !== null && _h !== void 0 ? _h : raw['note_text']) !== null && _j !== void 0 ? _j : null),
        createdAt: String((_l = (_k = raw.createdAt) !== null && _k !== void 0 ? _k : raw['created_at']) !== null && _l !== void 0 ? _l : ''),
    };
}
function normalizeHighlight(raw) {
    var _a, _b, _c;
    return {
        id: Number((_a = raw.id) !== null && _a !== void 0 ? _a : 0),
        selectedText: String((_c = (_b = raw.selectedText) !== null && _b !== void 0 ? _b : raw['selected_text']) !== null && _c !== void 0 ? _c : ''),
    };
}
function promptLoginForNote() {
    wx.showModal({
        title: '需要登录',
        content: '登录后可将划线与笔记保存到你的账号，并在「我的笔记」中查看。',
        confirmText: '去登录',
        success: (r) => {
            if (r.confirm)
                (0, router_1.navigateTo)(router_1.ROUTES.login);
        },
    });
}
exports.promptLoginForNote = promptLoginForNote;
function requireLoginForNote(action) {
    if (!(0, api_1.hasToken)()) {
        promptLoginForNote();
        return;
    }
    action();
}
exports.requireLoginForNote = requireLoginForNote;
async function submitNote(payload) {
    const res = await (0, api_1.request)('/notes', {
        method: 'POST',
        auth: true,
        data: {
            boxId: payload.boxId,
            sourceType: payload.sourceType,
            selectedText: payload.selectedText,
            noteText: payload.noteText || undefined,
            sourceRefId: payload.sourceRefId || undefined,
        },
    });
    return normalizeDetail((res.data || {}));
}
exports.submitNote = submitNote;
async function updateNote(id, noteText) {
    const res = await (0, api_1.request)(`/notes/${(0, encode_path_segment_1.encodePathSegment)(String(id))}`, {
        method: 'PATCH',
        auth: true,
        data: { noteText: noteText || '' },
    });
    return normalizeDetail((res.data || {}));
}
exports.updateNote = updateNote;
async function deleteNote(id) {
    await (0, api_1.request)(`/notes/${(0, encode_path_segment_1.encodePathSegment)(String(id))}`, {
        method: 'DELETE',
        auth: true,
    });
}
exports.deleteNote = deleteNote;
async function fetchNoteDetail(id) {
    const res = await (0, api_1.request)(`/notes/${(0, encode_path_segment_1.encodePathSegment)(String(id))}`, {
        auth: true,
    });
    return normalizeDetail((res.data || {}));
}
exports.fetchNoteDetail = fetchNoteDetail;
async function fetchNoteDynasties() {
    const res = await (0, api_1.request)('/notes/dynasties', { auth: true });
    return (res.data.items || []).map((x) => normalizeDynasty(x));
}
exports.fetchNoteDynasties = fetchNoteDynasties;
async function fetchNotesByDynasty(dynastyId, page = 1, pageSize = 20) {
    var _a;
    const res = await (0, api_1.request)(`/notes?dynastyId=${encodeURIComponent(dynastyId)}&page=${page}&pageSize=${pageSize}`, { auth: true });
    const items = (res.data.items || []).map((x) => normalizeListItem(x));
    return { items, total: (_a = res.data.total) !== null && _a !== void 0 ? _a : items.length };
}
exports.fetchNotesByDynasty = fetchNotesByDynasty;
async function fetchNoteHighlights(boxId, sourceType, sourceRefId) {
    if (!(0, api_1.hasToken)() || !boxId)
        return [];
    const ref = sourceRefId && sourceRefId > 0 ? `&sourceRefId=${sourceRefId}` : '';
    const res = await (0, api_1.request)(`/notes/highlights?boxId=${encodeURIComponent(boxId)}&sourceType=${encodeURIComponent(sourceType)}${ref}`, { auth: true, softAuth: true });
    return (res.data || []).map((x) => normalizeHighlight(x));
}
exports.fetchNoteHighlights = fetchNoteHighlights;
function resolveNoteSourceNav(detail) {
    const sourceType = detail.sourceType;
    const noteId = detail.id;
    if (sourceType === 'box_detail_selection') {
        const boxId = String(detail.boxId || '').trim();
        if (!boxId)
            return { error: '缺少史略信息，无法跳转' };
        return {
            path: router_1.ROUTES.boxDetail,
            query: {
                boxId,
                title: String(detail.boxTitle || '').trim(),
                noteId,
                tab: 'content',
            },
        };
    }
    if (sourceType === 'critique_detail_selection') {
        const critiqueId = toNullableNumber(detail.sourceRefId);
        if (!critiqueId)
            return { error: '缺少评述信息，无法跳转' };
        return {
            path: router_1.ROUTES.critiqueDetail,
            query: { critiqueId, noteId },
        };
    }
    if (sourceType === 'relic_detail_selection') {
        const relicId = toNullableNumber(detail.sourceRefId);
        if (!relicId)
            return { error: '缺少见证信息，无法跳转' };
        return {
            path: router_1.ROUTES.relicDetail,
            query: { relicId, noteId },
        };
    }
    if (sourceType === 'relation_graph_selection') {
        const boxId = String(detail.boxId || '').trim();
        if (!boxId)
            return { error: '缺少史略信息，无法跳转' };
        return {
            path: router_1.ROUTES.boxDetail,
            query: {
                boxId,
                title: String(detail.boxTitle || '').trim(),
                noteId,
                tab: 'relations',
                highlightName: String(detail.selectedText || '').trim(),
            },
        };
    }
    return { error: '未知来源，无法跳转' };
}
exports.resolveNoteSourceNav = resolveNoteSourceNav;
function navigateToNoteSource(detail) {
    const nav = resolveNoteSourceNav(detail);
    if ('error' in nav) {
        wx.showToast({ title: nav.error, icon: 'none' });
        return false;
    }
    (0, router_1.navigateTo)(nav.path, nav.query);
    return true;
}
exports.navigateToNoteSource = navigateToNoteSource;
