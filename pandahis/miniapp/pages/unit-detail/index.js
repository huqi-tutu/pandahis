"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const api_1 = require("../../native-utils/api");
const encode_path_segment_1 = require("../../native-utils/encode-path-segment");
const favorite_box_1 = require("../../native-utils/favorite-box");
const router_1 = require("../../native-utils/router");
const format_1 = require("../../native-utils/format");
const share_invite_1 = require("../../native-utils/share-invite");
function previewIntro(intro) {
    const max = 80;
    if (!intro || intro.length <= max)
        return { preview: intro || '', canExpand: false };
    return { preview: `${intro.slice(0, max)}…`, canExpand: true };
}
function heroDynastyTitle(dynastyTitle) {
    const d = (dynastyTitle || '').trim();
    if (!d)
        return '';
    if (d.endsWith('朝'))
        return d;
    return `${d}朝`;
}
function titleLines(title) {
    const raw = (title || '').trim();
    if (!raw)
        return [''];
    const parts = raw.split(/\r?\n/).map((s) => s.trim()).filter(Boolean);
    return parts.length ? parts : [raw];
}
function cellCardClass(highlight, colIndex) {
    if (highlight) {
        return 'ud-artifact--surface ud-artifact--marker';
    }
    return colIndex % 2 === 0 ? 'ud-artifact--high' : 'ud-artifact--highest';
}
Page({
    data: {
        unit: null,
        dynastyTitle: '',
        navTitle: '',
        heroDynastyTitle: '',
        heroSubLine: '',
        civTabs: [],
        relatedUnits: [],
        nextUnit: null,
        catHeaders: [],
        matrixRows: [],
        matrixStickyTopPx: 88,
        introPreview: '',
        introCanExpand: false,
        showIntroModal: false,
        matrixBoxIds: [],
        isFav: false,
        favPartial: false,
        favToggling: false,
    },
    onShow() {
        void this.refreshFavState();
    },
    onShareAppMessage() {
        const u = this.data.unit;
        const t = this.data.dynastyTitle || (u === null || u === void 0 ? void 0 : u.name) || '朝代详情';
        const id = u === null || u === void 0 ? void 0 : u.id;
        const path = id ? `/pages/unit-detail/index?unitId=${encodeURIComponent(id)}` : '/pages/unit-detail/index';
        return { title: t, path };
    },
    async onLoad(query) {
        var _a, _b;
        const unitId = query.unitId || query.id;
        if (!unitId)
            return;
        const menu = wx.getMenuButtonBoundingClientRect();
        const sys = wx.getSystemInfoSync();
        const matrixStickyTopPx = Math.max(Math.ceil(menu.bottom), (sys.statusBarHeight || 0) + 44);
        try {
            const enc = (0, encode_path_segment_1.encodePathSegment)(unitId);
            const [heroRes, matrixRes, civRes] = await Promise.all([
                (0, api_1.request)(`/units/${enc}`),
                (0, api_1.request)(`/units/${enc}/matrix`),
                (0, api_1.request)(`/units/${enc}/civ-tabs`).catch(() => ({ data: { tabs: [] } })),
            ]);
            const hero = heroRes.data;
            const unit = hero.unit;
            const dynastyTitle = (unit.dynastyName && unit.dynastyName.trim()) || unit.name;
            const navTitle = dynastyTitle.length <= 3 ? dynastyTitle : dynastyTitle.slice(0, 4);
            const matrix = matrixRes.data;
            let civTabs = ((_a = civRes.data) === null || _a === void 0 ? void 0 : _a.tabs) || [];
            if (!civTabs.length) {
                civTabs = [{ civilizationId: 0, civilizationName: '', unitId: unit.id, isActive: true }];
            }
            let catOrder = matrix.categories || [];
            if (!catOrder.length) {
                catOrder = format_1.PRD_CATEGORY_KEYS.map((k) => ({ key: k, name: (0, format_1.categoryLabel)(k) }));
            }
            const itemMap = new Map();
            for (const it of matrix.items || []) {
                itemMap.set(`${it.year}|${it.categoryKey}`, it);
            }
            const matrixRows = (matrix.years || []).map((y) => ({
                year: y.year,
                label: y.label,
                cells: catOrder.map((c, ci) => {
                    const it = itemMap.get(`${y.year}|${c.key}`);
                    if (!it)
                        return null;
                    return {
                        boxId: it.boxId,
                        title: it.title,
                        titleLines: titleLines(it.title),
                        blurb: it.blurb,
                        highlight: it.highlight,
                        cardClass: cellCardClass(it.highlight, ci),
                    };
                }),
            }));
            const activeCiv = civTabs.find((t) => t.isActive) || civTabs[0];
            const civPart = ((activeCiv === null || activeCiv === void 0 ? void 0 : activeCiv.civilizationName) || '').trim();
            const yearRange = `${unit.startYear}–${unit.endYear}`;
            const heroSubLine = civPart ? `${civPart} · ${yearRange}` : yearRange;
            const { preview, canExpand } = previewIntro(unit.summary || '');
            const matrixBoxIds = [];
            for (const row of matrixRows) {
                for (const cell of row.cells) {
                    if (cell === null || cell === void 0 ? void 0 : cell.boxId)
                        matrixBoxIds.push(cell.boxId);
                }
            }
            this.setData({
                unit,
                dynastyTitle,
                navTitle,
                heroDynastyTitle: heroDynastyTitle(dynastyTitle),
                heroSubLine,
                civTabs,
                relatedUnits: hero.relatedUnits || [],
                nextUnit: (_b = hero.nextUnit) !== null && _b !== void 0 ? _b : null,
                catHeaders: catOrder.map((c) => ({ key: c.key, name: c.name || (0, format_1.categoryLabel)(c.key) })),
                matrixRows,
                matrixBoxIds,
                matrixStickyTopPx,
                introPreview: preview,
                introCanExpand: canExpand,
            });
            void this.refreshFavState();
        }
        catch (e) {
            wx.showToast({ title: (e === null || e === void 0 ? void 0 : e.message) || '加载失败', icon: 'none' });
        }
    },
    goUnit(e) {
        const id = e.currentTarget.dataset.id;
        (0, router_1.navigateTo)(router_1.ROUTES.unitDetail, { unitId: id });
    },
    onCivTab(e) {
        var _a;
        const id = e.currentTarget.dataset.id;
        const cur = (_a = this.data.unit) === null || _a === void 0 ? void 0 : _a.id;
        if (!id || id === cur)
            return;
        (0, router_1.navigateTo)(router_1.ROUTES.unitDetail, { unitId: id });
    },
    goBox(e) {
        const id = e.currentTarget.dataset.id;
        (0, router_1.navigateTo)(router_1.ROUTES.boxDetail, { boxId: id });
    },
    openIntro() {
        this.setData({ showIntroModal: true });
    },
    closeIntro() {
        this.setData({ showIntroModal: false });
    },
    noop() { },
    async refreshFavState() {
        const boxIds = this.data.matrixBoxIds;
        if (!boxIds.length) {
            this.setData({ isFav: false, favPartial: false });
            return;
        }
        if (!(0, api_1.hasToken)()) {
            this.setData({ isFav: false, favPartial: false });
            return;
        }
        const favorited = await (0, favorite_box_1.fetchFavoritedBoxIdSet)();
        const st = (0, favorite_box_1.computeUnitFavoriteState)(boxIds, favorited);
        this.setData({
            isFav: st.allFavorited,
            favPartial: st.anyFavorited && !st.allFavorited,
        });
    },
    async onFavoriteTap() {
        if (this.data.favToggling)
            return;
        if (!(0, api_1.hasToken)()) {
            (0, favorite_box_1.promptLoginForFavorite)();
            return;
        }
        const boxIds = this.data.matrixBoxIds;
        if (!boxIds.length) {
            wx.showToast({ title: '当前朝代暂无史略可收藏', icon: 'none' });
            return;
        }
        const favorited = await (0, favorite_box_1.fetchFavoritedBoxIdSet)();
        const st = (0, favorite_box_1.computeUnitFavoriteState)(boxIds, favorited);
        const nextFav = !st.allFavorited;
        this.setData({ favToggling: true });
        wx.showLoading({ title: nextFav ? '收藏中' : '取消中', mask: true });
        try {
            await (0, favorite_box_1.setBoxesFavorited)(boxIds, nextFav);
            await this.refreshFavState();
            const msg = nextFav
                ? st.anyFavorited
                    ? '已补全本朝收藏'
                    : '已收藏本朝史略'
                : '已取消收藏';
            wx.showToast({ title: msg, icon: 'success' });
        }
        catch (e) {
            const msg = e instanceof Error ? e.message : '操作失败';
            wx.showToast({ title: msg.length > 18 ? `${msg.slice(0, 16)}…` : msg, icon: 'none' });
        }
        finally {
            wx.hideLoading();
            this.setData({ favToggling: false });
        }
    },
    onShareTap() {
        (0, share_invite_1.promptContentShareUnavailable)();
    },
    onMoreTap() {
        wx.showActionSheet({
            itemList: ['分享', '反馈与建议'],
            success: (res) => {
                if (res.tapIndex === 0) {
                    (0, share_invite_1.promptContentShareUnavailable)();
                    return;
                }
                if (res.tapIndex === 1) {
                    const email = 'support@pandahis.com';
                    wx.showModal({
                        title: '反馈与建议',
                        content: `请发送邮件至：\n${email}`,
                        confirmText: '复制邮箱',
                        cancelText: '关闭',
                        success: (r) => {
                            if (!r.confirm)
                                return;
                            wx.setClipboardData({
                                data: email,
                                success: () => wx.showToast({ title: '已复制邮箱', icon: 'success' }),
                            });
                        },
                    });
                }
            },
        });
    },
});
