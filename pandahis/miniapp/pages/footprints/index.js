"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const api_1 = require("../../native-utils/api");
const date_grouped_list_1 = require("../../native-utils/date-grouped-list");
const favorite_display_1 = require("../../native-utils/favorite-display");
const nav_metrics_1 = require("../../native-utils/nav-metrics");
const router_1 = require("../../native-utils/router");
const PAGE_SIZE = 50;
Page({
    data: {
        hasToken: false,
        loaded: false,
        loadingMore: false,
        hasMore: false,
        loadFinished: false,
        total: 0,
        page: 0,
        summaryText: '',
        groups: [],
        pageTopPadPx: 88,
    },
    _loading: false,
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
        if (!ok) {
            this.setData({
                hasToken: false,
                loaded: true,
                loadingMore: false,
                hasMore: false,
                loadFinished: false,
                total: 0,
                page: 0,
                summaryText: '',
                groups: [],
            });
            return;
        }
        const silent = this.data.groups.length > 0;
        this.setData({ hasToken: true });
        void this.load({ reset: true, silent });
    },
    onReachBottom() {
        if (!this.data.hasToken || !this.data.hasMore || this.data.loadingMore || this._loading)
            return;
        void this.load({ reset: false, silent: true });
    },
    goLogin() {
        (0, router_1.navigateTo)(router_1.ROUTES.login);
    },
    toRows(items) {
        return items.map((item) => {
            const view = (0, favorite_display_1.toFootprintCardView)(item);
            return {
                ...view,
                timeLabel: (0, date_grouped_list_1.formatClockTime)(item.lastViewedAt) || view.timeLabel,
            };
        });
    },
    async load(opts) {
        var _a;
        if (this._loading)
            return;
        this._loading = true;
        const reset = opts.reset;
        const silent = Boolean(opts.silent);
        const nextPage = reset ? 1 : this.data.page + 1;
        if (!silent) {
            this.setData(reset ? { loaded: false } : { loadingMore: true });
        }
        else if (!reset) {
            this.setData({ loadingMore: true });
        }
        try {
            const res = await (0, api_1.request)(`/footprints/boxes?page=${nextPage}&pageSize=${PAGE_SIZE}`, { auth: true });
            const batch = this.toRows(res.data.items || []);
            const total = (_a = res.data.total) !== null && _a !== void 0 ? _a : 0;
            const prevGroups = this.data.groups;
            const groups = reset
                ? (0, date_grouped_list_1.groupByDateKey)(batch, (item) => item.lastViewedAt)
                : (0, date_grouped_list_1.appendGroupedItems)(prevGroups, batch, (item) => item.lastViewedAt, (item) => item.boxId);
            const loadedCount = groups.reduce((n, g) => n + g.items.length, 0);
            const hasMore = batch.length >= PAGE_SIZE && loadedCount < total;
            this.setData({
                groups,
                total,
                page: nextPage,
                hasMore,
                loadFinished: !hasMore && loadedCount > 0,
                summaryText: total > 0 ? `共 ${total} 条 · 按访问时间由近及远` : '',
                loaded: true,
                loadingMore: false,
            });
        }
        catch {
            if (reset) {
                this.setData({
                    groups: [],
                    total: 0,
                    page: 0,
                    hasMore: false,
                    loadFinished: false,
                    summaryText: '',
                    loaded: true,
                    loadingMore: false,
                });
            }
            else {
                this.setData({ loadingMore: false });
                wx.showToast({ title: '加载失败', icon: 'none' });
            }
        }
        finally {
            this._loading = false;
        }
    },
    go(e) {
        const id = e.currentTarget.dataset.id;
        if (!id)
            return;
        (0, router_1.navigateTo)(router_1.ROUTES.boxDetail, { boxId: id });
    },
});
