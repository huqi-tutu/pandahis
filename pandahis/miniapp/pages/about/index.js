"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const brand_assets_1 = require("../../native-utils/brand-assets");
const nav_metrics_1 = require("../../native-utils/nav-metrics");
Page({
    data: {
        brandLogoUrl: brand_assets_1.BRAND_LOGO_URL,
        aboutNavTitle: `关于${brand_assets_1.APP_DISPLAY_NAME}`,
        introLead: `${brand_assets_1.APP_DISPLAY_NAME}以时空坐标组织史料，帮助你在朝代、人物与事件之间建立可浏览、可深读的知识网络。`,
        version: '0.1.0',
        pageTopPadPx: 88,
    },
    onLoad() {
        try {
            this.setData({ pageTopPadPx: (0, nav_metrics_1.computePageTopPadPx)() });
        }
        catch {
            this.setData({ pageTopPadPx: 88 });
        }
    },
});
