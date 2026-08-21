"use strict";
/** 史略详情页内搜索历史（按 boxId 隔离） */
Object.defineProperty(exports, "__esModule", { value: true });
exports.clearBoxDetailSearchHistory = exports.removeBoxDetailSearchHistory = exports.addBoxDetailSearchHistory = exports.readBoxDetailSearchHistory = void 0;
const PREFIX = 'boxDetailSearchHistory:';
const MAX = 15;
function storageKey(boxId) {
    return `${PREFIX}${String(boxId || '').trim()}`;
}
function readBoxDetailSearchHistory(boxId) {
    const id = String(boxId || '').trim();
    if (!id)
        return [];
    try {
        const raw = wx.getStorageSync(storageKey(id));
        if (!Array.isArray(raw))
            return [];
        return raw.filter((x) => typeof x === 'string' && x.trim()).map((x) => x.trim());
    }
    catch {
        return [];
    }
}
exports.readBoxDetailSearchHistory = readBoxDetailSearchHistory;
function addBoxDetailSearchHistory(boxId, keyword) {
    const id = String(boxId || '').trim();
    const k = String(keyword || '').trim().slice(0, 50);
    if (!id || !k)
        return;
    const list = readBoxDetailSearchHistory(id).filter((x) => x !== k);
    list.unshift(k);
    try {
        wx.setStorageSync(storageKey(id), list.slice(0, MAX));
    }
    catch {
        // ignore
    }
}
exports.addBoxDetailSearchHistory = addBoxDetailSearchHistory;
function removeBoxDetailSearchHistory(boxId, keyword) {
    const id = String(boxId || '').trim();
    const k = String(keyword || '').trim();
    if (!id || !k)
        return;
    try {
        wx.setStorageSync(storageKey(id), readBoxDetailSearchHistory(id).filter((x) => x !== k));
    }
    catch {
        // ignore
    }
}
exports.removeBoxDetailSearchHistory = removeBoxDetailSearchHistory;
/** 清空本篇全部搜索历史 */
function clearBoxDetailSearchHistory(boxId) {
    const id = String(boxId || '').trim();
    if (!id)
        return;
    try {
        wx.removeStorageSync(storageKey(id));
    }
    catch {
        try {
            wx.setStorageSync(storageKey(id), []);
        }
        catch {
            // ignore
        }
    }
}
exports.clearBoxDetailSearchHistory = clearBoxDetailSearchHistory;
