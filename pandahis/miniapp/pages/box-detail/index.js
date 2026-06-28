"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const api_1 = require("../../native-utils/api");
const encode_path_segment_1 = require("../../native-utils/encode-path-segment");
const favorite_box_1 = require("../../native-utils/favorite-box");
const router_1 = require("../../native-utils/router");
const box_narration_1 = require("../../native-utils/box-narration");
const share_invite_1 = require("../../native-utils/share-invite");
function relicThumbLabel(name) {
    const n = (name || '').trim();
    if (!n)
        return '—';
    if (n.length <= 4)
        return n;
    return n.slice(-4);
}
function mapCritiqueItems(raw) {
    return (raw || []).map((it, idx) => {
        const author = String(it.author || '').trim();
        const title = String(it.title || '').trim();
        const displayAuthor = author || title || '佚名';
        const era = String(it.eraText || '').trim();
        const yv = it.year;
        const y = yv != null && yv !== '' ? Number(yv) : NaN;
        const yearStr = Number.isFinite(y) && y !== 0 ? String(y) : '';
        const eraMeta = [era, yearStr].filter(Boolean).join(' · ');
        const content = String(it.content || '').trim();
        const blurb = String(it.blurb || '').trim();
        const bodyQuote = content || blurb;
        const source = String(it.source || it.book || '').trim();
        const cardTitle = title || displayAuthor;
        const cardMeta = [author, eraMeta, source].filter(Boolean).join(' · ');
        return {
            ...it,
            displayAuthor,
            eraMeta,
            bodyQuote,
            avatarLetter: displayAuthor.charAt(0) || '评',
            cardTitle,
            cardMeta,
            cardSummary: bodyQuote,
            _k: idx,
        };
    });
}
function mapRelicItems(raw) {
    return (raw || []).slice(0, 3).map((it) => {
        const teaser = String(it.summary || it.description || '').trim();
        const museum = it.museum || '馆藏待补充';
        return {
            name: it.name || '',
            imageUrl: it.imageUrl,
            summary: teaser,
            description: it.description,
            museum,
            priorityCode: it.priorityCode,
            thumbLabel: relicThumbLabel(it.name || ''),
            teaser,
            location: museum,
        };
    });
}
function formatDetailMetaLine(subText) {
    return String(subText || '')
        .replace(/\s*~\s*/g, ' — ')
        .replace(/~/g, '—')
        .replace(/\s*·\s*/g, ' · ')
        .trim();
}
function yearLabel(y) {
    if (!Number.isFinite(y) || y === 0)
        return '';
    return y < 0 ? `前${Math.abs(y)}` : String(y);
}
function buildDetailMetaFromBox(box) {
    const fromSub = formatDetailMetaLine(box.subText);
    if (fromSub)
        return fromSub;
    const parts = [];
    const y0 = yearLabel(box.startYear);
    const y1 = yearLabel(box.endYear);
    if (y0 && y1 && y0 !== y1)
        parts.push(`${y0} — ${y1}`);
    else if (y0)
        parts.push(y0);
    return parts.join(' · ');
}
function splitDetailParagraphs(md) {
    const raw = String(md || '').trim();
    if (!raw)
        return [];
    const parts = raw.split(/\n{2,}/).map((s) => s.trim()).filter(Boolean);
    return parts.length ? parts : [raw];
}
const ASSIST_ACTION_DEFS = [
    { key: 'original', label: '原文', icon: '/images/icons/yuanwen.png', angle: 5 },
    { key: 'play', label: '播放', icon: '/images/icons/bofang.png', angle: 42 },
    { key: 'fav', label: '收藏', icon: '/images/icons/shoucangA.png', angle: 79 },
    { key: 'share', label: '分享', icon: '/images/icons/fenxiang.png', angle: 116 },
];
function buildAssistMetrics(sys, bodyTop) {
    const margin = Math.round(32 * (sys.windowWidth / 750));
    const dotSize = Math.round(88 * (sys.windowWidth / 750));
    const menuRadius = Math.round(228 * (sys.windowWidth / 750));
    return {
        margin,
        menuRadius,
        minX: margin,
        minY: bodyTop + margin,
        maxX: sys.windowWidth - margin - dotSize,
        maxY: sys.windowHeight - margin - dotSize,
    };
}
function defaultAssistPosition(metrics, sys) {
    const x = Math.round(sys.windowWidth * 0.25);
    const availableH = sys.windowHeight - metrics.minY;
    const y = Math.round(metrics.minY + availableH * 0.72);
    return clampAssistPosition(x, y, metrics);
}
function clampAssistPosition(x, y, metrics) {
    return {
        x: Math.min(metrics.maxX, Math.max(metrics.minX, x)),
        y: Math.min(metrics.maxY, Math.max(metrics.minY, y)),
    };
}
function buildAssistMenuItems(open, menuRadius) {
    return ASSIST_ACTION_DEFS.map((def, idx) => {
        const rad = (def.angle * Math.PI) / 180;
        const dx = open ? Math.round(Math.cos(rad) * menuRadius) : 0;
        const dy = open ? Math.round(-Math.sin(rad) * menuRadius) : 0;
        return {
            key: def.key,
            label: def.label,
            icon: def.icon,
            dx,
            dy,
            delay: open ? idx * 30 : 0,
        };
    });
}
Page({
    data: {
        boxId: '',
        navTitle: '史略盒子',
        header: null,
        tabTop: 88,
        bodyTop: 160,
        graphCanvasH: 400,
        critColors: ['#92ADA4', '#C9825A', '#7BA87B', '#B85A5A', '#84572F', '#5A8FA8'],
        tab: 'content',
        isFav: false,
        detailMd: '',
        detailParagraphs: [],
        detailMetaDisplay: '',
        detailReady: false,
        detailErr: '',
        graph: { centerNodeKey: '', nodes: [], edges: [] },
        graphReady: false,
        graphErr: '',
        critiques: [],
        critReady: false,
        critErr: '',
        relics: [],
        relicReady: false,
        relicErr: '',
        detailFetched: false,
        graphFetched: false,
        critFetched: false,
        relicFetched: false,
        narrationState: 'idle',
        audioOpen: false,
        audioProgress: 0,
        audioCurrentTime: '0:00',
        audioDuration: '0:00',
        graphScaleLabel: '100%',
        assistOpen: false,
        assistDragging: false,
        assistX: 24,
        assistY: 560,
        assistMenuItems: [],
    },
    _assistMetrics: null,
    _assistTouch: null,
    onUnload() {
        (0, box_narration_1.stopNarration)();
        this.setData({ audioOpen: false });
    },
    onShareAppMessage() {
        var _a;
        const h = this.data.header;
        const id = this.data.boxId;
        const title = ((_a = h === null || h === void 0 ? void 0 : h.box) === null || _a === void 0 ? void 0 : _a.title) || '史略详情';
        const path = id ? `/pages/box-detail/index?boxId=${encodeURIComponent(id)}` : '/pages/box-detail/index';
        return { title, path };
    },
    onShareTap() {
        (0, share_invite_1.promptContentShareUnavailable)();
    },
    async onLoad(query) {
        const boxId = query.boxId || query.id;
        if (!boxId)
            return;
        const sys = wx.getSystemInfoSync();
        const navH = Math.round(88 * (sys.windowWidth / 750));
        const tabTop = (sys.statusBarHeight || 20) + navH;
        const tabBarPx = Math.round(72 * (sys.windowWidth / 750));
        const bodyTop = tabTop + tabBarPx;
        const graphCanvasH = Math.max(400, Math.floor((sys.windowHeight || 667) - bodyTop - 40));
        const assistMetrics = buildAssistMetrics(sys, bodyTop);
        const assistPos = defaultAssistPosition(assistMetrics, sys);
        this._assistMetrics = assistMetrics;
        this.setData({
            boxId,
            tabTop,
            bodyTop,
            graphCanvasH,
            assistX: assistPos.x,
            assistY: assistPos.y,
            assistMenuItems: buildAssistMenuItems(false, assistMetrics.menuRadius),
        });
        try {
            const res = await (0, api_1.request)(`/boxes/${(0, encode_path_segment_1.encodePathSegment)(boxId)}`);
            const header = res.data;
            this.setData({
                header,
                navTitle: header.box.title,
                detailMetaDisplay: buildDetailMetaFromBox(header.box),
            });
            await this.refreshFavState();
            await this.recordFootprint();
            await this.ensureTab('content');
        }
        catch (e) {
            wx.showToast({ title: (e === null || e === void 0 ? void 0 : e.message) || '加载失败', icon: 'none' });
        }
    },
    async recordFootprint() {
        if (!(0, api_1.hasToken)())
            return;
        const boxId = this.data.boxId;
        try {
            await (0, api_1.request)(`/footprints/boxes/${(0, encode_path_segment_1.encodePathSegment)(boxId)}/view`, { method: 'POST', auth: true });
        }
        catch {
            // 静默失败
        }
    },
    async refreshFavState() {
        const boxId = this.data.boxId;
        if (!(0, api_1.hasToken)()) {
            this.setData({ isFav: false });
            return;
        }
        const favorited = await (0, favorite_box_1.fetchFavoritedBoxIdSet)();
        this.setData({ isFav: favorited.has(boxId) });
    },
    promptLockedTab(access) {
        var _a;
        const reason = (access === null || access === void 0 ? void 0 : access.lockedReason) || '';
        const action = ((_a = access === null || access === void 0 ? void 0 : access.unlockAction) === null || _a === void 0 ? void 0 : _a.type) || '';
        if (reason === 'LOGIN_REQUIRED' || action === 'OPEN_LOGIN') {
            wx.showModal({
                title: '需要登录',
                content: '登录后可使用阅读点数查看评述、见证与原文。',
                confirmText: '去登录',
                success: (r) => {
                    if (r.confirm)
                        (0, router_1.navigateTo)(router_1.ROUTES.login);
                },
            });
            return;
        }
        if (reason === 'INSUFFICIENT_READS' || action === 'OPEN_INVITE_PAGE') {
            wx.showModal({
                title: '阅读点数不足',
                content: '邀请好友注册可获得阅读点数（每位新用户 +10 点）。',
                confirmText: '去邀请',
                success: (r) => {
                    if (r.confirm)
                        wx.switchTab({ url: router_1.ROUTES.invite });
                },
            });
        }
    },
    async ensureTab(tab) {
        const boxId = this.data.boxId;
        const enc = (0, encode_path_segment_1.encodePathSegment)(boxId);
        if (tab === 'content') {
            if (this.data.detailFetched)
                return;
            try {
                const res = await (0, api_1.request)(`/boxes/${enc}/detail`);
                const md = res.data.detailMd || '';
                this.setData({
                    detailMd: md,
                    detailParagraphs: splitDetailParagraphs(md),
                    detailErr: '',
                    detailReady: true,
                    detailFetched: true,
                });
            }
            catch (e) {
                this.setData({
                    detailErr: (e === null || e === void 0 ? void 0 : e.message) || '加载失败',
                    detailMd: '',
                    detailParagraphs: [],
                    detailReady: true,
                    detailFetched: true,
                });
            }
            return;
        }
        if (tab === 'relations') {
            if (this.data.graphFetched)
                return;
            try {
                const res = await (0, api_1.request)(`/boxes/${enc}/graph`);
                this.setData({
                    graph: {
                        centerNodeKey: res.data.centerNodeKey || '',
                        nodes: res.data.nodes || [],
                        edges: res.data.edges || [],
                    },
                    graphErr: '',
                    graphReady: true,
                    graphFetched: true,
                    graphScaleLabel: '100%',
                });
            }
            catch (e) {
                this.setData({
                    graphErr: (e === null || e === void 0 ? void 0 : e.message) || '加载失败',
                    graph: { centerNodeKey: '', nodes: [], edges: [] },
                    graphReady: true,
                    graphFetched: true,
                });
            }
            return;
        }
        if (tab === 'reviews') {
            if (this.data.critFetched)
                return;
            try {
                const res = await (0, api_1.request)(`/boxes/${enc}/critiques`);
                this.setData({
                    critiques: mapCritiqueItems(res.data.items || []),
                    critErr: '',
                    critReady: true,
                    critFetched: true,
                });
            }
            catch (e) {
                const msg = String((e === null || e === void 0 ? void 0 : e.message) || '');
                let err = msg || '加载失败';
                if (msg === 'UNAUTHORIZED' || msg.includes('login required')) {
                    err = '请先登录后查看评述';
                }
                else if (msg.includes('INSUFFICIENT_READS')) {
                    err = '阅读点数不足，去「邀请」页邀请好友可获得点数';
                }
                this.setData({
                    critiques: [],
                    critErr: err,
                    critReady: true,
                    critFetched: true,
                });
            }
            return;
        }
        if (tab === 'relics') {
            if (this.data.relicFetched)
                return;
            try {
                const res = await (0, api_1.request)(`/boxes/${enc}/relics`);
                const items = mapRelicItems(res.data.items || []);
                this.setData({ relics: items, relicErr: '', relicReady: true, relicFetched: true });
            }
            catch (e) {
                const msg = String((e === null || e === void 0 ? void 0 : e.message) || '');
                let err = msg || '加载失败';
                if (msg === 'UNAUTHORIZED' || msg.includes('login required')) {
                    err = '请先登录后查看见证';
                }
                else if (msg.includes('INSUFFICIENT_READS')) {
                    err = '阅读点数不足，去「邀请」页邀请好友可获得点数';
                }
                this.setData({
                    relics: [],
                    relicErr: err,
                    relicReady: true,
                    relicFetched: true,
                });
            }
        }
    },
    setAssistOpen(open) {
        const metrics = this._assistMetrics;
        const menuRadius = (metrics === null || metrics === void 0 ? void 0 : metrics.menuRadius) ?? 60;
        this.setData({
            assistOpen: open,
            assistMenuItems: buildAssistMenuItems(open, menuRadius),
        });
    },
    onAssistTouchStart(e) {
        const touch = e.touches[0];
        if (!touch)
            return;
        this._assistTouch = {
            startX: touch.clientX,
            startY: touch.clientY,
            originX: this.data.assistX,
            originY: this.data.assistY,
            moved: false,
        };
        this.setData({ assistDragging: false });
    },
    onAssistTouchMove(e) {
        const touch = e.touches[0];
        const state = this._assistTouch;
        const metrics = this._assistMetrics;
        if (!touch || !state || !metrics)
            return;
        const dx = touch.clientX - state.startX;
        const dy = touch.clientY - state.startY;
        if (!state.moved && Math.hypot(dx, dy) < 8)
            return;
        state.moved = true;
        const next = clampAssistPosition(state.originX + dx, state.originY + dy, metrics);
        if (this.data.assistOpen) {
            this.setAssistOpen(false);
        }
        this.setData({ assistDragging: true, assistX: next.x, assistY: next.y });
    },
    onAssistTouchEnd() {
        const state = this._assistTouch;
        this._assistTouch = null;
        if (!state)
            return;
        if (state.moved) {
            this.setData({ assistDragging: false });
            return;
        }
        this.setAssistOpen(!this.data.assistOpen);
        this.setData({ assistDragging: false });
    },
    onAssistAction(e) {
        const action = e.currentTarget.dataset.action;
        this.setAssistOpen(false);
        if (action === 'original') {
            this.goOriginal();
            return;
        }
        if (action === 'play') {
            void this.onPlayIntro();
            return;
        }
        if (action === 'fav') {
            this.toggleFav();
            return;
        }
        if (action === 'share') {
            this.onShareTap();
        }
    },
    setTab(e) {
        const tab = e.currentTarget.dataset.tab;
        if (tab !== 'content' && this.data.assistOpen) {
            this.setAssistOpen(false);
        }
        this.setData({ tab });
        void this.ensureTab(tab);
    },
    onCritiqueTap(e) {
        const idx = Number(e.currentTarget.dataset.idx);
        const list = this.data.critiques;
        const c = list[idx];
        if (!c)
            return;
        const body = [c.content, c.blurb, c.bodyQuote, c.source].filter(Boolean).join('\n\n');
        (0, router_1.navigateTo)(router_1.ROUTES.critiqueDetail, {
            title: c.title || '',
            author: c.displayAuthor || '',
            book: c.source || '',
            era: c.eraMeta || '',
            body,
        });
    },
    onRelicTap(e) {
        const idx = Number(e.currentTarget.dataset.idx);
        const list = this.data.relics;
        const r = list[idx];
        if (!r)
            return;
        (0, router_1.navigateTo)(router_1.ROUTES.relicDetail, {
            name: r.name || '',
            museum: r.museum || '',
            detail: [r.teaser, r.description].filter(Boolean).join('\n\n'),
            imageUrl: r.imageUrl || '',
        });
    },
    async onPlayIntro() {
        var _a, _b;
        const cur = (0, box_narration_1.getNarrationState)();
        if (cur === 'playing' || cur === 'paused') {
            this.setData({ audioOpen: true });
            (0, box_narration_1.toggleNarrationPlayback)();
            this.setData({ narrationState: (0, box_narration_1.getNarrationState)() });
            return;
        }
        if (cur === 'loading') {
            (0, box_narration_1.stopNarration)();
            this.setData({ narrationState: 'idle' });
            wx.hideLoading();
            return;
        }
        if (!this.data.detailFetched) {
            await this.ensureTab('content');
        }
        const h = this.data.header;
        const script = (0, box_narration_1.buildBoxNarrationScript)({
            title: (_a = h === null || h === void 0 ? void 0 : h.box) === null || _a === void 0 ? void 0 : _a.title,
            meta: this.data.detailMetaDisplay,
            paragraphs: this.data.detailParagraphs,
            blurb: (_b = h === null || h === void 0 ? void 0 : h.box) === null || _b === void 0 ? void 0 : _b.blurb,
        });
        if (!script.trim()) {
            wx.showToast({ title: '暂无正文可朗读', icon: 'none' });
            return;
        }
        let loadingVisible = false;
        try {
            wx.showLoading({ title: '正在准备朗读', mask: true });
            loadingVisible = true;
            this.setData({ audioOpen: true, audioProgress: 0, audioCurrentTime: '0:00', audioDuration: '0:00' });
            await (0, box_narration_1.startNarration)(script, (s) => {
                if (s === 'playing' && loadingVisible) {
                    wx.hideLoading();
                    loadingVisible = false;
                }
                if (s === 'idle') {
                    this.setData({ audioOpen: false, audioProgress: 0 });
                }
                this.setData({ narrationState: s });
            }, (p) => {
                this.setData({
                    audioProgress: p.progress,
                    audioCurrentTime: p.current,
                    audioDuration: p.duration,
                });
            });
        }
        catch (e) {
            const msg = e instanceof Error ? e.message : '朗读失败';
            wx.showToast({ title: msg.slice(0, 28), icon: 'none', duration: 2800 });
            this.setData({ narrationState: 'idle' });
        }
        finally {
            if (loadingVisible)
                wx.hideLoading();
        }
    },
    toggleAudioOverlay() {
        const open = !this.data.audioOpen;
        if (!open) {
            (0, box_narration_1.stopNarration)();
            this.setData({ audioOpen: false, narrationState: 'idle', audioProgress: 0 });
            return;
        }
        this.setData({ audioOpen: true });
        if ((0, box_narration_1.getNarrationState)() === 'idle')
            void this.onPlayIntro();
    },
    toggleAudioPlayback() {
        (0, box_narration_1.toggleNarrationPlayback)();
        this.setData({ narrationState: (0, box_narration_1.getNarrationState)() });
    },
    formatGraphScaleLabel(scale) {
        return `${Math.round((scale || 1) * 100)}%`;
    },
    refreshGraphScaleLabel() {
        const c = this.selectComponent('#bdRelationGraph');
        const scale = (c === null || c === void 0 ? void 0 : c.getZoomScale) ? c.getZoomScale() : 1;
        this.setData({ graphScaleLabel: this.formatGraphScaleLabel(scale) });
    },
    goOriginal() {
        var _a, _b;
        const h = this.data.header;
        const o = (_b = (_a = h === null || h === void 0 ? void 0 : h.access) === null || _a === void 0 ? void 0 : _a.tabs) === null || _b === void 0 ? void 0 : _b.original;
        if (o === null || o === void 0 ? void 0 : o.locked) {
            this.promptLockedTab(o);
            return;
        }
        (0, router_1.navigateTo)(router_1.ROUTES.originalText, { boxId: this.data.boxId });
    },
    onGraphNodeTap(e) {
        var _a, _b;
        const key = (_a = e.detail) === null || _a === void 0 ? void 0 : _a.key;
        const targetId = (_b = e.detail) === null || _b === void 0 ? void 0 : _b.targetBoxId;
        const boxId = this.data.boxId;
        if (targetId && targetId !== boxId) {
            (0, router_1.navigateTo)(router_1.ROUTES.boxDetail, { boxId: targetId });
            return;
        }
        if (key && boxId) {
            (0, router_1.navigateTo)(router_1.ROUTES.relationDetail, { boxId, nodeKey: key });
        }
    },
    noop() { },
    onGraphZoomIn() {
        var _a;
        const c = this.selectComponent('#bdRelationGraph');
        (_a = c === null || c === void 0 ? void 0 : c.zoomIn) === null || _a === void 0 ? void 0 : _a.call(c);
        this.refreshGraphScaleLabel();
    },
    onGraphZoomOut() {
        var _a;
        const c = this.selectComponent('#bdRelationGraph');
        (_a = c === null || c === void 0 ? void 0 : c.zoomOut) === null || _a === void 0 ? void 0 : _a.call(c);
        this.refreshGraphScaleLabel();
    },
    onGraphZoomReset() {
        var _a;
        const c = this.selectComponent('#bdRelationGraph');
        (_a = c === null || c === void 0 ? void 0 : c.resetZoom) === null || _a === void 0 ? void 0 : _a.call(c);
        this.refreshGraphScaleLabel();
    },
    onGraphZoomChange(e) {
        var _a;
        const scale = (_a = e.detail) === null || _a === void 0 ? void 0 : _a.scale;
        this.setData({ graphScaleLabel: this.formatGraphScaleLabel(scale !== null && scale !== void 0 ? scale : 1) });
    },
    toggleFav() {
        if (!(0, api_1.hasToken)()) {
            (0, favorite_box_1.promptLoginForFavorite)();
            return;
        }
        const boxId = this.data.boxId;
        const next = !this.data.isFav;
        const run = async () => {
            try {
                if (next) {
                    await (0, favorite_box_1.favoriteBox)(boxId);
                    wx.showToast({ title: '已收藏', icon: 'success' });
                }
                else {
                    await (0, favorite_box_1.unfavoriteBox)(boxId);
                    wx.showToast({ title: '已取消收藏', icon: 'success' });
                }
                await this.refreshFavState();
            }
            catch (e) {
                const msg = e instanceof Error ? e.message : '操作失败';
                wx.showToast({ title: msg, icon: 'none' });
            }
        };
        void run();
    },
});
