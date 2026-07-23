"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const api_1 = require("../../native-utils/api");
const favorite_display_1 = require("../../native-utils/favorite-display");
const nav_metrics_1 = require("../../native-utils/nav-metrics");
const router_1 = require("../../native-utils/router");
Page({
    data: {
        hasToken: false,
        loaded: false,
        total: 0,
        summaryText: '',
        items: [],
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
    onShow() {
        const ok = (0, api_1.hasToken)();
        this.setData({
            hasToken: ok,
            loaded: false,
            items: [],
            total: 0,
            summaryText: '',
        });
        if (ok)
            void this.load();
    },
    goLogin() {
        (0, router_1.navigateTo)(router_1.ROUTES.login);
    },
    async load() {
        var _a;
        try {
            const all = [];
            let page = 1;
            const pageSize = 50;
            let total = 0;
            while (true) {
                const res = await (0, api_1.request)(`/footprints/boxes?page=${page}&pageSize=${pageSize}`, { auth: true });
                const batch = res.data.items || [];
                all.push(...batch);
                total = (_a = res.data.total) !== null && _a !== void 0 ? _a : all.length;
                if (batch.length < pageSize || all.length >= total)
                    break;
                page += 1;
            }
            const items = all.map(favorite_display_1.toFootprintCardView);
            this.setData({
                items,
                total,
                summaryText: total > 0 ? `共 ${total} 条 · 按访问时间由近及远` : '',
                loaded: true,
            });
        }
        catch {
            this.setData({ items: [], total: 0, summaryText: '', loaded: true });
        }
    },
    go(e) {
        const id = e.currentTarget.dataset.id;
        if (!id)
            return;
        (0, router_1.navigateTo)(router_1.ROUTES.boxDetail, { boxId: id });
    },
});
