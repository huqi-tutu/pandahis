"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.parseCivilizationFromCrumb = exports.requireLoginForCorrection = exports.fetchCorrectionDetail = exports.fetchCorrections = exports.submitCorrection = exports.promptLoginForCorrection = exports.formatCorrectionTime = exports.correctionSourceLabel = exports.correctionStatusLabel = exports.CORRECTION_SOURCE_LABEL = exports.CORRECTION_STATUS_LABEL = void 0;
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
function normalizeDetail(raw) {
    var _a, _b, _c, _d, _e, _f, _g, _h, _j, _k, _l, _m, _o, _p, _q, _r, _s, _t, _u, _v;
    return {
        id: Number((_b = (_a = raw.id) !== null && _a !== void 0 ? _a : raw['id']) !== null && _b !== void 0 ? _b : 0),
        boxId: String((_d = (_c = raw.boxId) !== null && _c !== void 0 ? _c : raw['box_id']) !== null && _d !== void 0 ? _d : ''),
        boxTitle: String((_f = (_e = raw.boxTitle) !== null && _e !== void 0 ? _e : raw['box_title']) !== null && _f !== void 0 ? _f : ''),
        unitId: ((_h = (_g = raw.unitId) !== null && _g !== void 0 ? _g : raw['unit_id']) !== null && _h !== void 0 ? _h : null),
        civilizationName: String((_k = (_j = raw.civilizationName) !== null && _j !== void 0 ? _j : raw['civilization_name']) !== null && _k !== void 0 ? _k : ''),
        dynastyName: String((_m = (_l = raw.dynastyName) !== null && _l !== void 0 ? _l : raw['dynasty_name']) !== null && _m !== void 0 ? _m : ''),
        sourceType: String((_p = (_o = raw.sourceType) !== null && _o !== void 0 ? _o : raw['source_type']) !== null && _p !== void 0 ? _p : ''),
        selectedText: ((_r = (_q = raw.selectedText) !== null && _q !== void 0 ? _q : raw['selected_text']) !== null && _r !== void 0 ? _r : null),
        reason: ((_s = raw.reason) !== null && _s !== void 0 ? _s : null),
        status: String((_t = raw.status) !== null && _t !== void 0 ? _t : 'pending'),
        createdAt: String((_v = (_u = raw.createdAt) !== null && _u !== void 0 ? _u : raw['created_at']) !== null && _v !== void 0 ? _v : ''),
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
