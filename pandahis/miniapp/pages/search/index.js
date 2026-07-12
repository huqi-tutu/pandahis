"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const api_1 = require("../../native-utils/api");
const search_history_storage_1 = require("../../native-utils/search-history-storage");
const router_1 = require("../../native-utils/router");
Page({
    data: {
        keyword: '',
        hotKeywords: [],
        historyKeywords: [],
        headerPadPx: 88,
    },
    onLoad() {
        // 与 proto-nav 一致：状态栏 + 88rpx 导航行（随屏宽换算 px）
        try {
            const sys = wx.getSystemInfoSync();
            const navPx = 88 * (sys.windowWidth / 750);
            this.setData({ headerPadPx: (sys.statusBarHeight || 20) + navPx });
        }
        catch {
            this.setData({ headerPadPx: 88 });
        }
    },
    onShow() {
        const tab = typeof this.getTabBar === 'function' ? this.getTabBar() : null;
        if (tab && typeof tab.setSelected === 'function') {
            ;
            tab.setSelected(1);
        }
        void this.loadSuggest();
    },
    async loadSuggest() {
        let hotKeywords = [];
        let historyKeywords = [];
        try {
            const res = await (0, api_1.request)('/search/suggest');
            hotKeywords = res.data.hotKeywords || [];
            if ((0, api_1.hasToken)()) {
                historyKeywords = res.data.historyKeywords || [];
            }
        }
        catch {
            // 离线时仍展示本地历史
        }
        if (!(0, api_1.hasToken)()) {
            historyKeywords = (0, search_history_storage_1.readLocalSearchHistory)().map((keyword) => ({
                keyword,
                lastSearchedAt: '',
            }));
        }
        this.setData({ hotKeywords, historyKeywords });
    },
    onInput(e) {
        this.setData({ keyword: e.detail.value || '' });
    },
    onConfirm() {
        void this.doSearch();
    },
    onClear() {
        this.setData({ keyword: '' });
    },
    async doSearch() {
        const keyword = (this.data.keyword || '').trim();
        if (!keyword) {
            wx.showToast({ title: '请输入关键词', icon: 'none' });
            return;
        }
        (0, router_1.navigateTo)(router_1.ROUTES.searchResult, { q: keyword });
    },
    tapKeyword(e) {
        const k = e.currentTarget.dataset.k;
        if (!k)
            return;
        if (!(0, api_1.hasToken)())
            (0, search_history_storage_1.addLocalSearchHistory)(k);
        (0, router_1.navigateTo)(router_1.ROUTES.searchResult, { q: k });
    },
    async removeHistory(e) {
        const k = e.currentTarget.dataset.k;
        if (!k)
            return;
        if ((0, api_1.hasToken)()) {
            try {
                const qs = `keyword=${encodeURIComponent(k)}`;
                await (0, api_1.request)(`/search/history?${qs}`, { method: 'DELETE', auth: true });
                await this.loadSuggest();
            }
            catch (err) {
                const msg = err instanceof Error ? err.message : '清除失败';
                if (msg === 'UNAUTHORIZED') {
                    wx.showToast({ title: '请先登录', icon: 'none' });
                    return;
                }
                wx.showToast({ title: msg, icon: 'none' });
            }
            return;
        }
        (0, search_history_storage_1.removeLocalSearchHistory)(k);
        await this.loadSuggest();
    },
});
