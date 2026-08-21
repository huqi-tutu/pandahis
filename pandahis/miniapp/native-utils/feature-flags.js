"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.isHuaxiaUnitId = exports.isHuaxiaCivSlug = exports.toastCivLocked = exports.loadFeatureFlags = exports.isCivSwitchEnabled = exports.getFeatureFlags = exports.TOAST_CIV_LOCKED = void 0;
const api_1 = require("./api");
const runtime_env_1 = require("./runtime-env");
/** trial/release 请求失败时的兜底（develop 版在前端也会强制 true） */
const DEFAULT_FLAGS = { civSwitchEnabled: false };
exports.TOAST_CIV_LOCKED = '即将上线，敬请期待';
function getFeatureFlags() {
    var _a;
    try {
        const app = getApp();
        return ((_a = app === null || app === void 0 ? void 0 : app.globalData) === null || _a === void 0 ? void 0 : _a.featureFlags) || DEFAULT_FLAGS;
    }
    catch {
        return DEFAULT_FLAGS;
    }
}
exports.getFeatureFlags = getFeatureFlags;
function isCivSwitchEnabled() {
    if ((0, runtime_env_1.isDevelopEnv)())
        return true;
    return getFeatureFlags().civSwitchEnabled !== false;
}
exports.isCivSwitchEnabled = isCivSwitchEnabled;
async function loadFeatureFlags() {
    try {
        const res = await (0, api_1.request)('/config/features');
        const raw = res.data || {};
        const normalized = {
            civSwitchEnabled: raw.civSwitchEnabled !== false,
        };
        try {
            const app = getApp();
            if (app) {
                app.globalData = app.globalData || {};
                app.globalData.featureFlags = normalized;
            }
        }
        catch {
            // ignore
        }
        return normalized;
    }
    catch {
        return DEFAULT_FLAGS;
    }
}
exports.loadFeatureFlags = loadFeatureFlags;
function toastCivLocked() {
    wx.showToast({ title: exports.TOAST_CIV_LOCKED, icon: 'none' });
}
exports.toastCivLocked = toastCivLocked;
function isHuaxiaCivSlug(slug) {
    return String(slug || '').trim() === 'huaxia';
}
exports.isHuaxiaCivSlug = isHuaxiaCivSlug;
function isHuaxiaUnitId(unitId) {
    const id = String(unitId || '').trim().toUpperCase();
    if (!id)
        return true;
    return id.startsWith('CD_HX_') || id === 'CD_HX';
}
exports.isHuaxiaUnitId = isHuaxiaUnitId;
