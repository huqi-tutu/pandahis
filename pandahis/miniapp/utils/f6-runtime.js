"use strict";
/**
 * @antv/f6-wx MIT — 小程序 npm 兼容加载（require 无 .default）
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.readCanvasMetrics = exports.getF6Runtime = void 0;
function pickF6Module(mod) {
    var _a;
    const m = mod;
    if ((m === null || m === void 0 ? void 0 : m.Graph) && typeof m.registerLayout === 'function')
        return m;
    if (((_a = m === null || m === void 0 ? void 0 : m.default) === null || _a === void 0 ? void 0 : _a.Graph) && typeof m.default.registerLayout === 'function')
        return m.default;
    throw new Error('@antv/f6-wx 未正确加载，请在微信开发者工具执行「工具 → 构建 NPM」');
}
/** layout 扩展导出为构造函数，与 F6 主包不同 */
function pickLayoutModule(mod) {
    if (typeof mod === 'function')
        return mod;
    const m = mod;
    if (typeof (m === null || m === void 0 ? void 0 : m.default) === 'function')
        return m.default;
    return mod;
}
let cached = null;
/** 延迟加载 F6，避免首页启动时因 npm 导出差异崩溃 */
function getF6Runtime() {
    if (cached)
        return cached;
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const f6Mod = require('@antv/f6-wx');
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const radialMod = require('@antv/f6-wx/extends/layout/radialLayout');
    const F6 = pickF6Module(f6Mod);
    const radialLayout = pickLayoutModule(radialMod);
    F6.registerLayout('radial', radialLayout);
    cached = F6;
    return F6;
}
exports.getF6Runtime = getF6Runtime;
function readCanvasMetrics() {
    try {
        const win = wx.getWindowInfo();
        return {
            windowWidth: win.windowWidth || 375,
            pixelRatio: win.pixelRatio || 2,
        };
    }
    catch {
        const sys = wx.getSystemInfoSync();
        return {
            windowWidth: sys.windowWidth || 375,
            pixelRatio: sys.pixelRatio || 2,
        };
    }
}
exports.readCanvasMetrics = readCanvasMetrics;
