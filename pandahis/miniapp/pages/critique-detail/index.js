"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const nav_metrics_1 = require("../../native-utils/nav-metrics");
Page({
    data: {
        title: '',
        author: '',
        book: '',
        era: '',
        body: '',
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
            title: decodeURIComponent(query.title || ''),
            author: decodeURIComponent(query.author || ''),
            book: decodeURIComponent(query.book || ''),
            era: decodeURIComponent(query.era || ''),
            body: decodeURIComponent(query.body || ''),
        });
    },
});
