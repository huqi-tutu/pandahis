"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.isUnitFavorited = exports.unfavoriteUnit = exports.favoriteUnit = exports.fetchFavoritedUnitIdSet = exports.promptLoginForUnitFavorite = void 0;
const api_1 = require("./api");
const encode_path_segment_1 = require("./encode-path-segment");
const router_1 = require("./router");
function promptLoginForUnitFavorite() {
    wx.showModal({
        title: '需要登录',
        content: '登录后可收藏朝代，并在「我的收藏」中查看。',
        confirmText: '去登录',
        success: (r) => {
            if (r.confirm)
                (0, router_1.navigateTo)(router_1.ROUTES.login);
        },
    });
}
exports.promptLoginForUnitFavorite = promptLoginForUnitFavorite;
async function fetchFavoritedUnitIdSet() {
    var _a;
    if (!(0, api_1.hasToken)())
        return new Set();
    const set = new Set();
    try {
        let page = 1;
        const pageSize = 50;
        while (true) {
            const res = await (0, api_1.request)(`/favorites/units?page=${page}&pageSize=${pageSize}`, { auth: true });
            const items = res.data.items || [];
            for (const x of items) {
                if (x.unitId)
                    set.add(x.unitId);
            }
            const total = (_a = res.data.total) !== null && _a !== void 0 ? _a : items.length;
            if (items.length < pageSize || set.size >= total)
                break;
            page += 1;
        }
    }
    catch {
        return new Set();
    }
    return set;
}
exports.fetchFavoritedUnitIdSet = fetchFavoritedUnitIdSet;
async function favoriteUnit(unitId) {
    await (0, api_1.request)(`/favorites/units/${(0, encode_path_segment_1.encodePathSegment)(unitId)}`, { method: 'POST', auth: true });
}
exports.favoriteUnit = favoriteUnit;
async function unfavoriteUnit(unitId) {
    await (0, api_1.request)(`/favorites/units/${(0, encode_path_segment_1.encodePathSegment)(unitId)}`, { method: 'DELETE', auth: true });
}
exports.unfavoriteUnit = unfavoriteUnit;
async function isUnitFavorited(unitId) {
    const set = await fetchFavoritedUnitIdSet();
    return set.has(unitId);
}
exports.isUnitFavorited = isUnitFavorited;
