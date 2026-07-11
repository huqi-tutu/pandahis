"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const api_1 = require("../../native-utils/api");
const dev_config_1 = require("../../native-utils/dev-config");
const encode_path_segment_1 = require("../../native-utils/encode-path-segment");
const favorite_box_1 = require("../../native-utils/favorite-box");
const router_1 = require("../../native-utils/router");
const share_invite_1 = require("../../native-utils/share-invite");
const swim_lane_palette_1 = require("../../native-utils/swim-lane-palette");
const { formatHistoryYear } = require('../../native-utils/year-format.js');
const { buildSwimMatrixFromMock, buildHeroFromMock, normalizeDynastyKey, isDegradedMockFallback, } = require('./swim-local-fallback');
const PRIORITY_OPTIONS = [
    { value: 'p0', label: 'P0' },
    { value: 'p1', label: 'P1' },
    { value: 'p2', label: 'P2' },
    { value: 'p3', label: 'P3' },
];
const MAX_LANE_ROWS = 10;
const LANE_ROW_HEIGHT_RPX = 44;
const LANE_ROW_GAP_RPX = 16;
const LANE_TRACK_PAD_VERTICAL_RPX = 24;
const CHIP_WIDTH_RPX = 132;
const CHIP_GAP_RPX = 16;
const EDGE_GAP_RPX = 20;
const MORE_WIDTH_RPX = 112;
const MORE_GAP_RPX = 20;
function laneTrackHeight(rowCount) {
    const rows = Math.max(1, Math.min(MAX_LANE_ROWS, rowCount || 1));
    return LANE_TRACK_PAD_VERTICAL_RPX + rows * LANE_ROW_HEIGHT_RPX + (rows - 1) * LANE_ROW_GAP_RPX;
}
function collectMatrixBoxIds(swim) {
    const ids = [];
    for (const lane of (swim === null || swim === void 0 ? void 0 : swim.lanes) || []) {
        const fullView = lane.priorityViews && lane.priorityViews.p3;
        const rows = (fullView === null || fullView === void 0 ? void 0 : fullView.collapsedRows) || lane.collapsedRows || [];
        for (const row of rows) {
            for (const bar of row) {
                if (bar === null || bar === void 0 ? void 0 : bar.boxId)
                    ids.push(bar.boxId);
            }
        }
        for (const bar of ((fullView === null || fullView === void 0 ? void 0 : fullView.extraBars) || lane.extraBars || [])) {
            if (bar === null || bar === void 0 ? void 0 : bar.boxId)
                ids.push(bar.boxId);
        }
    }
    return Array.from(new Set(ids));
}
function findSwimBar(swim, boxId) {
    if (!(swim === null || swim === void 0 ? void 0 : swim.lanes) || !swim.lanes.length || !boxId)
        return null;
    for (const lane of swim.lanes) {
        const rows = lane.collapsedRows || [];
        for (const row of rows) {
            for (const bar of row) {
                if ((bar === null || bar === void 0 ? void 0 : bar.boxId) === boxId)
                    return bar;
            }
        }
        for (const bar of lane.extraBars || []) {
            if ((bar === null || bar === void 0 ? void 0 : bar.boxId) === boxId)
                return bar;
        }
    }
    return null;
}
function percentForYearOnSwim(swim, year) {
    const clamped = Math.max(swim.startYear, Math.min(swim.endYear, year));
    const segments = swim.timeSegments || [];
    if (segments.length) {
        for (const seg of segments) {
            if (clamped < seg.startYear || clamped > seg.endYear)
                continue;
            const segLeft = parseFloat(String(seg.left).replace('%', ''));
            const segWidth = parseFloat(String(seg.width).replace('%', ''));
            const segSpan = Math.max(1, seg.endYear - seg.startYear);
            return segLeft + ((clamped - seg.startYear) / segSpan) * segWidth;
        }
    }
    const span = Math.max(1, swim.endYear - swim.startYear);
    return ((clamped - swim.startYear) / span) * 100;
}
function splitIntroParagraphs(intro) {
    const text = (intro || '').trim() || '空';
    return text.split(/\n\n+/).map((p) => p.trim()).filter(Boolean);
}
function isDevelopEnv() {
    try {
        return wx.getAccountInfoSync()?.miniProgram?.envVersion === 'develop';
    }
    catch (_a) {
        return true;
    }
}
function warnIfDegradedMock(swim) {
    if (!isDegradedMockFallback(swim))
        return;
    wx.showToast({
        title: `后端未连通(${dev_config_1.DEV_LAN_HOST}:${dev_config_1.DEV_API_PORT})，仅显示君王`,
        icon: 'none',
        duration: 3500,
    });
}
function tryLoadLocalMock(dynastyName, unitId) {
    const key = normalizeDynastyKey(dynastyName);
    if (!key)
        return null;
    try {
        const swimMatrix = buildSwimMatrixFromMock(key);
        if (!(swimMatrix === null || swimMatrix === void 0 ? void 0 : swimMatrix.lanes) || !swimMatrix.lanes.length)
            return null;
        const hero = buildHeroFromMock(swimMatrix, unitId || key, key);
        return { hero, swim: swimMatrix };
    }
    catch (err) {
        console.warn('[dynasty-detail] local mock failed', err);
        return null;
    }
}
function generateTimelineTicks(startYear, endYear, originalSheetWidthRpx) {
  const span = endYear - startYear;
  const newSheetWidthRpx = Math.round(originalSheetWidthRpx);
  const ticks = [];
  ticks.push({ label: formatHistoryYear(startYear), left: '0%', edgeStart: true, hideLabel: false });
  const firstTick = Math.ceil((startYear + 1) / 10) * 10;
  let tickYear = firstTick;
  while (tickYear < endYear) {
    const left = ((tickYear - startYear) / span) * 100;
    const distToStart = tickYear - startYear;
    const distToEnd = endYear - tickYear;
    const isPenultimate = tickYear + 20 >= endYear;
    const hideLabel = (tickYear === firstTick && distToStart < 20) || (isPenultimate && distToEnd < 20);
    ticks.push({ label: formatHistoryYear(tickYear), left: left + '%', hideLabel });
    tickYear += 20;
  }
  const gridLines = ticks.filter(function(t) { return t.left !== '0%'; }).map(function(t) { return { left: t.left }; });
  return { ticks, endLabel: formatHistoryYear(endYear), sheetWidthRpx: newSheetWidthRpx, gridLines };
}
function applyPriorityView(swim, priority) {
    const sheetWidthRpx = swim.sheetWidthRpx || 1440;
    return Object.assign(Object.assign({}, swim), { sheetWidthRpx, lanes: (swim.lanes || []).map((lane, laneIndex) => {
            var _a;
            const view = (_a = lane.priorityViews) === null || _a === void 0 ? void 0 : _a[priority];
            const base = !view
                ? normalizeLegacyLane(lane, sheetWidthRpx, priority)
                : Object.assign(Object.assign({}, lane), { collapsedRows: view.collapsedRows || [[]], hasMore: view.hasMore, moreCount: view.moreCount, moreBarLeft: view.moreBarLeft, moreBarWidth: view.moreBarWidth, extraBars: view.extraBars || [], rowCount: view.rowCount, trackHeightRpx: view.trackHeightRpx, visibleCount: view.visibleCount });
            return (0, swim_lane_palette_1.enrichSwimLaneVisuals)(base, laneIndex);
        }) });
}
function estimateSheetWidth(swim) {
    const base = swim.sheetWidthRpx || 1440;
    const maxBars = Math.max(0, ...(swim.lanes || []).map((lane) => {
        var _a;
        const view = (_a = lane.priorityViews) === null || _a === void 0 ? void 0 : _a.p3;
        if (view)
            return view.visibleCount;
        return (lane.collapsedRows || []).reduce((count, row) => count + row.length, 0) + (lane.extraBars || []).length;
    }));
    const perRow = Math.max(1, Math.ceil(maxBars / MAX_LANE_ROWS));
    const needed = EDGE_GAP_RPX + perRow * CHIP_WIDTH_RPX + Math.max(0, perRow - 1) * CHIP_GAP_RPX + MORE_GAP_RPX + MORE_WIDTH_RPX + EDGE_GAP_RPX;
    return Math.max(base, Math.min(base * 4, needed));
}
function normalizeLegacyLane(lane, sheetWidthRpx, priority) {
    const allBars = [...(lane.collapsedRows || []).flat(), ...(lane.extraBars || [])]
        .map((bar) => prepareLegacyBar(bar, sheetWidthRpx))
        .sort(compareLegacyBars);
    const maxPriority = priorityRank(priority);
    const candidates = allBars.filter((bar) => priorityRank(bar.priority) <= maxPriority);
    const hiddenByPriority = allBars.filter((bar) => priorityRank(bar.priority) > maxPriority);
    const packed = packLegacyBars(candidates, sheetWidthRpx);
    const extraBars = [...hiddenByPriority, ...packed.extra].sort(compareLegacyBars);
    const hasMore = extraBars.length > 0;
    return Object.assign(Object.assign({}, lane), { collapsedRows: packed.rows.length ? packed.rows : [[]], hasMore, moreCount: extraBars.length, moreBarLeft: `${moreLeftPct(sheetWidthRpx).toFixed(2)}%`, moreBarWidth: lane.moreBarWidth || '12%', extraBars, rowCount: Math.max(1, packed.rows.length), trackHeightRpx: laneTrackHeight(packed.rows.length), visibleCount: packed.rows.reduce((count, row) => count + row.length, 0) });
}
function prepareLegacyBar(bar, sheetWidthRpx) {
    const rawLeft = parseFloat(String(bar.left || bar.unitLeft || '0').replace('%', ''));
    const edgePct = 20 / sheetWidthRpx * 100;
    const reservedRightRpx = EDGE_GAP_RPX + MORE_GAP_RPX + MORE_WIDTH_RPX;
    const chipPct = CHIP_WIDTH_RPX / sheetWidthRpx * 100;
    const maxLeft = 100 - (CHIP_WIDTH_RPX + reservedRightRpx) / sheetWidthRpx * 100;
    const left = Math.max(edgePct, Math.min(maxLeft, Number.isFinite(rawLeft) ? rawLeft : 0));
    return Object.assign(Object.assign({}, bar), { left: `${left.toFixed(2)}%`, width: `${chipPct.toFixed(2)}%`, _leftPct: left, _rightPct: left + chipPct, _priorityRank: priorityRank(bar.priority), _globalIdNumber: parseGlobalIdNumber(bar.boxId) });
}
function packLegacyBars(bars, sheetWidthRpx) {
    const rows = [];
    const extra = [];
    const gapPct = CHIP_GAP_RPX / sheetWidthRpx * 100;
    for (const bar of bars) {
        let assigned = -1;
        for (let rowIndex = 0; rowIndex < rows.length; rowIndex++) {
            if (canFitRow(rows[rowIndex], bar, gapPct)) {
                assigned = rowIndex;
                rows[rowIndex] = [...rows[rowIndex], bar].sort((a, b) => a._leftPct - b._leftPct);
                break;
            }
        }
        if (assigned === -1) {
            if (rows.length >= MAX_LANE_ROWS) {
                extra.push(bar);
            }
            else {
                rows.push([bar]);
            }
        }
    }
    return { rows, extra };
}
function canFitRow(row, bar, gapPct) {
    return row.every((existing) => bar._rightPct + gapPct <= existing._leftPct || existing._rightPct + gapPct <= bar._leftPct);
}
function compareLegacyBars(a, b) {
    if (a._priorityRank !== b._priorityRank)
        return a._priorityRank - b._priorityRank;
    if (a._leftPct !== b._leftPct)
        return a._leftPct - b._leftPct;
    return a._globalIdNumber - b._globalIdNumber;
}
function priorityRank(priority) {
    const value = String(priority || 'p3').toLowerCase();
    if (value === 'p0')
        return 0;
    if (value === 'p1')
        return 1;
    if (value === 'p2')
        return 2;
    return 3;
}
function parseGlobalIdNumber(boxId) {
    const match = String(boxId || '').match(/^GLBL_(\d+)$/);
    return match ? Number(match[1]) : Number.MAX_SAFE_INTEGER;
}
function moreLeftPct(sheetWidthRpx) {
    return 100 - ((EDGE_GAP_RPX + MORE_WIDTH_RPX) / sheetWidthRpx * 100);
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
        introDisplay: '',
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
        priorityOptions: PRIORITY_OPTIONS,
        activePriority: 'p3',
        chipTooltipVisible: false,
        chipTooltipTitle: '',
        chipTooltipRange: '',
        chipTooltipPeakYear: '',
        chipTooltipPeakReason: '',
        chipTooltipLeftPx: 0,
        chipTooltipTopPx: 0,
    },
    onShow() {
        void this.refreshFavState();
    },
    onShareAppMessage() {
        const u = this.data.unit;
        const t = this.data.dynastyTitle || (u === null || u === void 0 ? void 0 : u.name) || '朝代详情';
        const id = u === null || u === void 0 ? void 0 : u.id;
        const path = id ? `/pages/dynasty-detail/index?unitId=${encodeURIComponent(id)}` : '/pages/dynasty-detail/index';
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
            const heroSubLine = `${formatHistoryYear(unit.startYear)}–${formatHistoryYear(unit.endYear)}`;
            const activePriority = this.data.activePriority || 'p3';
            const prioritySwim = applyPriorityView(swim, activePriority);
            const matrixBoxIds = collectMatrixBoxIds(prioritySwim);
            const { preview, canExpand, paragraphs } = previewIntro(unit.summary || '');
            this.setData({
                unit,
                dynastyTitle,
                navTitle,
                heroSubLine,
                swim: prioritySwim,
                concurrentItems: prioritySwim.concurrentItems || [],
                relatedUnits: hero.relatedUnits || [],
                nextUnit: hero.nextUnit ?? null,
                matrixBoxIds,
                headerPadPx,
                scrollTop,
                introPreview: preview,
                introDisplay: preview,
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
                const enhancedSwim = Object.assign({}, swimRes.data, { gridLines: swimRes.data.gridLines || [] });
        applyPageData(heroRes.data, enhancedSwim);
                return;
            }
            catch (e) {
                console.error('[dynasty-detail] API failed', e);
                if (isDevelopEnv() && dynastyHint) {
                    const fallback = tryLoadLocalMock(dynastyHint, unitId);
                    if (fallback) {
                        console.warn('[dynasty-detail] using local mock for', dynastyHint);
                        const enhancedSwim = Object.assign({}, fallback.swim, generateTimelineTicks(fallback.swim.startYear, fallback.swim.endYear, fallback.swim.sheetWidthRpx), { timeScaleMode: 'linear' });
                        applyPageData(fallback.hero, enhancedSwim);
                        warnIfDegradedMock(enhancedSwim);
                        return;
                    }
                }
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
        if (isDevelopEnv() && dynastyHint) {
            const fallback = tryLoadLocalMock(dynastyHint, '');
            if (fallback) {
                console.warn('[dynasty-detail] using local mock for', dynastyHint);
                const enhancedSwim = Object.assign({}, fallback.swim, generateTimelineTicks(fallback.swim.startYear, fallback.swim.endYear, fallback.swim.sheetWidthRpx), { timeScaleMode: 'linear' });
                applyPageData(fallback.hero, enhancedSwim);
                warnIfDegradedMock(enhancedSwim);
                return;
            }
        }
        this.setData({ loadError: '缺少朝代 ID，无法加载' });
    },
    scrollToAnchorYear(anchorYear, swim) {
        const sheetPx = (swim.sheetWidthRpx || 1440) * (wx.getSystemInfoSync().windowWidth / 750);
        const targetPx = (percentForYearOnSwim(swim, anchorYear) / 100) * sheetPx;
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
        if (this.data.chipTooltipVisible) {
            this.hideChipTooltip();
        }
    },
    onBarTap(e) {
        if (this.data.chipTooltipVisible) {
            this.hideChipTooltip();
            return;
        }
        const ds = e.currentTarget.dataset || {};
        const boxId = ds.box;
        if (!boxId)
            return;
        (0, router_1.navigateTo)(router_1.ROUTES.boxDetail, { boxId, title: ds.title || '' });
    },
    onBarLongPress(e) {
        var _a, _b;
        const ds = e.currentTarget.dataset || {};
        const boxId = ds.box;
        const bar = findSwimBar(this.data.swim, boxId);
        const touch = ((_a = e.touches) === null || _a === void 0 ? void 0 : _a[0]) || ((_b = e.changedTouches) === null || _b === void 0 ? void 0 : _b[0]);
        const sys = wx.getSystemInfoSync();
        const left = (touch === null || touch === void 0 ? void 0 : touch.clientX) == null ? Math.round(sys.windowWidth / 2) : Math.max(140, Math.min(sys.windowWidth - 140, touch.clientX));
        const top = (touch === null || touch === void 0 ? void 0 : touch.clientY) == null ? Math.round(sys.windowHeight * 0.45) : Math.max(120, Math.min(sys.windowHeight - 160, touch.clientY - 96));
        const peakYearNum = bar === null || bar === void 0 ? void 0 : bar.peakYear;
        const peakReason = String((bar === null || bar === void 0 ? void 0 : bar.peakReason) || '').trim();
        this.setData({
            chipTooltipVisible: true,
            chipTooltipTitle: (bar === null || bar === void 0 ? void 0 : bar.title) || ds.title || '',
            chipTooltipRange: (bar === null || bar === void 0 ? void 0 : bar.timeRange) || ds.range || '',
            chipTooltipPeakYear: peakYearNum == null ? '' : formatHistoryYear(peakYearNum),
            chipTooltipPeakReason: peakReason,
            chipTooltipLeftPx: left,
            chipTooltipTopPx: top,
        });
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
        const bars = lane.extraBars || [];
        this.setData({ overlayVisible: true, overlayLabel: label, overlayBars: bars });
    },
    onPriorityTap(e) {
        const priority = e.currentTarget.dataset.priority;
        if (!priority || priority === this.data.activePriority)
            return;
        const swim = this.data.swim;
        if (!swim)
            return;
        this.setData({
            activePriority: priority,
            swim: applyPriorityView(swim, priority),
            overlayVisible: false,
            chipTooltipVisible: false,
        });
    },
    hideOverlay() {
        this.setData({ overlayVisible: false });
    },
    hideChipTooltip() {
        this.setData({ chipTooltipVisible: false });
    },
    goUnit(e) {
        const id = e.currentTarget.dataset.id;
        (0, router_1.navigateTo)(router_1.ROUTES.dynastyDetail, { unitId: id });
    },
    goNext() {
        const n = this.data.nextUnit;
        if (!(n === null || n === void 0 ? void 0 : n.unitId))
            return;
        (0, router_1.navigateTo)(router_1.ROUTES.dynastyDetail, { unitId: n.unitId, dynasty: n.title });
    },
    openIntro() {
        if (!this.data.introCanExpand)
            return;
        this.setData({ showIntroModal: true, introModalTitle: (this.data.dynastyTitle || '') + '·朝代简介' });
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
