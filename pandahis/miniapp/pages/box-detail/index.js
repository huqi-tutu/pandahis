"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const api_1 = require("../../native-utils/api");
const box_narration_1 = require("../../native-utils/box-narration");
const encode_path_segment_1 = require("../../native-utils/encode-path-segment");
const query_value_1 = require("../../native-utils/query-value");
const favorite_box_1 = require("../../native-utils/favorite-box");
const year_format_1 = require("../../native-utils/year-format");
const router_1 = require("../../native-utils/router");
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
    return (0, year_format_1.formatHistoryYear)(y);
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
function parseBoldSegments(text) {
    const parts = text.split(/(\*\*[^*]*\*\*)/);
    return parts.filter(Boolean).map((p) => {
        if (p.startsWith('**') && p.endsWith('**')) {
            return { text: p.slice(2, -2), bold: true };
        }
        return { text: p, bold: false };
    });
}
/** 中文/英文/常用标点字符集合（用于剔除首段开头标点） */
const LEADING_PUNCTUATION = new Set('《》「」『』【】（）()。，、！？；：""\'\'…—·.．,，\'·：；！？、，。');
function stripLeadingPunctuation(text) {
    let start = 0;
    while (start < text.length && LEADING_PUNCTUATION.has(text[start])) {
        start++;
    }
    return text.slice(start);
}
function findDropcap(segs) {
    var _a;
    for (let si = 0; si < segs.length; si++) {
        for (let ci = 0; ci < segs[si].text.length; ci++) {
            const ch = segs[si].text[ci];
            if (/[\u4e00-\u9fff\u3400-\u4dbf\w]/.test(ch)) {
                return { ch, si, ci };
            }
        }
    }
    const first = ((_a = segs[0]) === null || _a === void 0 ? void 0 : _a.text) || '';
    return { ch: first[0] || '', si: 0, ci: 0 };
}
function splitDetailParagraphs(md) {
    const raw = String(md || '').trim();
    if (!raw)
        return [];
    const parts = raw.split(/\n{2,}/).map((s) => s.trim()).filter(Boolean);
    const list = parts.length ? parts : [raw];
    return list.map((p, i) => {
        // 首段：剔除开头的标点符号，确保 dropcap 始终是正常文字
        let processed = i === 0 ? stripLeadingPunctuation(p) : p;
        const segs = parseBoldSegments(processed);
        const plain = segs.map((s) => s.text).join('');
        const para = { segs, plain };
        if (i === 0) {
            const dc = findDropcap(segs);
            para.dropcap = dc.ch;
            if (segs[dc.si]) {
                const seg = segs[dc.si];
                seg.text = seg.text.slice(0, dc.ci) + seg.text.slice(dc.ci + 1);
            }
        }
        return para;
    });
}
Page({
    data: {
        boxId: '',
        navTitle: '史略详情',
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
        audioTitle: '',
        audioActivePara: -1,
        audioSpeed: 1,
        audioSpeedLabel: '1x',
        audioTimeRange: '',
        audioCategoryPath: '',
        graphScaleLabel: '100%',
        readingProgress: 0,
        uiFocused: true,
        bodyScrollTop: 0,
        showOriginal: false,
        originalTitle: '',
        originalItems: [],
        originalFallback: '',
        originalEmpty: true,
        originalLoading: false,
    },
    _detailScrollTop: 0,
    _tabBarPx: 0,
    _suppressChromeHide: false,
    _suppressChromeHideTimer: null,
    _rawOriginalRef: null,
    onUnload() {
        if (this._suppressChromeHideTimer) {
            clearTimeout(this._suppressChromeHideTimer);
            this._suppressChromeHideTimer = null;
        }
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
        const provisionalTitle = (0, query_value_1.decodeQueryValue)(query.title || query.displayName);
        const sys = wx.getSystemInfoSync();
        const navH = Math.round(88 * (sys.windowWidth / 750));
        const tabTop = (sys.statusBarHeight || 20) + navH;
        const tabBarPx = Math.round(72 * (sys.windowWidth / 750));
        const bodyTop = tabTop + tabBarPx;
        const graphCanvasH = Math.max(400, Math.floor((sys.windowHeight || 667) - bodyTop - 40));
        this._tabBarPx = tabBarPx;
        this.setData({
            boxId,
            navTitle: provisionalTitle || '史略详情',
            tabTop,
            bodyTop,
            graphCanvasH,
        });
        try {
            const res = await (0, api_1.request)(`/boxes/${(0, encode_path_segment_1.encodePathSegment)(boxId)}`);
            const header = res.data;
            const y0 = yearLabel(header.box.startYear);
            const y1 = yearLabel(header.box.endYear);
            const timeRange = y0 && y1 ? y0 + ' — ' + y1 : (y0 || y1 || '');
            const blurbClean = stripLeadingPunctuation(header.box.blurb || '');
            this.setData({
                header,
                navTitle: header.box.title,
                detailMetaDisplay: buildDetailMetaFromBox(header.box),
                audioTimeRange: timeRange,
                audioCategoryPath: [header.box.civilization_name, header.box.dynasty_name].filter(Boolean).join(' · '),
                blurbSegs: parseBoldSegments(blurbClean),
                blurbDropcap: (() => {
                    const segs = parseBoldSegments(blurbClean);
                    const dc = findDropcap(segs);
                    return dc.ch;
                })(),
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
                content: '登录后可开通会员或使用阅读点查看评述、见证与原文。',
                confirmText: '去登录',
                success: (r) => {
                    if (r.confirm)
                        (0, router_1.navigateTo)(router_1.ROUTES.login);
                },
            });
            return;
        }
        if (reason === 'INSUFFICIENT_READS' ||
            reason === 'NEED_MEMBERSHIP_OR_READS' ||
            action === 'OPEN_INVITE_PAGE' ||
            action === 'OPEN_MEMBERSHIP_PAGE') {
            wx.showModal({
                title: '需要会员或阅读点',
                content: '开通会员可免扣点阅读评述、见证与原文；也可邀友助力免费领季卡，或在设置中查看阅读点。',
                confirmText: '去开通',
                success: (r) => {
                    if (r.confirm)
                        wx.switchTab({ url: router_1.ROUTES.membership });
                },
            });
        }
    },
    async ensureTab(tab) {
        var _a;
        const boxId = this.data.boxId;
        const enc = (0, encode_path_segment_1.encodePathSegment)(boxId);
        if (tab === 'content') {
            if (this.data.detailFetched)
                return;
            try {
                const res = await (0, api_1.request)(`/boxes/${enc}/detail`);
                const md = res.data.detailMd || '';
                const parsed = splitDetailParagraphs(md);
                this.setData({
                    detailMd: md,
                    detailParagraphs: parsed,
                    detailErr: '',
                    detailReady: true,
                    detailFetched: true,
                });
                this._rawOriginalRef = (_a = res.data.originalRef) !== null && _a !== void 0 ? _a : null;
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
                else if (msg.includes('INSUFFICIENT_READS') || msg.includes('NEED_MEMBERSHIP_OR_READS')) {
                    err = '需要会员或阅读点，请前往「会员」页开通或邀友助力';
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
                else if (msg.includes('INSUFFICIENT_READS') || msg.includes('NEED_MEMBERSHIP_OR_READS')) {
                    err = '需要会员或阅读点，请前往「会员」页开通或邀友助力';
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
    setTab(e) {
        const tab = e.currentTarget.dataset.tab;
        if (tab === this.data.tab)
            return;
        const nextScrollTop = this.data.bodyScrollTop === 0 ? 0.01 : 0;
        // 防止同一次点击冒泡到 onPageTap 后又被切成阅读全屏态
        this._ignoreTapFromBar = true;
        this._detailScrollTop = 0;
        this._suppressChromeHide = true;
        if (this._suppressChromeHideTimer) {
            clearTimeout(this._suppressChromeHideTimer);
        }
        this._suppressChromeHideTimer = setTimeout(() => {
            this._suppressChromeHide = false;
            this._suppressChromeHideTimer = null;
        }, 280);
        this.setData({
            tab,
            uiFocused: true,
            readingProgress: 0,
            bodyScrollTop: nextScrollTop,
        }, () => {
            if (nextScrollTop !== 0) {
                this.setData({ bodyScrollTop: 0 });
            }
        });
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
            const audioTitle = this.data.detailMetaDisplay || this.data.navTitle || '史略解说';
            this.setData({ audioOpen: true, audioTitle });
            (0, box_narration_1.toggleNarrationPlayback)();
            this.setData({ narrationState: (0, box_narration_1.getNarrationState)() });
            return;
        }
        if (cur === 'loading') {
            wx.showToast({ title: '正在准备朗读…', icon: 'none', duration: 1500 });
            return;
        }
        if (!this.data.detailFetched) {
            await this.ensureTab('content');
        }
        const h = this.data.header;
        const script = (0, box_narration_1.buildBoxNarrationScript)({
            title: (_a = h === null || h === void 0 ? void 0 : h.box) === null || _a === void 0 ? void 0 : _a.title,
            meta: this.data.detailMetaDisplay,
            paragraphs: this.data.detailParagraphs.map((p) => p.plain),
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
            const audioTitle = this.data.detailMetaDisplay || this.data.navTitle || '史略解说';
            this.setData({ audioOpen: true, audioTitle, audioProgress: 0, audioCurrentTime: '0:00', audioDuration: '0:00', audioActivePara: -1 });
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
            this.setData({ narrationState: 'idle', audioOpen: false });
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
        const audioTitle = this.data.detailMetaDisplay || this.data.navTitle || '史略解说';
        this.setData({ audioOpen: true, audioTitle });
        if ((0, box_narration_1.getNarrationState)() === 'idle')
            void this.onPlayIntro();
    },
    toggleAudioPlayback() {
        (0, box_narration_1.toggleNarrationPlayback)();
        this.setData({ narrationState: (0, box_narration_1.getNarrationState)() });
    },
    onAudioSkipBack() {
        (0, box_narration_1.seekNarration)(-15);
    },
    onAudioSkipFwd() {
        (0, box_narration_1.seekNarration)(15);
    },
    _audioSeekStartX: 0,
    onAudioSeekStart() {
        this._audioSeekStartX = 0;
    },
    onAudioSeekMove(e) {
        var _a;
        const touch = (_a = e.touches) === null || _a === void 0 ? void 0 : _a[0];
        if (!touch)
            return;
        const query = wx.createSelectorQuery().in(this);
        query.select('.box-audio-scrub-track').boundingClientRect((rect) => {
            if (!rect || rect.width <= 0)
                return;
            const x = touch.clientX - rect.left;
            const ratio = Math.max(0, Math.min(1, x / rect.width));
            const pct = Math.round(ratio * 100);
            this.setData({ audioProgress: pct });
        }).exec();
    },
    onAudioSeekEnd(e) {
        var _a;
        const touch = (_a = e.changedTouches) === null || _a === void 0 ? void 0 : _a[0];
        if (!touch)
            return;
        const query = wx.createSelectorQuery().in(this);
        query.select('.box-audio-scrub-track').boundingClientRect((rect) => {
            if (!rect || rect.width <= 0)
                return;
            const x = touch.clientX - rect.left;
            const ratio = Math.max(0, Math.min(1, x / rect.width));
            const pct = Math.round(ratio * 100);
            (0, box_narration_1.seekNarrationPct)(pct);
        }).exec();
    },
    onSpeedToggle() {
        const speeds = [0.75, 1, 1.25, 1.5, 2];
        const cur = this.data.audioSpeed;
        let idx = speeds.indexOf(cur);
        if (idx === -1 || idx === speeds.length - 1)
            idx = 0;
        else
            idx += 1;
        const next = speeds[idx];
        (0, box_narration_1.setPlaybackRate)(next);
        this.setData({ audioSpeed: next, audioSpeedLabel: next + 'x' });
        wx.showToast({ title: '倍速 ' + next + 'x', icon: 'none', duration: 1200 });
    },
    formatGraphScaleLabel(scale) {
        return `${Math.round((scale || 1) * 100)}%`;
    },
    refreshGraphScaleLabel() {
        var _a, _b;
        const c = this.selectComponent('#bdRelationGraph');
        const scale = (_b = (_a = c === null || c === void 0 ? void 0 : c.getZoomScale) === null || _a === void 0 ? void 0 : _a.call(c)) !== null && _b !== void 0 ? _b : 1;
        this.setData({ graphScaleLabel: this.formatGraphScaleLabel(scale) });
    },
    /** 解析原文引用（同 pages/original-text） */
    _parseOriginalRef(ref) {
        var _a, _b, _c, _d;
        if (ref == null || (Array.isArray(ref) && ref.length === 0) || (typeof ref === 'object' && Object.keys(ref).length === 0))
            return null;
        if (typeof ref === 'string') {
            const t = ref.trim();
            return t ? { title: '原文', items: [], fallback: t } : null;
        }
        if (typeof ref !== 'object' || ref === null)
            return null;
        const o = ref;
        const textField = typeof o.text === 'string' ? o.text.trim() : '';
        if (textField) {
            const title = typeof o.title === 'string' && o.title.trim() ? o.title.trim() : '史料原文';
            return { title, items: [], fallback: textField };
        }
        const title = typeof o.title === 'string' && o.title.trim() ? o.title.trim() : '史料原文';
        const rawItems = o.items;
        const items = [];
        if (Array.isArray(rawItems)) {
            for (const it of rawItems) {
                if (!it || typeof it !== 'object')
                    continue;
                const x = it;
                items.push({
                    work: String((_a = x.work) !== null && _a !== void 0 ? _a : '').trim(),
                    chapter: String((_b = x.chapter) !== null && _b !== void 0 ? _b : '').trim(),
                    excerpt: String((_c = x.excerpt) !== null && _c !== void 0 ? _c : '').trim().replace(/\\r\\n/g, '\n').replace(/\\n/g, '\n'),
                    url: String((_d = x.url) !== null && _d !== void 0 ? _d : '').trim(),
                });
            }
        }
        const hasStructured = items.some((i) => i.work || i.chapter || i.excerpt || i.url);
        if (!hasStructured) {
            try {
                return { title, items: [], fallback: JSON.stringify(ref, null, 2) };
            }
            catch {
                return { title, items: [], fallback: String(ref) };
            }
        }
        return { title, items, fallback: '' };
    },
    goOriginal() {
        var _a, _b;
        const h = this.data.header;
        const o = (_b = (_a = h === null || h === void 0 ? void 0 : h.access) === null || _a === void 0 ? void 0 : _a.tabs) === null || _b === void 0 ? void 0 : _b.original;
        if (o === null || o === void 0 ? void 0 : o.locked) {
            this.promptLockedTab(o);
            return;
        }
        // 优先使用之前缓存的数据
        const ref = this._rawOriginalRef;
        if (ref != null) {
            const parsed = this._parseOriginalRef(ref);
            if (parsed && (parsed.items.length > 0 || parsed.fallback.length > 0)) {
                this.setData({
                    showOriginal: true,
                    originalTitle: parsed.title,
                    originalItems: parsed.items,
                    originalFallback: parsed.fallback,
                    originalEmpty: false,
                    originalLoading: false,
                });
                return;
            }
        }
        // 无缓存，重新请求
        this.setData({ showOriginal: true, originalLoading: true, originalEmpty: true });
        const run = async () => {
            try {
                const enc = (0, encode_path_segment_1.encodePathSegment)(this.data.boxId);
                const res = await (0, api_1.request)(`/boxes/${enc}/original-ref`, { auth: (0, api_1.hasToken)() });
                const parsed = this._parseOriginalRef(res.data.originalRef);
                if (!parsed || (!parsed.items.length && !parsed.fallback.length)) {
                    this.setData({ originalLoading: false, originalEmpty: true, originalTitle: '', originalItems: [], originalFallback: '' });
                    return;
                }
                this.setData({
                    originalLoading: false,
                    originalEmpty: false,
                    originalTitle: parsed.title,
                    originalItems: parsed.items,
                    originalFallback: parsed.fallback,
                });
            }
            catch (e) {
                const msg = String((e === null || e === void 0 ? void 0 : e.message) || '');
                if (msg.includes('INSUFFICIENT_READS') || msg.includes('NEED_MEMBERSHIP_OR_READS')) {
                    this.setData({ showOriginal: false });
                    wx.showModal({
                        title: '需要会员或阅读点',
                        content: '开通会员可免扣点阅读；也可去会员页邀友助力或查看阅读点。',
                        confirmText: '去开通',
                        success: (r) => { if (r.confirm)
                            wx.switchTab({ url: router_1.ROUTES.membership }); },
                    });
                }
                else {
                    this.setData({ originalLoading: false, originalEmpty: true });
                    wx.showToast({ title: '加载失败', icon: 'none' });
                }
            }
        };
        void run();
    },
    closeOriginal() {
        this.setData({ showOriginal: false });
    },
    copyOriginalLink(e) {
        var _a, _b;
        const url = (_b = (_a = e.currentTarget) === null || _a === void 0 ? void 0 : _a.dataset) === null || _b === void 0 ? void 0 : _b.url;
        if (url) {
            wx.setClipboardData({ data: url });
            wx.showToast({ title: '链接已复制', icon: 'success' });
        }
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
    /** 标记本次tap来自底部操作栏，阻止导航栏切换 */
    markTapFromBar() { this._ignoreTapFromBar = true; },
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
        var _a, _b;
        const scale = (_b = (_a = e.detail) === null || _a === void 0 ? void 0 : _a.scale) !== null && _b !== void 0 ? _b : 1;
        this.setData({ graphScaleLabel: this.formatGraphScaleLabel(scale) });
    },
    onDetailScroll(e) {
        var _a;
        const d = e.detail || { scrollTop: 0, scrollHeight: 0 };
        const scrollTop = d.scrollTop || 0;
        const scrollHeight = d.scrollHeight || 0;
        const sysInfo = wx.getSystemInfoSync();
        const bodyTop = this.data.bodyTop;
        const viewportH = sysInfo.windowHeight - bodyTop;
        const maxScroll = Math.max(scrollHeight - viewportH, 1);
        const pct = Math.min(Math.round((scrollTop / maxScroll) * 100), 100);
        this.setData({ readingProgress: pct });
        // 自动隐藏 tab 栏（仅详情 Tab），使用 CSS transition 实现无抖动显隐
        if (this.data.tab === 'content' && !this._suppressChromeHide) {
            const prevScrollTop = (_a = this._detailScrollTop) !== null && _a !== void 0 ? _a : 0;
            const delta = scrollTop - prevScrollTop;
            this._detailScrollTop = scrollTop;
            if (scrollTop <= 5) {
                // 顶部自动显示
                if (!this.data.uiFocused)
                    this.setData({ uiFocused: true });
            }
            else if (delta > 5) {
                // 下划 > 5px 隐藏
                if (this.data.uiFocused)
                    this.setData({ uiFocused: false });
            }
            else if (delta < -5) {
                // 上划 > 5px 显示
                if (!this.data.uiFocused)
                    this.setData({ uiFocused: true });
            }
        }
        else if (this.data.tab === 'content') {
            this._detailScrollTop = scrollTop;
        }
    },
    /** 切换 tab 栏显隐（悬浮 overlay，不影响正文布局，无跳变） */
    onToggleUI(focused) {
        if (this.data.tab !== 'content')
            return;
        this.setData({ uiFocused: focused });
    },
    /** 点击屏幕切换导航栏显隐 */
    onPageTap() {
        if (this.data.showOriginal)
            return;
        if (this.data.tab === 'content' && !this._ignoreTapFromBar) {
            this.onToggleUI(!this.data.uiFocused);
        }
        this._ignoreTapFromBar = false;
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
