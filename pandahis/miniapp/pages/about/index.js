"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const brand_assets_1 = require("../../native-utils/brand-assets");
const nav_metrics_1 = require("../../native-utils/nav-metrics");
Page({
    data: {
        brandLogoUrl: brand_assets_1.BRAND_LOGO_URL,
        aboutNavTitle: `关于${brand_assets_1.APP_DISPLAY_NAME}`,
        introParas: [
            '旧史分卷，万古成隅。\n典籍各自封章，岁月各自沉埋。\n世人观史，多循笔墨既定的轨迹，\n见片段，不见山河相连。',
            '时络，以时空为经，人事为纬。\n破史籍之孤岛，织古今之隐脉。\n不困于一书一卷的叙事边界，\n不囿于一朝一代的线性光阴。',
            '让散落的兴亡彼此照映，\n让断续的人事自有归牵。\n于字缝拾因果，\n于脉络见千秋。',
            '所谓读史，\n不再是顺文承接的浏览，\n而是一场纵横往来的溯源与相逢。',
        ],
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
