"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.computeUnitFavoriteState = exports.setBoxesFavorited = exports.isBoxFavorited = exports.unfavoriteBox = exports.favoriteBox = exports.fetchFavoritedBoxIdSet = exports.promptLoginForFavorite = void 0;
const api_1 = require("./api");
const encode_path_segment_1 = require("./encode-path-segment");
const router_1 = require("./router");
function promptLoginForFavorite() {
    wx.showModal({
        title: '需要登录',
        content: '登录后可收藏，并在「我的收藏」中查看。',
        confirmText: '去登录',
        success: (r) => {
            if (r.confirm)
                (0, router_1.navigateTo)(router_1.ROUTES.login);
        },
    });
}
exports.promptLoginForFavorite = promptLoginForFavorite;
async function fetchFavoritedBoxIdSet() {
    var _a;
    if (!(0, api_1.hasToken)())
        return new Set();
    const set = new Set();
    try {
        let page = 1;
        const pageSize = 50;
        while (true) {
            const res = await (0, api_1.request)(`/favorites/boxes?page=${page}&pageSize=${pageSize}`, { auth: true });
            const items = res.data.items || [];
            for (const x of items) {
                if (x.boxId)
                    set.add(x.boxId);
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
exports.fetchFavoritedBoxIdSet = fetchFavoritedBoxIdSet;
async function favoriteBox(boxId) {
    await (0, api_1.request)(`/favorites/boxes/${(0, encode_path_segment_1.encodePathSegment)(boxId)}`, { method: 'POST', auth: true });
}
exports.favoriteBox = favoriteBox;
async function unfavoriteBox(boxId) {
    await (0, api_1.request)(`/favorites/boxes/${(0, encode_path_segment_1.encodePathSegment)(boxId)}`, { method: 'DELETE', auth: true });
}
exports.unfavoriteBox = unfavoriteBox;
async function isBoxFavorited(boxId) {
    const set = await fetchFavoritedBoxIdSet();
    return set.has(boxId);
}
exports.isBoxFavorited = isBoxFavorited;
/** 批量收藏 / 取消（遗留接口，朝代收藏请使用 favorite-unit） */
async function setBoxesFavorited(boxIds, favorited) {
    const ids = [...new Set(boxIds.filter(Boolean))];
    if (!ids.length)
        return;
    if (favorited) {
        await Promise.all(ids.map((id) => favoriteBox(id)));
    }
    else {
        await Promise.all(ids.map((id) => unfavoriteBox(id)));
    }
}
exports.setBoxesFavorited = setBoxesFavorited;
function computeUnitFavoriteState(boxIds, favorited) {
    const ids = boxIds.filter(Boolean);
    if (!ids.length) {
        return { allFavorited: false, anyFavorited: false, favoritedCount: 0 };
    }
    let favoritedCount = 0;
    for (const id of ids) {
        if (favorited.has(id))
            favoritedCount += 1;
    }
    return {
        allFavorited: favoritedCount === ids.length,
        anyFavorited: favoritedCount > 0,
        favoritedCount,
    };
}
exports.computeUnitFavoriteState = computeUnitFavoriteState;
