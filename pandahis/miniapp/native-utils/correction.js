"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.navigateToCorrectionSource = exports.resolveCorrectionSourceNav = exports.parseCivilizationFromCrumb = exports.requireLoginForCorrection = exports.fetchCorrectionDetail = exports.fetchCorrections = exports.submitCorrection = exports.promptLoginForCorrection = exports.formatCorrectionTime = exports.correctionSourceLabel = exports.correctionStatusLabel = exports.CORRECTION_SOURCE_LABEL = exports.CORRECTION_STATUS_LABEL = void 0;
const api_1 = require("./api");
const encode_path_segment_1 = require("./encode-path-segment");
const router_1 = require("./router");
exports.CORRECTION_STATUS_LABEL = {
    pending: '待处理',
    reviewed: '已审阅',
    resolved: '已解决',
};
exports.CORRECTION_SOURCE_LABEL = {
    dynasty_canvas: '朝代详情页',
    box_detail_selection: '史略详情页',
    box_original_selection: '母本原文',
    critique_detail_selection: '评述',
    relic_detail_selection: '见证',
    relation_graph_selection: '关系图谱页',
};
function correctionStatusLabel(status) {
    return exports.CORRECTION_STATUS_LABEL[status] || status || '待处理';
}
exports.correctionStatusLabel = correctionStatusLabel;
function correctionSourceLabel(sourceType) {
    return exports.CORRECTION_SOURCE_LABEL[sourceType] || sourceType || '';
}
exports.correctionSourceLabel = correctionSourceLabel;
function formatCorrectionTime(iso) {
    if (!iso)
        return '';
    const d = new Date(iso);
    if (Number.isNaN(d.getTime()))
        return iso.replace('T', ' ').slice(0, 19);
    const pad = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}
