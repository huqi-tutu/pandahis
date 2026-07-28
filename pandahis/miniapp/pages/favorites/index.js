"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const api_1 = require("../../native-utils/api");
const favorite_display_1 = require("../../native-utils/favorite-display");
const router_1 = require("../../native-utils/router");
const nav_metrics_1 = require("../../native-utils/nav-metrics");
async function fetchAllBoxFavorites() {
    var _a;
    const all = [];
    let page = 1;
    const pageSize = 50;
    while (true) {
        const res = await (0, api_1.request)(`/favorites/boxes?page=${page}&pageSize=${pageSize}`, { auth: true });
        const batch = res.data.items || [];
        all.push(...batch);
        const total = (_a = res.data.total) !== null && _a !== void 0 ? _a : all.length;
        if (batch.length < pageSize || all.length >= total)
            break;
        page += 1;
    }
    return all;
}
async function fetchAllUnitFavorites() {
    var _a;
    const all = [];
    let page = 1;
    const pageSize = 50;
    while (true) {
        const res = await (0, api_1.request)(`/favorites/units?page=${page}&pageSize=${pageSize}`, { auth: true });
        const batch = res.data.items || [];
        all.push(...batch);
        const total = (_a = res.data.total) !== null && _a !== void 0 ? _a : all.length;
        if (batch.length < pageSize || all.length >= total)
            break;
        page += 1;
    }
    return all;
}
Page({
    data: {
        hasToken: false,
        loaded: false,
        activeTab: 'dynasty',
        dynastyCount: 0,
        shilueCount: 0,
        visibleItems: [],
        dynastyItems: [],
        shilueItems: [],
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
            visibleItems: [],
            dynastyItems: [],
            shilueItems: [],
            dynastyCount: 0,
            shilueCount: 0,
        });
        if (ok)
            void this.load();
    },
    goLogin() {
        (0, router_1.navigateTo)(router_1.ROUTES.login);
    },
    onTab(e) {
        const tab = e.currentTarget.dataset.tab;
        if (!tab || tab === this.data.activeTab)
            return;
        this.applyTab(tab);
    },
    applyTab(tab) {
        const visibleItems = tab === 'dynasty' ? this.data.dynastyItems : this.data.shilueItems;
        this.setData({ activeTab: tab, visibleItems });
    },
    async load() {
        try {
            const [unitRaw, boxRaw] = await Promise.all([
                fetchAllUnitFavorites(),
                fetchAllBoxFavorites(),
            ]);
            const dynasty = unitRaw.map(favorite_display_1.toUnitFavoriteCardView);
            const shilue = boxRaw.map(favorite_display_1.toFavoriteCardView);
            const activeTab = dynasty.length > 0 ? 'dynasty' : shilue.length > 0 ? 'shilue' : 'dynasty';
            const visibleItems = activeTab === 'dynasty' ? dynasty : shilue;
            this.setData({
                dynastyItems: dynasty,
                shilueItems: shilue,
                dynastyCount: dynasty.length,
                shilueCount: shilue.length,
                activeTab,
                visibleItems,
                loaded: true,
            });
        }
        catch {
            this.setData({
                dynastyItems: [],
                shilueItems: [],
                visibleItems: [],
                dynastyCount: 0,
                shilueCount: 0,
                loaded: true,
            });
        }
    },
    go(e) {
        const ds = e.currentTarget.dataset;
        const id = ds.id || '';
        if (!id)
            return;
        if (ds.kind === 'dynasty' || this.data.activeTab === 'dynasty') {
            (0, router_1.navigateTo)(router_1.ROUTES.dynastyDetail, { unitId: id });
            return;
        }
        (0, router_1.navigateTo)(router_1.ROUTES.boxDetail, { boxId: id });
    },
});
