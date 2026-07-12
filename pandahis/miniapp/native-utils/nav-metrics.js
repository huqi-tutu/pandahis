"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.getNavBarMetrics = void 0;
function getNavBarMetrics() {
    return new Promise((resolve, reject) => {
        const rect = wx.getMenuButtonBoundingClientRect();
        wx.getSystemInfo({
            success: (res) => {
                const statusBarHeight = res.statusBarHeight || 0;
                const menuGap = Math.max(0, rect.top - statusBarHeight);
                const navContentHeight = menuGap * 2 + rect.height;
                resolve({
                    totalHeight: statusBarHeight + navContentHeight,
                    statusBarHeight,
                    paddingLeft: Math.max(0, res.windowWidth - rect.right),
                    paddingRight: Math.max(0, res.windowWidth - rect.left),
                });
            },
            fail: reject,
        });
    });
}
exports.getNavBarMetrics = getNavBarMetrics;
