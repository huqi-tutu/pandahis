"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.removeLocalSearchHistory = exports.addLocalSearchHistory = exports.readLocalSearchHistory = void 0;
const KEY = 'searchHistoryLocal';
const MAX = 20;
function readLocalSearchHistory() {
    try {
        const raw = wx.getStorageSync(KEY);
        if (!Array.isArray(raw))
            return [];
        return raw.filter((x) => typeof x === 'string' && x.trim()).map((x) => x.trim());
    }
    catch {
        return [];
    }
}
exports.readLocalSearchHistory = readLocalSearchHistory;
function addLocalSearchHistory(keyword) {
    const k = keyword.trim();
    if (!k)
        return;
    const list = readLocalSearchHistory().filter((x) => x !== k);
    list.unshift(k);
    try {
        wx.setStorageSync(KEY, list.slice(0, MAX));
    }
    catch {
        // ignore
    }
}
exports.addLocalSearchHistory = addLocalSearchHistory;
function removeLocalSearchHistory(keyword) {
    const k = keyword.trim();
    if (!k)
        return;
    try {
        wx.setStorageSync(KEY, readLocalSearchHistory().filter((x) => x !== k));
    }
    catch {
        // ignore
    }
}
exports.removeLocalSearchHistory = removeLocalSearchHistory;
