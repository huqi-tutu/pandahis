"use strict";
/** 选文操作条锚点自适应（避免贴边被裁切） */
Object.defineProperty(exports, "__esModule", { value: true });
exports.resolveSelectionBarAnchor = void 0;
function rpxToPx(rpx, windowWidth) {
    return (windowWidth / 750) * rpx;
}
/**
 * 根据选区矩形计算操作条锚点。
 * - left/top 为 CSS 定位点；组件用 transform 相对该点放置
 * - placement=above：条在选区上方（默认）
 * - placement=below：条在选区下方（顶部空间不够时）
 */
function resolveSelectionBarAnchor(rect, fallback, options) {
    var _a;
    const placementFallback = fallback.placement || 'above';
    if (!rect || rect.left == null || rect.top == null) {
        return { left: fallback.left, top: fallback.top, placement: placementFallback };
    }
    const sys = wx.getSystemInfoSync();
    const ww = sys.windowWidth || 375;
    const wh = sys.windowHeight || 667;
    const statusBar = sys.statusBarHeight || 20;
    // 预留自定义导航 + tab 大致高度，避免盖住标题栏
    const safeTop = statusBar + rpxToPx(88 + 72, ww);
    const safeBottom = rpxToPx(48, ww);
    const edge = rpxToPx(16, ww);
    // 与 text-selection-bar.scss 尺寸对齐：N×88 + gap×(N-1) + padding
    const buttonCount = Math.max(1, Math.floor((_a = options === null || options === void 0 ? void 0 : options.buttonCount) !== null && _a !== void 0 ? _a : 4));
    const barW = rpxToPx(88 * buttonCount + 14 * Math.max(buttonCount - 1, 0) + 14 * 2, ww);
    const barH = rpxToPx(16 + 14 + 40 + 8 + 28, ww);
    const gap = rpxToPx(14, ww);
    const selLeft = Number(rect.left) || 0;
    const selTop = Number(rect.top) || 0;
    const selW = Number(rect.width) || 0;
    const selH = Number(rect.height) || 0;
    const selBottom = selTop + selH;
    let left = selLeft + selW / 2;
    const half = barW / 2;
    left = Math.max(edge + half, Math.min(ww - edge - half, left));
    const need = barH + gap;
    const spaceAbove = selTop - safeTop;
    const spaceBelow = wh - safeBottom - selBottom;
    let placement = 'above';
    let top = selTop;
    if (spaceAbove >= need) {
        placement = 'above';
        top = selTop;
    }
    else if (spaceBelow >= need) {
        placement = 'below';
        top = selBottom;
    }
    else if (spaceBelow > spaceAbove) {
        placement = 'below';
        top = Math.min(selBottom, wh - safeBottom - need);
    }
    else {
        placement = 'above';
        top = Math.max(selTop, safeTop + need);
    }
    return { left, top, placement };
}
exports.resolveSelectionBarAnchor = resolveSelectionBarAnchor;
