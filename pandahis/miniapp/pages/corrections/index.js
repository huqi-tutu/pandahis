"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const api_1 = require("../../native-utils/api");
const correction_1 = require("../../native-utils/correction");
const router_1 = require("../../native-utils/router");
const nav_metrics_1 = require("../../native-utils/nav-metrics");
const EMPTY_DETAIL = {
    id: 0,
    boxId: '',
    boxTitle: '',
    civilizationName: '',
    dynastyName: '',
    sourceType: 'dynasty_canvas',
    sourceRefId: null,
    status: 'pending',
    createdAt: '',
};
Page({
    data: {
        hasToken: false,
        loaded: false,
        items: [],
        detailVisible: false,
        detail: EMPTY_DETAIL,
        canViewSource: false,
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
        this.setData({ hasToken: ok, loaded: false, items: [] });
        if (ok)
            void this.load();
        else
            this.setData({ loaded: true });
    },
    goLogin() {
        (0, router_1.navigateTo)(router_1.ROUTES.login);
    },
    mapItem(item) {
        return {
            ...item,
            createdAtLabel: (0, correction_1.formatCorrectionTime)(item.createdAt),
            statusLabel: (0, correction_1.correctionStatusLabel)(item.status),
        };
    },
    async load() {
        var _a;
        try {
            const all = [];
            let page = 1;
            const pageSize = 50;
            let total = 0;
            while (true) {
                const res = await (0, api_1.request)(`/corrections?page=${page}&pageSize=${pageSize}`, { auth: true });
                const batch = res.data.items || [];
                all.push(...batch);
                total = (_a = res.data.total) !== null && _a !== void 0 ? _a : all.length;
                if (batch.length < pageSize || all.length >= total)
                    break;
                page += 1;
            }
            this.setData({
                items: all.map((x) => this.mapItem(x)),
                loaded: true,
            });
        }
        catch {
            this.setData({ items: [], loaded: true });
        }
    },
    async onItemTap(e) {
        const id = Number(e.currentTarget.dataset.id);
        if (!id)
            return;
        try {
            wx.showLoading({ title: '加载中', mask: true });
            const detail = await (0, correction_1.fetchCorrectionDetail)(id);
            wx.hideLoading();
            const canViewSource = !('error' in (0, correction_1.resolveCorrectionSourceNav)(detail));
            this.setData({ detail, detailVisible: true, canViewSource });
        }
        catch (err) {
            wx.hideLoading();
            const msg = err instanceof Error ? err.message : '加载失败';
            wx.showToast({ title: msg, icon: 'none' });
        }
    },
    closeDetail() {
        this.setData({ detailVisible: false, canViewSource: false });
    },
    onViewSource() {
        const detail = this.data.detail;
        if (!detail || !detail.id || !this.data.canViewSource)
            return;
        const ok = (0, correction_1.navigateToCorrectionSource)(detail);
        if (ok)
            this.setData({ detailVisible: false, canViewSource: false });
    },
});
