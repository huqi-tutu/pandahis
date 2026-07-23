"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const api_1 = require("../../native-utils/api");
const favorite_display_1 = require("../../native-utils/favorite-display");
const read_complete_1 = require("../../native-utils/read-complete");
const router_1 = require("../../native-utils/router");
const ACTION_WIDTH_RPX = 168;
Page({
    data: {
        hasToken: false,
        loaded: false,
        total: 0,
        summaryText: '',
        items: [],
        headerPadPx: 88,
        openBoxId: '',
        draggingBoxId: '',
    },
    _actionWidthPx: 84,
    _swipe: null,
    onLoad() {
        try {
            const sys = wx.getSystemInfoSync();
            const navPx = 88 * (sys.windowWidth / 750);
            this._actionWidthPx = ACTION_WIDTH_RPX * (sys.windowWidth / 750);
            this.setData({ headerPadPx: (sys.statusBarHeight || 20) + navPx });
        }
        catch {
            this.setData({ headerPadPx: 88 });
        }
    },
    onShow() {
        const ok = (0, api_1.hasToken)();
        this._swipe = null;
        this.setData({
            hasToken: ok,
            loaded: false,
            items: [],
            total: 0,
            summaryText: '',
            openBoxId: '',
            draggingBoxId: '',
        });
        if (ok)
            void this.load();
    },
    goLogin() {
        (0, router_1.navigateTo)(router_1.ROUTES.login);
    },
    buildSummary(total) {
        if (total <= 0)
            return '';
        return `共 ${total} 条 · 按标记时间由近及远 · 左滑可取消`;
    },
    toRows(items) {
        const openBoxId = this.data.openBoxId;
        const actionWidthPx = this._actionWidthPx;
        return items.map((item) => ({
            ...(0, favorite_display_1.toReadCompleteCardView)(item),
            swipeX: item.boxId === openBoxId ? -actionWidthPx : 0,
        }));
    },
    async load() {
        var _a;
        try {
            const all = [];
            let page = 1;
            const pageSize = 50;
            let total = 0;
            while (true) {
                const res = await (0, api_1.request)(`/read-complete/boxes?page=${page}&pageSize=${pageSize}`, { auth: true });
                const batch = res.data.items || [];
                all.push(...batch);
                total = (_a = res.data.total) !== null && _a !== void 0 ? _a : all.length;
                if (batch.length < pageSize || all.length >= total)
                    break;
                page += 1;
            }
            const openBoxId = this.data.openBoxId;
            const stillOpen = openBoxId && all.some((item) => item.boxId === openBoxId) ? openBoxId : '';
            this.setData({
                openBoxId: stillOpen,
                items: this.toRows(all),
                total,
                summaryText: this.buildSummary(total),
                loaded: true,
            });
        }
        catch {
            this.setData({ items: [], total: 0, summaryText: '', loaded: true, openBoxId: '' });
        }
    },
    updateRowSwipe(boxId, swipeX, extra) {
        const items = this.data.items.map((item) => item.boxId === boxId ? { ...item, swipeX } : item);
        this.setData({ items, ...(extra || {}) });
    },
    closeAllRows() {
        const items = this.data.items.map((item) => ({ ...item, swipeX: 0 }));
        this.setData({ items, openBoxId: '' });
    },
    onSwipeStart(e) {
        var _a;
        const boxId = String(e.currentTarget.dataset.id || '');
        if (!boxId)
            return;
        const item = this.data.items.find((row) => row.boxId === boxId);
        if (!item)
            return;
        if (this.data.openBoxId && this.data.openBoxId !== boxId) {
            this.closeAllRows();
        }
        const current = this.data.items.find((row) => row.boxId === boxId);
        this._swipe = {
            boxId,
            startX: e.touches[0].clientX,
            startOffset: (_a = current === null || current === void 0 ? void 0 : current.swipeX) !== null && _a !== void 0 ? _a : 0,
        };
        this.setData({ draggingBoxId: boxId });
    },
    onSwipeMove(e) {
        const session = this._swipe;
        if (!session)
            return;
        const dx = e.touches[0].clientX - session.startX;
        const max = this._actionWidthPx;
        const next = Math.max(-max, Math.min(0, session.startOffset + dx));
        this.updateRowSwipe(session.boxId, next);
    },
    onSwipeEnd() {
        var _a;
        const session = this._swipe;
        this._swipe = null;
        this.setData({ draggingBoxId: '' });
        if (!session)
            return;
        const item = this.data.items.find((row) => row.boxId === session.boxId);
        const current = (_a = item === null || item === void 0 ? void 0 : item.swipeX) !== null && _a !== void 0 ? _a : 0;
        const open = Math.abs(current) > this._actionWidthPx * 0.38;
        const swipeX = open ? -this._actionWidthPx : 0;
        this.updateRowSwipe(session.boxId, swipeX, { openBoxId: open ? session.boxId : '' });
    },
    go(e) {
        const id = String(e.currentTarget.dataset.id || '');
        if (!id)
            return;
        const item = this.data.items.find((row) => row.boxId === id);
        if (!item)
            return;
        if (Math.abs(item.swipeX) > 8) {
            this.updateRowSwipe(id, 0, { openBoxId: '' });
            return;
        }
        (0, router_1.navigateTo)(router_1.ROUTES.boxDetail, { boxId: id });
    },
    async onUnmark(e) {
        const boxId = String(e.currentTarget.dataset.id || '');
        if (!boxId)
            return;
        try {
            await (0, read_complete_1.unmarkBoxReadComplete)(boxId);
            const items = this.data.items.filter((item) => item.boxId !== boxId);
            const total = Math.max(0, this.data.total - 1);
            const openBoxId = this.data.openBoxId === boxId ? '' : this.data.openBoxId;
            this.setData({
                items,
                total,
                openBoxId,
                summaryText: this.buildSummary(total),
            });
            wx.showToast({ title: '已取消标记', icon: 'none' });
        }
        catch (err) {
            const msg = err instanceof Error ? err.message : '操作失败';
            wx.showToast({ title: msg, icon: 'none' });
        }
    },
});