exports.formatCorrectionTime = formatCorrectionTime;
function toNullableNumber(raw) {
    if (raw === undefined || raw === null || raw === '')
        return null;
    const n = Number(raw);
    return Number.isFinite(n) && n > 0 ? n : null;
}
function normalizeDetail(raw) {
    var _a, _b, _c, _d, _e, _f, _g, _h, _j, _k, _l, _m, _o, _p, _q, _r, _s, _t, _u, _v, _w;
    return {
        id: Number((_b = (_a = raw.id) !== null && _a !== void 0 ? _a : raw['id']) !== null && _b !== void 0 ? _b : 0),
        boxId: String((_d = (_c = raw.boxId) !== null && _c !== void 0 ? _c : raw['box_id']) !== null && _d !== void 0 ? _d : ''),
        boxTitle: String((_f = (_e = raw.boxTitle) !== null && _e !== void 0 ? _e : raw['box_title']) !== null && _f !== void 0 ? _f : ''),
        unitId: ((_h = (_g = raw.unitId) !== null && _g !== void 0 ? _g : raw['unit_id']) !== null && _h !== void 0 ? _h : null),
        civilizationName: String((_k = (_j = raw.civilizationName) !== null && _j !== void 0 ? _j : raw['civilization_name']) !== null && _k !== void 0 ? _k : ''),
        dynastyName: String((_m = (_l = raw.dynastyName) !== null && _l !== void 0 ? _l : raw['dynasty_name']) !== null && _m !== void 0 ? _m : ''),
        sourceType: String((_p = (_o = raw.sourceType) !== null && _o !== void 0 ? _o : raw['source_type']) !== null && _p !== void 0 ? _p : ''),
        sourceRefId: toNullableNumber((_q = raw.sourceRefId) !== null && _q !== void 0 ? _q : raw['source_ref_id']),
        selectedText: ((_s = (_r = raw.selectedText) !== null && _r !== void 0 ? _r : raw['selected_text']) !== null && _s !== void 0 ? _s : null),
        reason: ((_t = raw.reason) !== null && _t !== void 0 ? _t : null),
        status: String((_u = raw.status) !== null && _u !== void 0 ? _u : 'pending'),
        createdAt: String((_w = (_v = raw.createdAt) !== null && _v !== void 0 ? _v : raw['created_at']) !== null && _w !== void 0 ? _w : ''),
    };
}
function normalizeListItem(raw) {
    var _a, _b, _c, _d, _e, _f, _g, _h, _j;
    return {
        id: Number((_b = (_a = raw.id) !== null && _a !== void 0 ? _a : raw['id']) !== null && _b !== void 0 ? _b : 0),
        boxId: String((_d = (_c = raw.boxId) !== null && _c !== void 0 ? _c : raw['box_id']) !== null && _d !== void 0 ? _d : ''),
        boxTitle: String((_f = (_e = raw.boxTitle) !== null && _e !== void 0 ? _e : raw['box_title']) !== null && _f !== void 0 ? _f : ''),
        status: String((_g = raw.status) !== null && _g !== void 0 ? _g : 'pending'),
        createdAt: String((_j = (_h = raw.createdAt) !== null && _h !== void 0 ? _h : raw['created_at']) !== null && _j !== void 0 ? _j : ''),
    };
}
function promptLoginForCorrection() {
    wx.showModal({
        title: '需要登录',
        content: '登录后可提交纠错，并在「我的纠错」中查看记录。',
        confirmText: '去登录',
        success: (r) => {
            if (r.confirm)
                (0, router_1.navigateTo)(router_1.ROUTES.login);
        },
    });
}
exports.promptLoginForCorrection = promptLoginForCorrection;
async function submitCorrection(payload) {
    const res = await (0, api_1.request)('/corrections', {
        method: 'POST',
        auth: true,
        data: {
            boxId: payload.boxId,
            sourceType: payload.sourceType,
            reason: payload.reason || undefined,
            selectedText: payload.selectedText || undefined,
            sourceRefId: payload.sourceRefId || undefined,
        },
    });
    return normalizeDetail((res.data || {}));
}
exports.submitCorrection = submitCorrection;
async function fetchCorrections(page = 1, pageSize = 20) {
    var _a;
    const res = await (0, api_1.request)(`/corrections?page=${page}&pageSize=${pageSize}`, { auth: true });
    const items = (res.data.items || []).map((x) => normalizeListItem(x));
    return { items, total: (_a = res.data.total) !== null && _a !== void 0 ? _a : items.length };
}
exports.fetchCorrections = fetchCorrections;
async function fetchCorrectionDetail(id) {
    const res = await (0, api_1.request)(`/corrections/${(0, encode_path_segment_1.encodePathSegment)(String(id))}`, {
        auth: true,
    });
    return normalizeDetail((res.data || {}));
}
exports.fetchCorrectionDetail = fetchCorrectionDetail;
function requireLoginForCorrection(action) {
    if (!(0, api_1.hasToken)()) {
        promptLoginForCorrection();
        return;
    }
    action();
}
exports.requireLoginForCorrection = requireLoginForCorrection;
function parseCivilizationFromCrumb(crumbText) {
    const text = (crumbText || '').trim();
    if (!text)
        return '';
    const idx = text.indexOf(' · ');
    return idx >= 0 ? text.slice(0, idx).trim() : text;
}
exports.parseCivilizationFromCrumb = parseCivilizationFromCrumb;
/** 解析纠错来源对应的跳转目标；无法跳转时返回 error */
function resolveCorrectionSourceNav(detail) {
    const sourceType = detail.sourceType;
    if (sourceType === 'dynasty_canvas') {
        const unitId = String(detail.unitId || '').trim();
        if (!unitId)
            return { error: '缺少朝代信息，无法跳转' };
        return {
            path: router_1.ROUTES.dynastyDetail,
            query: {
                unitId,
                dynasty: String(detail.dynastyName || '').trim(),
            },
        };
    }
    if (sourceType === 'box_detail_selection') {
        const boxId = String(detail.boxId || '').trim();
        if (!boxId)
            return { error: '缺少史略信息，无法跳转' };
        return {
            path: router_1.ROUTES.boxDetail,
            query: {
                boxId,
                title: String(detail.boxTitle || '').trim(),
            },
        };
    }
    if (sourceType === 'box_original_selection') {
        const boxId = String(detail.boxId || '').trim();
        if (!boxId)
            return { error: '缺少史略信息，无法跳转' };
        return {
            path: router_1.ROUTES.boxDetail,
            query: {
                boxId,
                title: String(detail.boxTitle || '').trim(),
                openOriginal: '1',
            },
        };
    }
    if (sourceType === 'critique_detail_selection') {
        const critiqueId = toNullableNumber(detail.sourceRefId);
        if (!critiqueId)
            return { error: '缺少评述信息，无法跳转' };
        return {
            path: router_1.ROUTES.critiqueDetail,
            query: { critiqueId },
        };
    }
    if (sourceType === 'relic_detail_selection') {
        const relicId = toNullableNumber(detail.sourceRefId);
        if (!relicId)
            return { error: '缺少见证信息，无法跳转' };
        return {
            path: router_1.ROUTES.relicDetail,
            query: { relicId },
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
            },
        };
    }
    return { error: '未知来源，无法跳转' };
}
exports.resolveCorrectionSourceNav = resolveCorrectionSourceNav;
function navigateToCorrectionSource(detail) {
    const nav = resolveCorrectionSourceNav(detail);
    if ('error' in nav) {
        wx.showToast({ title: nav.error, icon: 'none' });
        return false;
    }
    (0, router_1.navigateTo)(nav.path, nav.query);
    return true;
}
exports.navigateToCorrectionSource = navigateToCorrectionSource;
