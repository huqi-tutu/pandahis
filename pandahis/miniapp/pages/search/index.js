"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const api_1 = require("../../native-utils/api");
const search_history_storage_1 = require("../../native-utils/search-history-storage");
const router_1 = require("../../native-utils/router");
const nav_metrics_1 = require("../../native-utils/nav-metrics");
function dedupeHotKeywords(list) {
    const seen = new Set();
    const out = [];
    for (const item of list) {
        const keyword = String((item === null || item === void 0 ? void 0 : item.keyword) || '').trim();
        if (!keyword || seen.has(keyword))
            continue;
        seen.add(keyword);
        out.push({ keyword, isHot: Boolean(item.isHot) });
    }
    return out;
}
Page({
    data: {
        keyword: '',
        hotKeywords: [],
        historyKeywords: [],
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
            hotKeywords = dedupeHotKeywords(res.data.hotKeywords || []);
            if ((0, api_1.hasToken)()) {
                historyKeywords = res.data.historyKeywords || [];
            }
        }
        catch {
            // 离线时仍展示本地历史
        }
        // 未登录，或登录态服务端暂无历史时，回退本地最近搜索
        if (!historyKeywords.length) {
            historyKeywords = (0, search_history_storage_1.readLocalSearchHistory)().map((keyword) => ({
                keyword,
                lastSearchedAt: '',
            }));
        }
        // 热门固定展示 TOP10（后端已按搜索量聚合）
        this.setData({ hotKeywords: hotKeywords.slice(0, 10), historyKeywords });
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
        // 本地始终记一笔，保证「最近搜索」可展示；登录态另由 /search 写入服务端
        (0, search_history_storage_1.addLocalSearchHistory)(keyword);
        (0, router_1.navigateTo)(router_1.ROUTES.searchResult, { q: keyword });
    },
    tapKeyword(e) {
        const k = e.currentTarget.dataset.k;
        if (!k)
            return;
        (0, search_history_storage_1.addLocalSearchHistory)(k);
        (0, router_1.navigateTo)(router_1.ROUTES.searchResult, { q: k });
    },
    async removeHistory(e) {
        const k = e.currentTarget.dataset.k;
        if (!k)
            return;
        // 本地始终清除，避免服务端清空后被本地回退重新展示
        (0, search_history_storage_1.removeLocalSearchHistory)(k);
        if ((0, api_1.hasToken)()) {
            try {
                const qs = `keyword=${encodeURIComponent(k)}`;
                await (0, api_1.request)(`/search/history?${qs}`, { method: 'DELETE', auth: true });
            }
            catch (err) {
                const msg = err instanceof Error ? err.message : '清除失败';
                if (msg === 'UNAUTHORIZED') {
                    wx.showToast({ title: '请先登录', icon: 'none' });
                    await this.loadSuggest();
                    return;
                }
                wx.showToast({ title: msg, icon: 'none' });
                await this.loadSuggest();
                return;
            }
        }
        await this.loadSuggest();
    },
});
