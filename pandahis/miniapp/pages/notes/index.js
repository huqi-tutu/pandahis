"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const api_1 = require("../../native-utils/api");
const note_1 = require("../../native-utils/note");
const nav_metrics_1 = require("../../native-utils/nav-metrics");
const router_1 = require("../../native-utils/router");
Page({
    data: {
        hasToken: false,
        loaded: false,
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
        this.setData({ hasToken: ok, loaded: false });
        if (ok)
            void this.load();
        else
            this.setData({ loaded: true, items: [] });
    },
    goLogin() {
        (0, router_1.navigateTo)(router_1.ROUTES.login);
    },
    async load() {
        try {
            const items = await (0, note_1.fetchNoteDynasties)();
            this.setData({ items, loaded: true });
        }
        catch {
            this.setData({ items: [], loaded: true });
        }
    },
    onDynastyTap(e) {
        const ds = e.currentTarget.dataset;
        const dynastyId = String(ds.id || '').trim();
        if (!dynastyId) {
            wx.showToast({ title: '缺少朝代信息', icon: 'none' });
            return;
        }
        (0, router_1.navigateTo)(router_1.ROUTES.noteList, {
            dynastyId,
            dynastyName: String(ds.name || ''),
            civilizationName: String(ds.civ || ''),
        });
    },
});
