"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const nav_metrics_1 = require("../../native-utils/nav-metrics");
Page({
    data: {
        name: '',
        museum: '',
        detail: '',
        imageUrl: '',
        pageTopPadPx: 88,
    },
    onLoad(query) {
        try {
            this.setData({ pageTopPadPx: (0, nav_metrics_1.computePageTopPadPx)() });
        }
        catch {
            this.setData({ pageTopPadPx: 88 });
        }
        this.setData({
            name: decodeURIComponent(query.name || ''),
            museum: decodeURIComponent(query.museum || ''),
            detail: decodeURIComponent(query.detail || ''),
            imageUrl: decodeURIComponent(query.imageUrl || ''),
        });
    },
});
