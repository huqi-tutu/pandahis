"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const api_1 = require("../../native-utils/api");
const encode_path_segment_1 = require("../../native-utils/encode-path-segment");
const favorite_box_1 = require("../../native-utils/favorite-box");
const router_1 = require("../../native-utils/router");
const share_invite_1 = require("../../native-utils/share-invite");
function collectMatrixBoxIds(swim) {
    const ids = [];
    for (const lane of (swim === null || swim === void 0 ? void 0 : swim.lanes) || []) {
        for (const row of lane.collapsedRows || []) {
            for (const bar of row) {
                if (bar === null || bar === void 0 ? void 0 : bar.boxId)
                    ids.push(bar.boxId);
            }
        }
    }
    return ids;
}
function splitIntroParagraphs(intro) {
    const text = (intro || '').trim() || '空';
    return text.split(/\n\n+/).map((p) => p.trim()).filter(Boolean);
}
function previewIntro(intro) {
    const paragraphs = splitIntroParagraphs(intro);
    if (paragraphs.length <= 1) {
        return { preview: paragraphs[0] || '空', canExpand: false, paragraphs };
    }
    return { preview: paragraphs[0], canExpand: true, paragraphs };
}
Page({
    swimScrollLeft: 0,
    _echoMatrix: false,
    _echoAxis: false,
    data: {
        unit: null,
        dynastyTitle: '',
        navTitle: '',
        heroSubLine: '',
        swim: null,
        concurrentItems: [],
        relatedUnits: [],
        nextUnit: null,
        introPreview: '',
        introCanExpand: false,
        introParagraphs: [],
        showIntroModal: false,
        matrixBoxIds: [],
        isFav: false,
        favPartial: false,
        favToggling: false,
        headerPadPx: 88,
        scrollTop: 140,
        matrixScrollLeft: 0,
        axisScrollLeft: 0,
        axisPinned: false,
        overlayVisible: false,
        overlayLabel: '',
        overlayBars: [],
        loadError: '',
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
        const unitId = query.unitId || query.id;
        const dynastyHint = decodeURIComponent(query.dynasty || query.displayName || '');
        if (!unitId && !dynastyHint)
            return;
        const sys = wx.getSystemInfoSync();
        const navH = Math.round(88 * (sys.windowWidth / 750));
        const headerPadPx = (sys.statusBarHeight || 20) + navH;
        const tabBarH = Math.round(72 * (sys.windowWidth / 750));
        const scrollTop = headerPadPx + tabBarH;
        const anchorYear = query.anchorYear ? parseInt(query.anchorYear, 10) : NaN;
        const applyPageData = (hero, swim) => {
            const unit = hero.unit;
            const dynastyTitle = (unit.dynastyName && unit.dynastyName.trim()) || unit.name;
            const navTitle = dynastyTitle.length <= 4 ? dynastyTitle : dynastyTitle.slice(0, 4);
            const heroSubLine = `${unit.startYear}–${unit.endYear}`;
            const matrixBoxIds = collectMatrixBoxIds(swim);
            const { preview, canExpand, paragraphs } = previewIntro(unit.summary || '');
            this.setData({
                unit,
                dynastyTitle,
                navTitle,
                heroSubLine,
                swim,
                concurrentItems: swim.concurrentItems || [],
                relatedUnits: hero.relatedUnits || [],
                nextUnit: hero.nextUnit ?? null,
                matrixBoxIds,
                headerPadPx,
                scrollTop,
                introPreview: preview,
                introCanExpand: canExpand,
                introParagraphs: paragraphs,
                loadError: '',
            });
            void this.refreshFavState();
            if (!Number.isNaN(anchorYear)) {
                setTimeout(() => this.scrollToAnchorYear(anchorYear, swim), 120);
            }
        };
        if (unitId) {
            try {
                const enc = (0, encode_path_segment_1.encodePathSegment)(unitId);
                const [heroRes, swimRes] = await Promise.all([
                    (0, api_1.request)(`/units/${enc}`),
                    (0, api_1.request)(`/units/${enc}/swim-matrix`),
                ]);
                applyPageData(heroRes.data, swimRes.data);
                return;
            }
            catch (e) {
                console.error('[unit-detail] API failed', e);
                const msg = (e === null || e === void 0 ? void 0 : e.message) || '加载失败';
                this.setData({
                    unit: null,
                    swim: null,
                    loadError: `无法加载朝代数据（${msg}）。请确认后端已启动且已导入 historical_dynasty / historical_box 数据。`,
                });
                wx.showToast({ title: '加载失败', icon: 'none' });
                return;
            }
        }
        this.setData({ loadError: '缺少朝代 ID，无法加载' });
    },
    scrollToAnchorYear(anchorYear, swim) {
        const span = Math.max(1, swim.endYear - swim.startYear);
        const clamped = Math.max(swim.startYear, Math.min(swim.endYear, anchorYear));
        const sheetPx = (swim.sheetWidthRpx || 1440) * (wx.getSystemInfoSync().windowWidth / 750);
        const targetPx = ((clamped - swim.startYear) / span) * sheetPx;
        const bias = wx.getSystemInfoSync().windowWidth * 0.32;
        const left = Math.max(0, targetPx - bias);
        this.swimScrollLeft = left;
        this.setData({ matrixScrollLeft: left, axisScrollLeft: left });
    },
    onMatrixHScroll(e) {
        const left = e.detail.scrollLeft;
        this.swimScrollLeft = left;
        if (this._echoMatrix) {
            this._echoMatrix = false;
            return;
        }
        if (this.data.axisPinned) {
            this._echoAxis = true;
            this.setData({ axisScrollLeft: left });
        }
    },
    onAxisHScroll(e) {
        const left = e.detail.scrollLeft;
        this.swimScrollLeft = left;
        if (this._echoAxis) {
            this._echoAxis = false;
            return;
        }
        this._echoMatrix = true;
        this.setData({ matrixScrollLeft: left });
    },
    onDynastyScroll(e) {
        const top = e.detail.scrollTop;
        const pinned = top > 120;
        if (pinned !== this.data.axisPinned) {
            this.setData({ axisPinned: pinned });
        }
    },
    onBarTap(e) {
        const boxId = e.currentTarget.dataset.box;
        if (!boxId)
            return;
        (0, router_1.navigateTo)(router_1.ROUTES.boxDetail, { boxId });
    },
    showMoreOverlay(e) {
        const label = e.currentTarget.dataset.label;
        const laneIdx = Number(e.currentTarget.dataset.lane);
        const swim = this.data.swim;
        if (!swim)
            return;
        const lane = swim.lanes[laneIdx];
        if (!lane)
            return;
        const bars = (lane.extraBars && lane.extraBars.length)
            ? lane.extraBars
            : lane.collapsedRows.flat();
        this.setData({ overlayVisible: true, overlayLabel: label, overlayBars: bars });
    },
    hideOverlay() {
        this.setData({ overlayVisible: false });
    },
    goUnit(e) {
        const id = e.currentTarget.dataset.id;
        (0, router_1.navigateTo)(router_1.ROUTES.unitDetail, { unitId: id });
    },
    goNext() {
        const n = this.data.nextUnit;
        if (!(n === null || n === void 0 ? void 0 : n.unitId))
            return;
        (0, router_1.navigateTo)(router_1.ROUTES.unitDetail, { unitId: n.unitId, dynasty: n.title });
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
        if (!boxIds.length || !(0, api_1.hasToken)()) {
            this.setData({ isFav: false, favPartial: false });
            return;
        }
        const favorited = await (0, favorite_box_1.fetchFavoritedBoxIdSet)();
        const st = (0, favorite_box_1.computeUnitFavoriteState)(boxIds, favorited);
        this.setData({ isFav: st.allFavorited, favPartial: st.anyFavorited && !st.allFavorited });
    },
    async onFavoriteTap() {
        if (this.data.favToggling || !(0, api_1.hasToken)()) {
            if (!(0, api_1.hasToken)())
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
        try {
            await (0, favorite_box_1.setBoxesFavorited)(boxIds, nextFav);
            await this.refreshFavState();
            wx.showToast({ title: nextFav ? '已收藏本朝史略' : '已取消收藏', icon: 'success' });
        }
        catch (e) {
            wx.showToast({ title: e instanceof Error ? e.message : '操作失败', icon: 'none' });
        }
        finally {
            this.setData({ favToggling: false });
        }
    },
    onShareTap() {
        (0, share_invite_1.promptContentShareUnavailable)();
    },
});
