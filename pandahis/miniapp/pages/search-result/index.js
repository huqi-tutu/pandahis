"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const api_1 = require("../../native-utils/api");
const format_1 = require("../../native-utils/format");
const search_history_storage_1 = require("../../native-utils/search-history-storage");
const router_1 = require("../../native-utils/router");
const nav_metrics_1 = require("../../native-utils/nav-metrics");
const FILTER_CATS = ['全部', '君王', '士臣', '典制', '事略', '民录'];
function extractCategory(pathText, type) {
    if (type !== 'box')
        return '';
    const parts = String(pathText || '')
        .split(/[›>]/g)
        .map((s) => s.trim())
        .filter(Boolean);
    const last = parts[parts.length - 1] || '';
    return FILTER_CATS.includes(last) ? last : '';
}
function applyFilter(items, filterIndex) {
    if (filterIndex <= 0)
        return items;
    const cat = FILTER_CATS[filterIndex];
    return items.filter((it) => it.category === cat);
}
Page({
    data: {
        keyword: '',
        searching: false,
        results: [],
        filteredResults: [],
        resultTotal: 0,
        filterCats: [...FILTER_CATS],
        filterIndex: 0,
        pageTopPadPx: 88,
    },
    onLoad(query) {
        try {
            this.setData({ pageTopPadPx: (0, nav_metrics_1.computePageTopPadPx)() });
        }
        catch {
            this.setData({ pageTopPadPx: 88 });
        }
        const keyword = decodeURIComponent(query.q || query.keyword || '');
        this.setData({ keyword });
        if (keyword) {
            (0, search_history_storage_1.addLocalSearchHistory)(keyword);
            void this.doSearch(keyword);
        }
    },
    mapResultItems(items) {
        return (items || []).map((it) => {
            const pathText = (0, format_1.formatSearchPath)(it.pathText || '');
            const descPlain = (0, format_1.stripHtml)(it.descHighlight || '');
            return {
                key: `${it.type}-${it.id}`,
                type: it.type,
                id: it.id,
                pathText,
                dynastyHint: it.type === 'unit' ? (0, format_1.extractUnitDynastyHint)(pathText) : '',
                titleRich: (0, format_1.highlightEmToRich)(it.titleHighlight || ''),
                descRich: (0, format_1.highlightEmToRich)(it.descHighlight || ''),
                hasDesc: descPlain.length > 0,
                category: extractCategory(pathText, it.type),
            };
        });
    },
    async doSearch(keyword) {
        var _a;
        this.setData({ searching: true, filterIndex: 0 });
        try {
            const q = encodeURIComponent(keyword);
            const res = await (0, api_1.request)(`/search?q=${q}&page=1&pageSize=20`);
            const results = this.mapResultItems(res.data.items || []);
            this.setData({
                results,
                filteredResults: results,
                resultTotal: (_a = res.data.total) !== null && _a !== void 0 ? _a : results.length,
                searching: false,
            });
        }
        catch (e) {
            wx.showToast({ title: e instanceof Error ? e.message : '搜索失败', icon: 'none' });
            this.setData({ searching: false });
        }
    },
    onFilter(e) {
        const i = Number(e.currentTarget.dataset.i);
        if (!Number.isFinite(i))
            return;
        const results = this.data.results;
        this.setData({
            filterIndex: i,
            filteredResults: applyFilter(results, i),
        });
    },
    go(e) {
        const ds = e.currentTarget.dataset;
        if (ds.type === 'unit') {
            (0, router_1.navigateTo)(router_1.ROUTES.dynastyDetail, {
                unitId: ds.id,
                dynasty: ds.dynasty || '',
            });
            return;
        }
        if (ds.type === 'box') {
            (0, router_1.navigateTo)(router_1.ROUTES.boxDetail, { boxId: ds.id });
        }
    },
});
