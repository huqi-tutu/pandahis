"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const api_1 = require("../../native-utils/api");
const note_1 = require("../../native-utils/note");
const nav_metrics_1 = require("../../native-utils/nav-metrics");
const query_value_1 = require("../../native-utils/query-value");
const router_1 = require("../../native-utils/router");
Page({
    data: {
        hasToken: false,
        loaded: false,
        dynastyId: '',
        navTitle: '笔记',
        items: [],
        pageTopPadPx: 88,
    },
    onLoad(query) {
        try {
            this.setData({ pageTopPadPx: (0, nav_metrics_1.computePageTopPadPx)() });
        }
        catch {
            this.setData({ pageTopPadPx: 88 });
        }
        const dynastyId = (0, query_value_1.decodeQueryValue)(query.dynastyId || '');
        const dynastyName = (0, query_value_1.decodeQueryValue)(query.dynastyName || '') || '笔记';
        this.setData({ dynastyId, navTitle: dynastyName });
    },
    onShow() {
        const ok = (0, api_1.hasToken)();
        this.setData({ hasToken: ok, loaded: false });
        if (ok)
            void this.load();
        else
            this.setData({ loaded: true, items: [] });
    },
    goLogin() {
        (0, router_1.navigateTo)(router_1.ROUTES.login);
    },
    mapItem(item) {
        const remark = String(item.noteText || '').trim();
        return {
            ...item,
            createdAtLabel: (0, note_1.formatNoteTime)(item.createdAt),
            selectedExcerpt: (0, note_1.excerptText)(item.selectedText, 80),
            remarkLabel: (0, note_1.noteRemarkLabel)(remark),
            emptyRemark: !remark,
        };
    },
    async load() {
        const dynastyId = this.data.dynastyId;
        if (!dynastyId) {
            this.setData({ items: [], loaded: true });
            return;
        }
        try {
            const all = [];
            let page = 1;
            const pageSize = 50;
            let total = 0;
            while (true) {
                const res = await (0, note_1.fetchNotesByDynasty)(dynastyId, page, pageSize);
                all.push(...res.items);
                total = res.total;
                if (res.items.length < pageSize || all.length >= total)
                    break;
                page += 1;
            }
            this.setData({ items: all.map((x) => this.mapItem(x)), loaded: true });
        }
        catch {
            this.setData({ items: [], loaded: true });
        }
    },
    onItemTap(e) {
        const id = Number(e.currentTarget.dataset.id);
        if (!id)
            return;
        (0, router_1.navigateTo)(router_1.ROUTES.noteDetail, { id });
    },
});
