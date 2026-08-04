"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const api_1 = require("../../native-utils/api");
const category_label_1 = require("../../native-utils/category-label");
const format_1 = require("../../native-utils/format");
const search_history_storage_1 = require("../../native-utils/search-history-storage");
const router_1 = require("../../native-utils/router");
const nav_metrics_1 = require("../../native-utils/nav-metrics");
const year_format_1 = require("../../native-utils/year-format");
Page({
    data: {
        keyword: '',
        searching: false,
        preciseResults: [],
        relatedResults: [],
        preciseTotal: 0,
        relatedTotal: 0,
        resultTotal: 0,
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
    mapResultItem(it) {
        const id = String(it.id || '').trim();
        if (!id)
            return null;
        const type = String(it.type || 'box').trim() || 'box';
        const titlePlain = (0, format_1.stripHtml)(it.titleHighlight || '');
        const category = String(it.categoryName || '').trim() ||
            (0, category_label_1.categoryLabel)(String(it.categoryKey || ''));
        const coordinateText = String(it.coordinateText || '').trim();
        const startYear = typeof it.startYear === 'number' ? it.startYear : undefined;
        const endYear = typeof it.endYear === 'number' ? it.endYear : undefined;
        const yearText = startYear !== undefined || endYear !== undefined
            ? (0, year_format_1.formatYearRange)(startYear, endYear, ' — ')
            : '';
        const personTag = String(it.personTag || '').trim();
        return {
            key: `${type}-${id}`,
            type,
            id,
            titlePlain,
            category,
            coordinateText,
            yearText,
            personTag,
            hasPersonTag: personTag.length > 0,
        };
    },
    async doSearch(keyword) {
        var _a, _b, _c;
        this.setData({ searching: true });
        try {
            const q = encodeURIComponent(keyword);
            const res = await (0, api_1.request)(`/search?q=${q}&page=1&pageSize=50`);
            const preciseRaw = Array.isArray(res.data.preciseItems)
                ? res.data.preciseItems
                : (res.data.items || []).filter((it) => it.matchTier !== 'related');
            const relatedRaw = Array.isArray(res.data.relatedItems)
                ? res.data.relatedItems
                : (res.data.items || []).filter((it) => it.matchTier === 'related');
            const preciseResults = preciseRaw
                .map((it) => this.mapResultItem(it))
                .filter((it) => Boolean(it));
            const relatedResults = relatedRaw
                .map((it) => this.mapResultItem(it))
                .filter((it) => Boolean(it));
            const preciseTotal = (_a = res.data.preciseTotal) !== null && _a !== void 0 ? _a : preciseResults.length;
            const relatedTotal = (_b = res.data.relatedTotal) !== null && _b !== void 0 ? _b : relatedResults.length;
            this.setData({
                preciseResults,
                relatedResults,
                preciseTotal,
                relatedTotal,
                resultTotal: (_c = res.data.total) !== null && _c !== void 0 ? _c : preciseTotal + relatedTotal,
                searching: false,
            });
        }
        catch (e) {
            wx.showToast({ title: e instanceof Error ? e.message : '搜索失败', icon: 'none' });
            this.setData({
                searching: false,
                preciseResults: [],
                relatedResults: [],
                preciseTotal: 0,
                relatedTotal: 0,
                resultTotal: 0,
            });
        }
    },
    go(e) {
        const ds = e.currentTarget.dataset;
        const id = String(ds.id || '').trim();
        if (!id) {
            wx.showToast({ title: '条目无效', icon: 'none' });
            return;
        }
        // 搜索结果仅返回史略（box）；兼容旧 type
        const type = String(ds.type || 'box').trim();
        if (type === 'unit') {
            (0, router_1.navigateTo)(router_1.ROUTES.dynastyDetail, { unitId: id });
            return;
        }
        (0, router_1.navigateTo)(router_1.ROUTES.boxDetail, { boxId: id });
    },
});
