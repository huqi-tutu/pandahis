"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const brand_assets_1 = require("../../native-utils/brand-assets");
const nav_metrics_1 = require("../../native-utils/nav-metrics");
Page({
    data: {
        brandLogoUrl: brand_assets_1.BRAND_LOGO_URL,
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
