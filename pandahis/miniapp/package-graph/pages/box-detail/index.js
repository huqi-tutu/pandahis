"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const api_1 = require("../../../native-utils/api");
const box_reading_progress_1 = require("../../../native-utils/box-reading-progress");
const box_narration_1 = require("../../../native-utils/box-narration");
const encode_path_segment_1 = require("../../../native-utils/encode-path-segment");
const query_value_1 = require("../../../native-utils/query-value");
const favorite_box_1 = require("../../../native-utils/favorite-box");
const year_format_1 = require("../../../native-utils/year-format");
const router_1 = require("../../../native-utils/router");
const share_poster_open_1 = require("../../../native-utils/share-poster-open");
const correction_1 = require("../../../native-utils/correction");
const note_1 = require("../../../native-utils/note");
const note_highlight_1 = require("../../../native-utils/note-highlight");
const category_label_1 = require("../../../native-utils/category-label");
const read_complete_1 = require("../../../native-utils/read-complete");
const selection_bar_position_1 = require("../../../native-utils/selection-bar-position");
const brand_assets_1 = require("../../../native-utils/brand-assets");
const box_detail_search_1 = require("../../../native-utils/box-detail-search");
const box_detail_search_history_1 = require("../../../native-utils/box-detail-search-history");
function relicThumbLabel(name) {
    const n = (name || '').trim();
    if (!n)
        return '—';
    if (n.length <= 4)
        return n;
    return n.slice(-4);
}
/** 从「史略名称·评述角度」取 · 后的评述角度 */
function critiqueAngleTitle(fullTitle) {
    const t = String(fullTitle || '').trim();
    if (!t)
        return '';
    const dotIdx = t.indexOf('·');
    if (dotIdx >= 0) {
        const rest = t.slice(dotIdx + 1).trim();
        return rest || t;
    }
    return t;
}
const TRADITIONAL_DYNASTIES = [
    '北宋', '南宋', '西汉', '东汉', '南北朝',
    '战国末期', '战国', '春秋末期', '春秋', '五帝', '三皇', '上古',
    '东晋', '西晋', '三国', '五代', '魏晋',
    '夏', '商', '周', '秦', '隋', '唐', '宋', '元', '明', '清',
];
const MODERN_PERIOD_LABELS = [
    '近现代', '近代', '现代', '当代', '中华民国', '二十世纪', '20世纪',
];
function isYearLikeFragment(text) {
    const s = String(text || '').trim();
    if (!s)
        return false;
    return /^(约)?\s*公元前/u.test(s)
        || /^(约)?\s*[\d０-９]+/u.test(s)
        || /世纪|年代|^\d+年$/u.test(s);
}
/** 从评述年代取传统朝代（清及以前），去掉括号内年份与 · 后的具体时间 */
function critiqueDynastyLabel(eraText) {
    var _a;
    let s = String(eraText || '').trim();
    if (!s)
        return '';
    const trailing = s.match(/[（(]([^）)]+)[）)]\s*$/);
    const beforeParens = s.replace(/[（(][^）)]+[）)]/gu, '').trim();
    if (isYearLikeFragment(beforeParens) && trailing && isDynastyLikeLabel(trailing[1])) {
        s = trailing[1].trim();
    }
    else {
        s = s.replace(/[（(][^）)]+[）)]/gu, '').trim();
    }
    for (const sep of ['·', '・']) {
        if (s.includes(sep)) {
            const head = (_a = s.split(sep)[0]) === null || _a === void 0 ? void 0 : _a.trim();
            if (head) {
                s = head;
                break;
            }
        }
    }
    s = s.replace(/\s+约?公元前.*$/u, '').trim();
    s = s.replace(/[，,]\s*约?.*$/u, '').trim();
    s = s.replace(/\s+约?\d+.*$/u, '').trim();
    for (const d of [...TRADITIONAL_DYNASTIES, ...MODERN_PERIOD_LABELS].sort((a, b) => b.length - a.length)) {
        if (s === d || s.startsWith(d))
            return d;
    }
    const short = s.match(/^(清|明|元|宋|唐|隋|秦|周|商|夏)/u);
    if (short)
        return short[1];
    return s;
}
function isDynastyLikeLabel(text) {
    const s = String(text || '').trim();
    if (!s)
        return false;
    if ([...TRADITIONAL_DYNASTIES, ...MODERN_PERIOD_LABELS].some((d) => s === d || s.startsWith(d)))
        return true;
    return /^(春|战|西|东|南|北|五|三|上|近|现)/u.test(s);
}
function isTraditionalDynasty(label) {
    const s = String(label || '').trim();
    if (!s || isYearLikeFragment(s))
        return false;
    if (MODERN_PERIOD_LABELS.some((m) => s === m || s.startsWith(m)))
        return false;
    return TRADITIONAL_DYNASTIES.some((d) => s === d || s.startsWith(d))
        || /^(清|明|元|宋|唐|隋|秦|周|商|夏)/u.test(s);
}
/** 1912 年后无法归入传统朝代时，提取年份/世纪/年代 */
function critiqueYearLabel(eraText) {
    const raw = String(eraText || '').trim();
    if (!raw)
        return '';
    const parenParts = [];
    const parenRe = /[（(]([^）)]+)[）)]/gu;
    let parenMatch;
    while ((parenMatch = parenRe.exec(raw)) !== null) {
        const part = parenMatch[1].trim();
        if (isYearLikeFragment(part))
            parenParts.push(part);
    }
    if (parenParts.length) {
        const exact = parenParts.find((t) => /^\d+年$/u.test(t));
        if (exact)
            return exact;
        const withYear = parenParts.find((t) => /\d/u.test(t));
        if (withYear)
            return withYear.replace(/^约\s*/u, '约');
    }
    for (const sep of ['·', '・']) {
        if (raw.includes(sep)) {
            const tail = raw.split(sep).slice(1).join(sep).replace(/[（(][^）)]+[）)]/gu, '').trim();
            if (tail && isYearLikeFragment(tail))
                return tail.replace(/^约\s*/u, '约');
        }
    }
    const stripped = raw.replace(/[（(][^）)]+[）)]/gu, '').trim();
    if (isYearLikeFragment(stripped))
        return stripped.replace(/^约\s*/u, '约');
    const embedded = stripped.match(/(\d{4}年(?:代)?|20世纪[^\s，,）)]*|约?\d+世纪[^\s，,）)]*|\d{2,4}年代)/u);
    if (embedded)
        return embedded[1];
    return '';
}
/** 列表/详情时代展示：传统朝代只显示朝代；1912 年后只显示年份，不同时出现 */
function critiqueEraDisplay(eraText) {
    const era = String(eraText || '').trim();
    if (!era)
        return '';
    const dynasty = critiqueDynastyLabel(era);
    if (isTraditionalDynasty(dynasty))
        return dynasty;
    const year = critiqueYearLabel(era);
    if (year)
        return year;
    if (dynasty && !isYearLikeFragment(dynasty))
        return dynasty;
    return '';
}
function mapCritiqueItems(raw) {
    return (raw || []).map((it, idx) => {
        const idNum = Number(it.id);
        const author = String(it.author || '').trim();
        const title = String(it.title || '').trim();
        const angleTitle = critiqueAngleTitle(title);
        const displayAuthor = author || angleTitle || title || '佚名';
        const era = String(it.eraText || '').trim();
        const dynasty = critiqueEraDisplay(era);
        const content = String(it.content || '').trim();
        const blurb = String(it.blurb || '').trim();
        const bodyQuote = content || blurb;
        const source = String(it.source || it.book || '').trim();
        const cardTitle = angleTitle || displayAuthor;
        const metaParts = [];
        if (title && author)
            metaParts.push(author);
        if (dynasty)
            metaParts.push(dynasty);
        if (source)
            metaParts.push(source);
        const cardMeta = metaParts.filter(Boolean).join(' · ');
        return {
            ...it,
            id: Number.isFinite(idNum) && idNum > 0 ? idNum : null,
            displayAuthor,
            eraMeta: dynasty,
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
    return (raw || []).map((it) => {
        const idNum = Number(it.id);
        const full = String(it.description || it.summary || '').trim();
        // 列表简介：优先用服务端 summary；勿把截断摘要拼进详情全文
        const teaser = String(it.summary || it.description || '').trim();
        const museum = it.museum || '馆藏待补充';
        return {
            id: Number.isFinite(idNum) && idNum > 0 ? idNum : null,
            name: it.name || '',
            imageUrl: it.imageUrl,
            summary: teaser,
            description: full,
            museum,
            priorityCode: it.priorityCode,
            thumbLabel: relicThumbLabel(it.name || ''),
            teaser,
            location: museum,
            cardMeta: museum,
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
/** 君王/诸侯的起止年语义为在位年，展示时加「在位」前缀，避免被读成生卒 */
const REIGN_YEAR_CATEGORY_KEYS = new Set(['junji', 'zhuhou']);
function buildDetailMetaFromBox(box) {
    var _a, _b;
    const cat = String(box.categoryKey || '').trim();
    const y0 = yearLabel(box.startYear);
    const y1 = yearLabel(box.endYear);
    const raw = box;
    const civ = String((_b = (_a = raw.civilizationName) !== null && _a !== void 0 ? _a : raw.civilization_name) !== null && _b !== void 0 ? _b : '').trim();
    const catName = (0, category_label_1.categoryLabel)(cat);
    if (REIGN_YEAR_CATEGORY_KEYS.has(cat) && y0) {
        const range = y1 && y1 !== y0 ? `${y0} — ${y1}` : y0;
        const parts = [`在位 ${range}`];
        if (civ)
            parts.push(civ);
        if (catName)
            parts.push(catName);
        return parts.join(' · ');
    }
    const fromSub = formatDetailMetaLine(box.subText);
    if (fromSub)
        return fromSub;
    const parts = [];
    if (y0 && y1 && y0 !== y1)
        parts.push(`${y0} — ${y1}`);
    else if (y0)
        parts.push(y0);
    return parts.join(' · ');
}
function readBoxLocationNames(box) {
    var _a, _b, _c, _d;
    if (!box)
        return { civ: '', dynasty: '' };
    const raw = box;
    return {
        civ: String((_b = (_a = raw.civilizationName) !== null && _a !== void 0 ? _a : raw.civilization_name) !== null && _b !== void 0 ? _b : '').trim(),
        dynasty: String((_d = (_c = raw.dynastyName) !== null && _c !== void 0 ? _c : raw.dynasty_name) !== null && _d !== void 0 ? _d : '').trim(),
    };
}
const QUOTE_CLOSER = { '「': '」', '『': '』' };
const QUOTE_OPENERS = new Set(Object.keys(QUOTE_CLOSER));
const QUOTE_CLOSERS = new Set(Object.values(QUOTE_CLOSER));
function stripMarkdownBold(text) {
    return text.replace(/\*\*([^*]+)\*\*/g, '$1');
}
const MIN_QUOTE_BOLD_CHARS = 5;
const REF_PARA_RE = /^[\s*]*参考著作\s*[:：]/;
/** 参考著作节：标题加粗 + 编号书目列表（兼容 *参考著作* / - 列表 / 同行连写） */
function parseReferenceParagraph(raw) {
    let body = raw.trim();
    body = body.replace(/^[\s*]*参考著作\s*[:：]\s*[\s*]*/u, '');
    body = body.replace(/^\*+|\*+$/g, '').trim();
    const titles = [];
    const bookRe = /《[^》]+》/g;
    let m;
    while ((m = bookRe.exec(body)) !== null) {
        titles.push(m[0]);
    }
    const segs = [{ text: '参考著作：', bold: true }];
    if (!titles.length) {
        if (body)
            segs.push({ text: `\n${body}`, bold: false });
        const plain = segs.map((s) => s.text).join('');
        return { segs, plain };
    }
    titles.forEach((t, i) => {
        segs.push({ text: '\n', bold: false });
        segs.push({ text: `${i + 1}. ${t}`, bold: false });
    });
    const plain = segs.map((s) => s.text).join('');
    return { segs, plain };
}
/** 直角引号「」『』内正文 ≥5 字时，引号与原文整体加粗；正文勿写 ** markdown 加粗 */
function parseDisplaySegments(raw) {
    const text = stripMarkdownBold(raw);
    const pieces = [];
    const stack = [];
    let plain = '';
    const flushPlain = () => {
        if (!plain)
            return;
        pieces.push({ text: plain, bold: null });
        plain = '';
    };
    const markRange = (start, end, bold) => {
        for (let i = start; i <= end; i++) {
            const piece = pieces[i];
            if (!piece)
                continue;
            if (bold) {
                if (piece.bold !== false)
                    piece.bold = true;
            }
            else {
                piece.bold = false;
            }
        }
    };
    for (let i = 0; i < text.length; i++) {
        const ch = text[i];
        if (QUOTE_OPENERS.has(ch)) {
            flushPlain();
            for (const frame of stack)
                frame.inner += ch;
            stack.push({ inner: '', pieceStart: pieces.length });
            pieces.push({ text: ch, bold: null });
            continue;
        }
        if (QUOTE_CLOSERS.has(ch)) {
            const frame = stack.pop();
            if (!frame) {
                plain += ch;
                continue;
            }
            for (const f of stack)
                f.inner += ch;
            pieces.push({ text: ch, bold: null });
            markRange(frame.pieceStart, pieces.length - 1, frame.inner.length >= MIN_QUOTE_BOLD_CHARS);
            continue;
        }
        if (stack.length) {
            for (const frame of stack)
                frame.inner += ch;
            pieces.push({ text: ch, bold: null });
        }
        else {
            plain += ch;
        }
    }
    flushPlain();
    const segs = [];
    for (const piece of pieces) {
        const bold = piece.bold === true;
        const prev = segs[segs.length - 1];
        if (prev && prev.bold === bold) {
            prev.text += piece.text;
        }
        else {
            segs.push({ text: piece.text, bold });
        }
    }
    return segs;
}
function splitDetailParagraphs(md) {
    const raw = String(md || '').trim();
    if (!raw)
        return [];
    const fixed = raw.replace(/\\n/g, '\n');
    const parts = fixed.split(/\n{2,}/).map((s) => s.trim()).filter(Boolean);
    const list = parts.length ? parts : [fixed];
    return list.map((p) => {
        if (REF_PARA_RE.test(p)) {
            return parseReferenceParagraph(p);
        }
        const segs = parseDisplaySegments(p);
        const plain = segs.map((s) => s.text).join('');
        return { segs, plain };
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
        critColors: ['#A2734F', '#63899C', '#B99D5B', '#9A798F', '#7D8A6A', '#A46A65'],
        tab: 'content',
        showRelationsTab: false,
        isFav: false,
        isReadComplete: false,
        detailMd: '',
        detailParagraphs: [],
        blurbSegs: [],
        detailMetaDisplay: '',
        detailReady: false,
        detailErr: '',
        graph: { centerNodeKey: '', nodes: [], edges: [] },
        graphNodeCount: 0,
        graphPhase: 'idle',
        graphReady: false,
        graphLoading: false,
        graphRenderHint: '',
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
        narrationCoverLogoUrl: brand_assets_1.NARRATION_COVER_LOGO_URL,
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
        originalSourceWork: '',
        originalItems: [],
        originalFallback: '',
        originalEmpty: true,
        originalLoading: false,
        /** 仅程序定位时写入数字；定位后立刻置 ''，避免 scroll-top 受控锁死 */
        originalScrollAssign: '',
        originalReadingProgress: 0,
        correctionVisible: false,
        dictionaryVisible: false,
        dictionaryQuery: '',
        correctionSubmitting: false,
        correctionBoxTitle: '',
        correctionCivilizationName: '',
        correctionDynastyName: '',
        correctionSelectedText: '',
        correctionSourceType: 'box_detail_selection',
        noteVisible: false,
        noteSubmitting: false,
        noteSelectedText: '',
        noteBoxTitle: '',
        noteCivilizationName: '',
        noteDynastyName: '',
        detailHighlights: [],
        relationNotedNames: [],
        focusNoteId: 0,
        noteScrollIntoView: '',
        selectionBarVisible: false,
        selectionBarLeft: 0,
        selectionBarTop: 0,
        selectionBarPlacement: 'above',
        selectionBarText: '',
        selectionMountKey: 1,
        originalSelectionMountKey: 1,
        sharePosterVisible: false,
        sharePosterQuote: '',
        sharePosterSourceLine1: '',
        sharePosterSourceLine2: '',
        sharePosterUserName: '历史读者',
        sharePosterUserAvatar: '',
        sharePosterExcerptDate: '',
        /** 详情正文页内搜索半屏 */
        showContentSearch: false,
        contentSearchKeyword: '',
        contentSearchHasSearched: false,
        contentSearchResults: [],
        contentSearchHistory: [],
        contentSearchEmptyHint: '',
        searchFlashParaIndex: -1,
        contentSearchFocus: false,
        contentSearchTruncated: false,
        /** 搜索半屏：键盘顶起后垫高，避免历史/结果被挡 */
        contentSearchKeyboardHeight: 0,
        contentSearchModalStyle: '',
        contentSearchCardStyle: '',
        contentSearchBodyStyle: '',
        /** 轻量搜索浏览态：顶条 + 上一个/下一个 */
        contentSearchBrowseActive: false,
        contentSearchBrowseIndex: 0,
        contentSearchBrowseCounter: '',
        searchBrowseParaIndex: -1,
    },
    _selectionContext: null,
    _originalSelectionContext: null,
    _openOriginalOnReady: false,
    _searchFlashTimer: null,
    _searchFlashClearTimer: null,
    _ignoreTapFromBar: false,
    _onContentSearchKeyboard: null,
    _rawDetailParagraphs: [],
    _rawBlurbSegs: [],
    _focusNoteName: '',
    /** 详情 Tab 实时滚动位置（沉浸态判定用） */
    _detailScrollTop: 0,
    /** 离开详情 Tab 时缓存的阅读进度（当次访问有效） */
    _contentScrollTop: 0,
    _contentReadingProgress: 0,
    _tabBarPx: 0,
    _suppressChromeHide: false,
    _suppressChromeHideTimer: null,
    _restoreContentScrollTimer: null,
    /** 程序定位 scroll-top 的世代号，用于作废过期 setData 回调 */
    _bodyScrollAssignSeq: 0,
    /** 正在按持久化进度恢复滚动，期间不写回进度 */
    _restoringReadingProgress: false,
    /** 正在拉取/合并跨次进度，期间禁止 flush，避免 0% 误删 */
    _progressHydrating: false,
    /** 本页是否已完成本次跨次阅读进度 hydrate */
    _persistedProgressApplied: false,
    _persistReadingProgressTimer: null,
    /** 详情 scroll-view 可视高度（与恢复共用，保证百分比换算一致） */
    _detailViewportH: 0,
    _originalScrollTop: 0,
    _originalReadingProgress: 0,
    _originalViewportH: 0,
    _restoringOriginalProgress: false,
    _originalProgressHydrating: false,
    _originalProgressApplied: false,
    _persistOriginalProgressTimer: null,
    _restoreOriginalScrollTimer: null,
    _unlockOriginalProgressTimer: null,
    _rawOriginalRef: null,
    onReady() {
        this.bindDetailSelectionContext();
    },
    bindDetailSelectionContext() {
        wx.createSelectorQuery()
            .in(this)
            .select('#detailBodySelection')
            .context((res) => {
            var _a;
            this._selectionContext = (_a = res === null || res === void 0 ? void 0 : res.context) !== null && _a !== void 0 ? _a : null;
        })
            .exec();
    },
    bindOriginalSelectionContext() {
        wx.createSelectorQuery()
            .in(this)
            .select('#originalBodySelection')
            .context((res) => {
            var _a;
            this._originalSelectionContext = (_a = res === null || res === void 0 ? void 0 : res.context) !== null && _a !== void 0 ? _a : null;
        })
            .exec();
    },
    clearDetailSelection() {
        const ctx = this._selectionContext;
        if (ctx && typeof ctx.removeSelection === 'function') {
            try {
                ctx.removeSelection();
                return;
            }
            catch {
                // fallback to remount below
            }
        }
        this.setData({ selectionMountKey: this.data.selectionMountKey + 1 }, () => {
            this.bindDetailSelectionContext();
        });
    },
    clearOriginalSelection() {
        const ctx = this._originalSelectionContext;
        if (ctx && typeof ctx.removeSelection === 'function') {
            try {
                ctx.removeSelection();
                return;
            }
            catch {
                // fallback to remount below
            }
        }
        if (!this.data.showOriginal)
            return;
        this.setData({ originalSelectionMountKey: this.data.originalSelectionMountKey + 1 }, () => {
            this.bindOriginalSelectionContext();
        });
    },
    onHide() {
        this.flushPersistReadingProgress();
        this.cancelOriginalProgressRestore();
        void this.flushPersistOriginalReadingProgress();
    },
    onUnload() {
        if (this._suppressChromeHideTimer) {
            clearTimeout(this._suppressChromeHideTimer);
            this._suppressChromeHideTimer = null;
        }
        if (this._restoreContentScrollTimer) {
            clearTimeout(this._restoreContentScrollTimer);
            this._restoreContentScrollTimer = null;
        }
        if (this._persistReadingProgressTimer) {
            clearTimeout(this._persistReadingProgressTimer);
            this._persistReadingProgressTimer = null;
        }
        this.clearSearchFlashTimers();
        this.unbindContentSearchKeyboard();
        this.cancelOriginalProgressRestore();
        void this.flushPersistReadingProgress();
        void this.flushPersistOriginalReadingProgress();
        (0, box_narration_1.stopNarration)();
        this.setData({ audioOpen: false });
    },
    clearSearchFlashTimers() {
        if (this._searchFlashTimer) {
            clearTimeout(this._searchFlashTimer);
            this._searchFlashTimer = null;
        }
        if (this._searchFlashClearTimer) {
            clearTimeout(this._searchFlashClearTimer);
            this._searchFlashClearTimer = null;
        }
    },
    bindContentSearchKeyboard() {
        if (this._onContentSearchKeyboard)
            return;
        this._onContentSearchKeyboard = (res) => {
            if (!this.data.showContentSearch)
                return;
            const height = Math.max(0, Math.floor(Number(res === null || res === void 0 ? void 0 : res.height) || 0));
            this.applyContentSearchSheetLayout(height);
        };
        if (typeof wx.onKeyboardHeightChange === 'function') {
            wx.onKeyboardHeightChange(this._onContentSearchKeyboard);
        }
    },
    unbindContentSearchKeyboard() {
        const handler = this._onContentSearchKeyboard;
        if (handler && typeof wx.offKeyboardHeightChange === 'function') {
            wx.offKeyboardHeightChange(handler);
        }
        this._onContentSearchKeyboard = null;
    },
    /** 搜索半屏高度封顶约 75%；键盘升起时整体上移且不越过小程序顶栏 */
    applyContentSearchSheetLayout(keyboardHeight) {
        var _a;
        const kb = Math.max(0, Math.floor((_a = keyboardHeight !== null && keyboardHeight !== void 0 ? keyboardHeight : this.data.contentSearchKeyboardHeight) !== null && _a !== void 0 ? _a : 0));
        let windowHeight = 667;
        let windowWidth = 375;
        let safeBottom = 0;
        try {
            const sys = wx.getSystemInfoSync();
            windowHeight = Math.max(1, Math.floor(Number(sys.windowHeight) || 667));
            windowWidth = Math.max(1, Math.floor(Number(sys.windowWidth) || 375));
            const insets = sys.safeAreaInsets;
            safeBottom = Math.max(0, Math.floor(Number(insets === null || insets === void 0 ? void 0 : insets.bottom) || 0));
        }
        catch {
            // keep defaults
        }
        const padBottomRest = Math.max(14, Math.round((28 * windowWidth) / 750)) + safeBottom;
        const padBottom = kb > 0 ? Math.max(12, Math.round((16 * windowWidth) / 750)) : padBottomRest;
        const heightCap = Math.floor(windowHeight * 0.75);
        // 有键盘时：半屏仍不超过 75%，且不超过键盘上方剩余空间
        const aboveKeyboard = kb > 0 ? Math.max(260, windowHeight - kb - 8) : heightCap;
        const cardMaxHeightPx = Math.min(heightCap, aboveKeyboard);
        const headerPx = Math.round((88 * windowWidth) / 750);
        const barPx = Math.round((100 * windowWidth) / 750);
        const padTopPx = Math.round((28 * windowWidth) / 750);
        const chromePx = padTopPx + headerPx + barPx + padBottom;
        const bodyHeightPx = Math.max(160, cardMaxHeightPx - chromePx);
        this.setData({
            contentSearchKeyboardHeight: kb,
            contentSearchModalStyle: kb > 0 ? `padding-bottom: ${kb}px;` : '',
            contentSearchCardStyle: `max-height: ${cardMaxHeightPx}px; padding-bottom: ${padBottom}px;`,
            contentSearchBodyStyle: `height: ${bodyHeightPx}px; max-height: ${bodyHeightPx}px;`,
        });
    },
    currentReadingProgressPct() {
        if (this.data.tab === 'content') {
            return (0, box_reading_progress_1.clampProgressPct)(this.data.readingProgress || 0);
        }
        return (0, box_reading_progress_1.clampProgressPct)(this._contentReadingProgress || 0);
    },
    currentReadingScrollTopPx() {
        if (this.data.tab === 'content') {
            return Math.max(0, Math.round(this._detailScrollTop || 0));
        }
        return Math.max(0, Math.round(this._contentScrollTop || 0));
    },
    /** 与有栏布局一致：优先实测 scroll-view 高；回退 windowHeight - tabTop */
    detailViewportHeightPx() {
        if (this._detailViewportH > 0)
            return this._detailViewportH;
        const sys = wx.getSystemInfoSync();
        return (0, box_reading_progress_1.detailViewportFallbackPx)(sys.windowHeight || 0, this.data.tabTop || 0);
    },
    measureDetailViewport(done) {
        wx.createSelectorQuery()
            .in(this)
            .select('#boxBodyScroll')
            .boundingClientRect()
            .exec((res) => {
            const rect = (res && res[0]);
            const h = Number(rect === null || rect === void 0 ? void 0 : rect.height) || 0;
            if (h > 0)
                this._detailViewportH = h;
            done === null || done === void 0 ? void 0 : done();
        });
    },
    schedulePersistReadingProgress(immediate = false) {
        if (!(0, api_1.hasToken)() || this._restoringReadingProgress || this._progressHydrating)
            return;
        if (!this._persistedProgressApplied)
            return;
        if (this._persistReadingProgressTimer) {
            clearTimeout(this._persistReadingProgressTimer);
            this._persistReadingProgressTimer = null;
        }
        if (immediate) {
            void this.flushPersistReadingProgress();
            return;
        }
        this._persistReadingProgressTimer = setTimeout(() => {
            this._persistReadingProgressTimer = null;
            void this.flushPersistReadingProgress();
        }, 1200);
    },
    async flushPersistReadingProgress() {
        if (!(0, api_1.hasToken)() || this._restoringReadingProgress || this._progressHydrating)
            return;
        if (!this._persistedProgressApplied)
            return;
        const boxId = this.data.boxId;
        if (!boxId)
            return;
        const progressPct = this.currentReadingProgressPct();
        const scrollTopPx = this.currentReadingScrollTopPx();
        try {
            await (0, box_reading_progress_1.persistBoxReadingProgress)(boxId, { progressPct, scrollTopPx });
        }
        catch {
            // 静默失败：本地已优先写入
        }
    },
    /** 登录用户：正文就绪后按有栏坐标系恢复阅读位置 */
    async tryRestorePersistedReadingProgress() {
        if (!(0, api_1.hasToken)() || this._persistedProgressApplied || this._progressHydrating)
            return;
        const boxId = this.data.boxId;
        if (!boxId || this.data.tab !== 'content' || !this.data.detailReady)
            return;
        this._progressHydrating = true;
        this._restoringReadingProgress = true;
        // 恢复时始终按「导航+Tab 可见」呈现，与进度锚点一致
        if (!this.data.uiFocused) {
            this.setData({ uiFocused: true });
        }
        let record = null;
        try {
            record = await (0, box_reading_progress_1.resolveBoxReadingProgress)(boxId);
        }
        catch {
            this._restoringReadingProgress = false;
            this._progressHydrating = false;
            this._persistedProgressApplied = true;
            return;
        }
        this._persistedProgressApplied = true;
        this._progressHydrating = false;
        if (!record || !(0, box_reading_progress_1.isRestorableProgressPct)(record.progressPct)) {
            this._restoringReadingProgress = false;
            return;
        }
        this._contentReadingProgress = record.progressPct;
        this.setData({ readingProgress: record.progressPct, uiFocused: true });
        this.restoreContentScrollFromRecord(record);
    },
    restoreContentScrollFromRecord(record, attempt = 0) {
        if (!(0, box_reading_progress_1.isRestorableProgressPct)(record.progressPct)) {
            this._restoringReadingProgress = false;
            return;
        }
        const maxAttempts = 10;
        this._restoringReadingProgress = true;
        wx.createSelectorQuery()
            .in(this)
            .select('#boxBodyScroll')
            .scrollOffset()
            .select('#boxBodyScroll')
            .boundingClientRect()
            .exec((res) => {
            const scroll = (res && res[0]);
            const rect = (res && res[1]);
            const scrollHeight = Number(scroll === null || scroll === void 0 ? void 0 : scroll.scrollHeight) || 0;
            const viewportH = Number(rect === null || rect === void 0 ? void 0 : rect.height) || this.detailViewportHeightPx();
            if (viewportH > 0)
                this._detailViewportH = viewportH;
            const maxScroll = (0, box_reading_progress_1.maxScrollFromMetrics)(scrollHeight, viewportH);
            const target = (0, box_reading_progress_1.resolveRestoreScrollTop)(record, maxScroll);
            const ready = maxScroll > 0 && scrollHeight >= Math.max(viewportH * 1.2, 120);
            if (ready || attempt >= maxAttempts) {
                this._contentScrollTop = target;
                this._detailScrollTop = target;
                this.restoreContentScrollTop(target);
                if (target > 0) {
                    wx.showToast({ title: '已回到上次阅读位置', icon: 'none', duration: 1600 });
                }
                setTimeout(() => {
                    this._restoringReadingProgress = false;
                }, 400);
                return;
            }
            this._restoreContentScrollTimer = setTimeout(() => {
                this._restoreContentScrollTimer = null;
                this.restoreContentScrollFromRecord(record, attempt + 1);
            }, 48 + attempt * 28);
        });
    },
    /** 强制设置 scroll-view 的 scroll-top（同值时需先 bump 再设回） */
    applyBodyScrollTop(target, after) {
        const safeTarget = Math.max(0, target);
        const seq = ++this._bodyScrollAssignSeq;
        const prev = Number(this.data.bodyScrollTop);
        const mid = safeTarget <= 0
            ? (prev === 0 ? 0.01 : 0)
            : (prev === 0.01 ? 0.02 : 0.01);
        const applyFinal = () => {
            if (seq !== this._bodyScrollAssignSeq)
                return;
            if (mid === safeTarget) {
                after === null || after === void 0 ? void 0 : after();
                return;
            }
            this.setData({ bodyScrollTop: safeTarget }, () => {
                if (seq !== this._bodyScrollAssignSeq)
                    return;
                after === null || after === void 0 ? void 0 : after();
            });
        };
        if (prev === mid) {
            applyFinal();
            return;
        }
        this.setData({ bodyScrollTop: mid }, applyFinal);
    },
    /** 详情 DOM 重建后恢复阅读进度（scrollHeight 就绪前会短间隔重试） */
    restoreContentScrollTop(target, attempt = 0) {
        if (this.data.tab !== 'content') {
            this._restoringReadingProgress = false;
            return;
        }
        const safeTarget = Math.max(0, target);
        if (safeTarget <= 0) {
            this._restoringReadingProgress = false;
            this.applyBodyScrollTop(0, () => this.bindDetailSelectionContext());
            return;
        }
        const maxAttempts = 12;
        wx.createSelectorQuery()
            .in(this)
            .select('#boxBodyScroll')
            .scrollOffset()
            .select('#boxBodyScroll')
            .boundingClientRect()
            .select('#boxTab1Body')
            .boundingClientRect()
            .exec((res) => {
            if (this.data.tab !== 'content') {
                this._restoringReadingProgress = false;
                return;
            }
            const scroll = (res && res[0]);
            const rect = (res && res[1]);
            const contentRect = (res && res[2]);
            const scrollHeight = Number(scroll === null || scroll === void 0 ? void 0 : scroll.scrollHeight) || 0;
            const contentH = Number(contentRect === null || contentRect === void 0 ? void 0 : contentRect.height) || 0;
            const viewportH = Number(rect === null || rect === void 0 ? void 0 : rect.height) || 0;
            const minH = safeTarget + Math.max(viewportH * 0.35, 64);
            const ready = contentH > 0 && Math.max(contentH, scrollHeight) >= minH;
            if (!ready && attempt < maxAttempts) {
                this._restoreContentScrollTimer = setTimeout(() => {
                    this._restoreContentScrollTimer = null;
                    this.restoreContentScrollTop(safeTarget, attempt + 1);
                }, 40 + attempt * 24);
                return;
            }
            this.applyBodyScrollTop(safeTarget, () => {
                this.bindDetailSelectionContext();
                wx.createSelectorQuery()
                    .in(this)
                    .select('#boxBodyScroll')
                    .scrollOffset()
                    .exec((check) => {
                    var _a;
                    if (this.data.tab !== 'content') {
                        this._restoringReadingProgress = false;
                        return;
                    }
                    const actual = Math.round(Number((_a = (check && check[0])) === null || _a === void 0 ? void 0 : _a.scrollTop) || 0);
                    if (Math.abs(actual - safeTarget) > 16 && attempt < maxAttempts) {
                        this._restoreContentScrollTimer = setTimeout(() => {
                            this._restoreContentScrollTimer = null;
                            this.restoreContentScrollTop(safeTarget, attempt + 1);
                        }, 48 + attempt * 24);
                        return;
                    }
                    setTimeout(() => {
                        this._restoringReadingProgress = false;
                    }, 400);
                });
            });
        });
    },
    onShareAppMessage() {
        var _a;
        const h = this.data.header;
        const id = this.data.boxId;
        const title = ((_a = h === null || h === void 0 ? void 0 : h.box) === null || _a === void 0 ? void 0 : _a.title) || '史略详情';
        const path = id ? `/package-graph/pages/box-detail/index?boxId=${encodeURIComponent(id)}` : '/package-graph/pages/box-detail/index';
        return { title, path };
    },
    /** 底部「分享」：与选文分享同一套海报 UI，默认用详情第一段 */
    async onShareTap() {
        var _a, _b, _c;
        const paragraphs = this.data.detailParagraphs;
        const firstPara = String(((_a = paragraphs === null || paragraphs === void 0 ? void 0 : paragraphs[0]) === null || _a === void 0 ? void 0 : _a.plain) || '').trim();
        const blurb = String(((_c = (_b = this.data.header) === null || _b === void 0 ? void 0 : _b.box) === null || _c === void 0 ? void 0 : _c.blurb) || '').trim();
        const quote = firstPara || blurb;
        if (!quote) {
            wx.showToast({ title: '暂无可分享内容', icon: 'none' });
            return;
        }
        await this.openSharePoster(quote);
    },
    /** 打开摘录分享海报（选文 / 底栏共用） */
    async openSharePoster(quoteText) {
        const text = String(quoteText || '').trim();
        if (!text)
            return;
        wx.showLoading({ title: '生成海报…', mask: true });
        try {
            const header = this.data.header;
            const box = header === null || header === void 0 ? void 0 : header.box;
            const { civ, dynasty } = readBoxLocationNames(box);
            const title = (box === null || box === void 0 ? void 0 : box.title) || this.data.navTitle || '史略';
            const typeLabel = (0, category_label_1.categoryLabel)((box === null || box === void 0 ? void 0 : box.categoryKey) || '') || '史略';
            const sourceLine1 = `/${[civ, dynasty, typeLabel, title].filter(Boolean).join('・')}`;
            const posterState = await (0, share_poster_open_1.buildSharePosterSheetState)(text, sourceLine1, '');
            this.setData(posterState);
        }
        catch {
            wx.hideLoading();
            wx.showToast({ title: '海报生成失败', icon: 'none' });
        }
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
        const zoomBarPx = 0;
        const graphCanvasH = Math.max(400, Math.floor((sys.windowHeight || 667) - bodyTop - zoomBarPx));
        this._tabBarPx = tabBarPx;
        this._persistedProgressApplied = false;
        this._progressHydrating = false;
        this._restoringReadingProgress = false;
        this._bodyScrollAssignSeq = 0;
        this._contentScrollTop = 0;
        this._contentReadingProgress = 0;
        this._detailScrollTop = 0;
        this._detailViewportH = 0;
        this._originalScrollTop = 0;
        this._originalReadingProgress = 0;
        this._originalViewportH = 0;
        this._restoringOriginalProgress = false;
        this._originalProgressHydrating = false;
        this._originalProgressApplied = false;
        const requestedTab = query.tab === 'relations' ? 'relations' : 'content';
        const focusNoteId = Number(query.noteId || 0);
        this._focusNoteName = (0, query_value_1.decodeQueryValue)(query.highlightName || '');
        this._openOriginalOnReady = query.openOriginal === '1';
        this.setData({
            boxId,
            navTitle: provisionalTitle || '史略详情',
            tabTop,
            bodyTop,
            graphCanvasH,
            tab: requestedTab,
            focusNoteId: Number.isFinite(focusNoteId) ? focusNoteId : 0,
        });
        try {
            const res = await (0, api_1.request)(`/boxes/${(0, encode_path_segment_1.encodePathSegment)(boxId)}`, {
                auth: (0, api_1.hasToken)(),
                softAuth: true,
            });
            const header = res.data;
            const y0 = yearLabel(header.box.startYear);
            const y1 = yearLabel(header.box.endYear);
            const timeRange = y0 && y1 ? y0 + ' — ' + y1 : (y0 || y1 || '');
            const { civ, dynasty } = readBoxLocationNames(header.box);
            const showRelationsTab = (0, category_label_1.isPersonBoxCategory)(header.box.categoryKey);
            const tab = !showRelationsTab && this.data.tab === 'relations' ? 'content' : this.data.tab;
            this.setData({
                header,
                navTitle: header.box.title,
                detailMetaDisplay: buildDetailMetaFromBox(header.box),
                audioTimeRange: timeRange,
                audioCategoryPath: [civ, dynasty].filter(Boolean).join(' · '),
                blurbSegs: (this._rawBlurbSegs = parseDisplaySegments(header.box.blurb || '')),
                showRelationsTab,
                tab,
                isReadComplete: !!header.isReadComplete,
            });
            await this.refreshFavState();
            await this.recordFootprint();
            await this.ensureTab('content');
            await this.loadDetailHighlights();
            if (tab === 'relations' && showRelationsTab) {
                this.setData({ tab: 'relations' });
                await this.ensureTab('relations');
                this.focusRelationNoteIfNeeded();
            }
            else if (this.data.focusNoteId) {
                this.measureDetailViewport(() => {
                    this.scrollToNoteAnchor(this.data.focusNoteId);
                });
            }
            else if (tab === 'content') {
                this.measureDetailViewport(() => {
                    void this.tryRestorePersistedReadingProgress();
                });
            }
            if (this._openOriginalOnReady) {
                this._openOriginalOnReady = false;
                this.goOriginal();
            }
            // 详情正文就绪后预取关系图，切换 Tab 时无需再等
            if (showRelationsTab) {
                this.loadRelationsGraph();
            }
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
                content: '登录后可使用阅读点查看评述、见证与原文。',
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
                title: '需要阅读点',
                content: '深度阅读需消耗阅读点。可邀请好友注册获取阅读点，或稍后再试。',
                confirmText: '去邀请',
                success: (r) => {
                    if (r.confirm)
                        wx.switchTab({ url: router_1.ROUTES.invite });
                },
            });
        }
    },
    /** 关系 Tab：独立拉取，避免 ensureTab 早退导致 Network 无 /graph 请求 */
    loadRelationsGraph() {
        if (!this.data.showRelationsTab)
            return;
        if (!this.data.boxId) {
            this.setData({
                graphErr: '史略信息未就绪，请返回后重试',
                graphPhase: 'error',
                graphReady: true,
                graphLoading: false,
            });
            return;
        }
        if (this.data.graphFetched && this.data.graphPhase === 'ready')
            return;
        void this.fetchRelationsGraph();
    },
    async fetchRelationsGraph() {
        if (this._graphInflight)
            return this._graphInflight;
        const boxId = this.data.boxId;
        const enc = (0, encode_path_segment_1.encodePathSegment)(boxId);
        this.setData({
            graphLoading: true,
            graphPhase: 'loading',
            graphErr: '',
            graphRenderHint: '',
        });
        console.info('[box-detail] GET /boxes/' + boxId + '/graph');
        const task = (async () => {
            try {
                const res = await (0, api_1.request)(`/boxes/${enc}/graph`);
                const nodes = res.data.nodes || [];
                const edges = res.data.edges || [];
                const nodeCount = nodes.length;
                this.setData({
                    graph: {
                        centerNodeKey: res.data.centerNodeKey || '',
                        nodes,
                        edges,
                    },
                    graphNodeCount: nodeCount,
                    graphErr: '',
                    graphPhase: 'ready',
                    graphReady: true,
                    graphFetched: true,
                    graphLoading: false,
                    graphScaleLabel: '100%',
                });
                console.info('[box-detail] graph loaded nodes=', nodeCount);
                void this.loadRelationHighlights();
                this.focusRelationNoteIfNeeded();
            }
            catch (e) {
                console.warn('[box-detail] graph fetch failed', (e === null || e === void 0 ? void 0 : e.message) || e);
                this.setData({
                    graphErr: (e === null || e === void 0 ? void 0 : e.message) || '加载失败',
                    graph: { centerNodeKey: '', nodes: [], edges: [] },
                    graphNodeCount: 0,
                    graphPhase: 'error',
                    graphReady: true,
                    graphFetched: true,
                    graphLoading: false,
                });
            }
        })();
        this._graphInflight = task.finally(() => {
            ;
            this._graphInflight = undefined;
        });
        return task;
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
                this._rawDetailParagraphs = parsed;
                this.setData({
                    detailMd: md,
                    detailParagraphs: parsed,
                    detailErr: '',
                    detailReady: true,
                    detailFetched: true,
                }, () => {
                    this.bindDetailSelectionContext();
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
            this.loadRelationsGraph();
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
                    err = '阅读点不足，可前往「邀请」页邀请好友获取';
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
                    err = '阅读点不足，可前往「邀请」页邀请好友获取';
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
    onShow() {
        if (this.data.tab === 'relations'
            && this.data.showRelationsTab
            && this.data.graphPhase !== 'ready'
            && this.data.graphPhase !== 'error') {
            this.loadRelationsGraph();
        }
    },
    onGraphRenderHint(e) {
        var _a;
        const hint = String(((_a = e.detail) === null || _a === void 0 ? void 0 : _a.hint) || '').trim();
        this.setData({ graphRenderHint: hint });
    },
    setTab(e) {
        var _a;
        const tab = e.currentTarget.dataset.tab;
        if (!tab)
            return;
        if (tab === 'relations' && !this.data.showRelationsTab)
            return;
        if (tab === this.data.tab) {
            if (tab === 'relations' && this.data.graphPhase !== 'ready') {
                this.loadRelationsGraph();
            }
            return;
        }
        this.hideSelectionBar();
        if (this.data.contentSearchBrowseActive && tab !== 'content') {
            this.exitContentSearchBrowse();
        }
        const graph = this.selectComponent('#bdRelationGraph');
        (_a = graph === null || graph === void 0 ? void 0 : graph.hideSelectionBar) === null || _a === void 0 ? void 0 : _a.call(graph);
        const prevTab = this.data.tab;
        // 离开详情 Tab：缓存当次阅读进度
        if (prevTab === 'content') {
            this._contentScrollTop = this._detailScrollTop || 0;
            this._contentReadingProgress = this.data.readingProgress || 0;
            this.schedulePersistReadingProgress(true);
        }
        // 防止同一次点击冒泡到 onPageTap 后又被切成阅读全屏态
        this._ignoreTapFromBar = true;
        this._suppressChromeHide = true;
        if (this._suppressChromeHideTimer) {
            clearTimeout(this._suppressChromeHideTimer);
        }
        this._suppressChromeHideTimer = setTimeout(() => {
            this._suppressChromeHide = false;
            this._suppressChromeHideTimer = null;
        }, 280);
        if (this._restoreContentScrollTimer) {
            clearTimeout(this._restoreContentScrollTimer);
            this._restoreContentScrollTimer = null;
        }
        const restoreContent = tab === 'content';
        const restoreTop = restoreContent ? Math.max(0, this._contentScrollTop || 0) : 0;
        this._detailScrollTop = restoreTop;
        if (restoreContent) {
            this._restoringReadingProgress = restoreTop > 0;
        }
        else {
            this._restoringReadingProgress = false;
        }
        // 切换 Tab 时始终显示顶部四 Tab（非详情阅读沉浸态）
        this.setData({
            tab,
            uiFocused: true,
            readingProgress: restoreContent ? this._contentReadingProgress || 0 : 0,
        }, () => {
            if (restoreContent) {
                this.restoreContentScrollTop(restoreTop);
            }
            else {
                this.applyBodyScrollTop(0);
            }
            if (tab === 'relations') {
                this.loadRelationsGraph();
            }
            else {
                void this.ensureTab(tab).then(() => {
                    if (restoreContent)
                        this.bindDetailSelectionContext();
                });
            }
        });
    },
    onCritiqueTap(e) {
        const idx = Number(e.currentTarget.dataset.idx);
        const list = this.data.critiques;
        const c = list[idx];
        if (!c)
            return;
        const critiqueId = Number(c.id || 0);
        if (!(critiqueId > 0)) {
            wx.showToast({ title: '评述暂不可用', icon: 'none' });
            return;
        }
        (0, router_1.navigateTo)(router_1.ROUTES.critiqueDetail, { critiqueId });
    },
    onRelicTap(e) {
        const idx = Number(e.currentTarget.dataset.idx);
        const list = this.data.relics;
        const r = list[idx];
        if (!r)
            return;
        const relicId = Number(r.id || 0);
        if (!(relicId > 0)) {
            wx.showToast({ title: '见证暂不可用', icon: 'none' });
            return;
        }
        (0, router_1.navigateTo)(router_1.ROUTES.relicDetail, { relicId });
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
        // 卡在 loading 时允许强制重开，避免「点了没反应」
        if (cur === 'loading') {
            (0, box_narration_1.stopNarration)({ silent: true });
            this.setData({ narrationState: 'idle' });
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
        let initialReady = false;
        try {
            wx.showLoading({ title: '正在准备朗读', mask: true });
            loadingVisible = true;
            const audioTitle = this.data.detailMetaDisplay || this.data.navTitle || '史略解说';
            this.setData({ audioOpen: true, audioTitle, audioProgress: 0, audioCurrentTime: '0:00', audioDuration: '0:00', audioActivePara: -1 });
            await (0, box_narration_1.startNarration)(script, (s) => {
                if (s === 'playing' && loadingVisible) {
                    wx.hideLoading();
                    loadingVisible = false;
                    initialReady = true;
                }
                // 拖进度到未缓存片：短暂提示，不关浮层
                if (s === 'loading' && initialReady && this.data.audioOpen) {
                    wx.showToast({ title: '加载中…', icon: 'none', duration: 800 });
                }
                // seek 完成进入 playing/paused 后再允许 timeUpdate 写回进度
                if ((s === 'playing' || s === 'paused' || s === 'idle') && this._audioSeeking) {
                    this._audioSeeking = false;
                }
                // 仅在已经成功开播过之后，idle 才关闭浮层（避免启动失败/重启时闪退）
                if (s === 'idle' && initialReady) {
                    this.setData({ audioOpen: false, audioProgress: 0 });
                }
                this.setData({ narrationState: s });
            }, (p) => {
                // 拖动进度条时以手势为准，避免 timeUpdate 回跳
                if (this._audioSeeking) {
                    this.setData({ audioDuration: p.duration });
                    return;
                }
                this.setData({
                    audioProgress: p.progress,
                    audioCurrentTime: p.current,
                    audioDuration: p.duration,
                });
            });
            // start 成功返回时若仍未 playing（极端情况），以当前引擎状态为准
            if ((0, box_narration_1.getNarrationState)() === 'playing' || (0, box_narration_1.getNarrationState)() === 'paused') {
                initialReady = true;
            }
        }
        catch (e) {
            const msg = e instanceof Error ? e.message : '朗读失败';
            wx.showToast({ title: msg.slice(0, 28), icon: 'none', duration: 2800 });
            // 启动失败保留浮层，便于用户重试；仅复位状态
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
        const audioTitle = this.data.detailMetaDisplay || this.data.navTitle || '史略解说';
        this.setData({ audioOpen: true, audioTitle });
        if ((0, box_narration_1.getNarrationState)() === 'idle')
            void this.onPlayIntro();
    },
    toggleAudioPlayback() {
        const cur = (0, box_narration_1.getNarrationState)();
        if (cur === 'loading') {
            wx.showToast({ title: '正在加载音频…', icon: 'none', duration: 1200 });
            return;
        }
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
    _audioSeeking: false,
    onAudioSeekStart() {
        this._audioSeekStartX = 0;
        this._audioSeeking = true;
    },
    _formatAudioMmSs(sec) {
        if (!Number.isFinite(sec) || sec < 0)
            return '0:00';
        const m = Math.floor(sec / 60);
        const s = Math.floor(sec % 60);
        return `${m}:${s < 10 ? '0' : ''}${s}`;
    },
    _parseAudioMmSs(text) {
        const m = String(text || '0:00').match(/^(\d+):(\d{1,2})$/);
        if (!m)
            return 0;
        return Number(m[1]) * 60 + Number(m[2]);
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
            const totalSec = this._parseAudioMmSs(this.data.audioDuration);
            const curSec = totalSec > 0 ? (pct / 100) * totalSec : 0;
            this.setData({
                audioProgress: pct,
                audioCurrentTime: this._formatAudioMmSs(curSec),
            });
        }).exec();
    },
    onAudioSeekEnd(e) {
        var _a;
        const touch = (_a = e.changedTouches) === null || _a === void 0 ? void 0 : _a[0];
        if (!touch) {
            // 保持 _audioSeeking，等 playing 回调再清，避免旧 timeUpdate 回跳
            setTimeout(() => {
                if (this._audioSeeking && (0, box_narration_1.getNarrationState)() !== 'loading')
                    this._audioSeeking = false;
            }, 600);
            return;
        }
        const query = wx.createSelectorQuery().in(this);
        query.select('.box-audio-scrub-track').boundingClientRect((rect) => {
            if (!rect || rect.width <= 0) {
                this._audioSeeking = false;
                return;
            }
            const x = touch.clientX - rect.left;
            const ratio = Math.max(0, Math.min(1, x / rect.width));
            const pct = Math.round(ratio * 100);
            this.setData({ audioProgress: pct });
            // 松手后仍短暂锁进度，待引擎 seek 完成（state→playing）再解锁
            (0, box_narration_1.seekNarrationPct)(pct);
            setTimeout(() => {
                if (this._audioSeeking && (0, box_narration_1.getNarrationState)() !== 'loading')
                    this._audioSeeking = false;
            }, 1200);
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
    /** 解析原文引用 */
    _parseOriginalRef(ref) {
        var _a, _b, _c, _d, _f;
        if (ref == null || (Array.isArray(ref) && ref.length === 0) || (typeof ref === 'object' && Object.keys(ref).length === 0))
            return null;
        if (typeof ref === 'string') {
            const t = ref.trim();
            return t ? { title: '母本原文', sourceWork: '', items: [], fallback: t } : null;
        }
        if (typeof ref !== 'object' || ref === null)
            return null;
        const o = ref;
        const title = typeof o.title === 'string' && o.title.trim() ? o.title.trim() : '母本原文';
        const sourceWork = (typeof o.sourceWork === 'string' ? o.sourceWork.trim() : '') ||
            (typeof o.primarySource === 'string' ? o.primarySource.trim() : '');
        const textField = (typeof o.text === 'string' ? o.text.trim() : '') ||
            (typeof o.originalText === 'string' ? o.originalText.trim() : '');
        if (textField) {
            return { title, sourceWork, items: [], fallback: textField };
        }
        // 索引侧 paragraphs: [{ text }] 或 string[]
        if (Array.isArray(o.paragraphs)) {
            const parts = [];
            for (const p of o.paragraphs) {
                if (typeof p === 'string' && p.trim())
                    parts.push(p.trim());
                else if (p && typeof p === 'object') {
                    const t = String((_a = p.text) !== null && _a !== void 0 ? _a : '').trim();
                    if (t)
                        parts.push(t);
                }
            }
            if (parts.length)
                return { title, sourceWork, items: [], fallback: parts.join('\n') };
        }
        const rawItems = o.items;
        const items = [];
        if (Array.isArray(rawItems)) {
            for (const it of rawItems) {
                if (!it || typeof it !== 'object')
                    continue;
                const x = it;
                items.push({
                    work: String((_b = x.work) !== null && _b !== void 0 ? _b : '').trim(),
                    chapter: String((_c = x.chapter) !== null && _c !== void 0 ? _c : '').trim(),
                    excerpt: String((_d = x.excerpt) !== null && _d !== void 0 ? _d : '').trim().replace(/\\r\\n/g, '\n').replace(/\\n/g, '\n'),
                    url: String((_f = x.url) !== null && _f !== void 0 ? _f : '').trim(),
                });
            }
        }
        const hasStructured = items.some((i) => i.work || i.chapter || i.excerpt || i.url);
        // 无法识别的结构：不向用户展示 JSON 字符串
        if (!hasStructured)
            return null;
        return { title, sourceWork, items, fallback: '' };
    },
    originalViewportHeightPx() {
        if (this._originalViewportH > 0)
            return this._originalViewportH;
        const sys = wx.getSystemInfoSync();
        return (0, box_reading_progress_1.originalViewportFallbackPx)(sys.windowHeight || 0);
    },
    clearOriginalProgressTimers() {
        if (this._persistOriginalProgressTimer) {
            clearTimeout(this._persistOriginalProgressTimer);
            this._persistOriginalProgressTimer = null;
        }
        if (this._restoreOriginalScrollTimer) {
            clearTimeout(this._restoreOriginalScrollTimer);
            this._restoreOriginalScrollTimer = null;
        }
        if (this._unlockOriginalProgressTimer) {
            clearTimeout(this._unlockOriginalProgressTimer);
            this._unlockOriginalProgressTimer = null;
        }
    },
    cancelOriginalProgressRestore() {
        this.clearOriginalProgressTimers();
        this._restoringOriginalProgress = false;
        this._originalProgressHydrating = false;
    },
    unlockOriginalProgressSoon() {
        if (this._unlockOriginalProgressTimer) {
            clearTimeout(this._unlockOriginalProgressTimer);
            this._unlockOriginalProgressTimer = null;
        }
        this._unlockOriginalProgressTimer = setTimeout(() => {
            this._unlockOriginalProgressTimer = null;
            this._restoringOriginalProgress = false;
        }, 400);
    },
    schedulePersistOriginalReadingProgress(immediate = false) {
        if (!(0, api_1.hasToken)() || this._restoringOriginalProgress || this._originalProgressHydrating)
            return;
        if (!this._originalProgressApplied)
            return;
        if (this._persistOriginalProgressTimer) {
            clearTimeout(this._persistOriginalProgressTimer);
            this._persistOriginalProgressTimer = null;
        }
        if (immediate) {
            void this.flushPersistOriginalReadingProgress();
            return;
        }
        this._persistOriginalProgressTimer = setTimeout(() => {
            this._persistOriginalProgressTimer = null;
            void this.flushPersistOriginalReadingProgress();
        }, 1200);
    },
    async flushPersistOriginalReadingProgress() {
        if (!(0, api_1.hasToken)() || this._restoringOriginalProgress || this._originalProgressHydrating)
            return;
        if (!this._originalProgressApplied)
            return;
        const boxId = this.data.boxId;
        if (!boxId)
            return;
        const progressPct = (0, box_reading_progress_1.clampProgressPct)(this.data.originalReadingProgress || this._originalReadingProgress || 0);
        const scrollTopPx = Math.max(0, Math.round(this._originalScrollTop || 0));
        try {
            await (0, box_reading_progress_1.persistBoxReadingProgress)((0, box_reading_progress_1.originalReadingProgressId)(this.data.boxId), { progressPct, scrollTopPx });
        }
        catch {
            // 静默失败：本地已优先写入
        }
    },
    async tryRestoreOriginalReadingProgress() {
        if (!this.data.showOriginal || this.data.originalLoading || this.data.originalEmpty) {
            this._restoringOriginalProgress = false;
            this._originalProgressHydrating = false;
            return;
        }
        if (!(0, api_1.hasToken)()) {
            this._originalProgressApplied = true;
            const memoryTop = Math.max(0, Math.round(this._originalScrollTop || 0));
            if (memoryTop > 0)
                this.restoreOriginalScrollTop(memoryTop);
            else
                this._restoringOriginalProgress = false;
            return;
        }
        if (this._originalProgressHydrating)
            return;
        this._originalProgressHydrating = true;
        this._restoringOriginalProgress = true;
        this._originalProgressApplied = false;
        let record = null;
        try {
            record = await (0, box_reading_progress_1.resolveBoxReadingProgress)((0, box_reading_progress_1.originalReadingProgressId)(this.data.boxId));
        }
        catch {
            this._restoringOriginalProgress = false;
            this._originalProgressHydrating = false;
            if (this.data.showOriginal)
                this._originalProgressApplied = true;
            return;
        }
        this._originalProgressHydrating = false;
        if (!this.data.showOriginal) {
            this._restoringOriginalProgress = false;
            return;
        }
        this._originalProgressApplied = true;
        if (!record || !(0, box_reading_progress_1.isRestorableProgressPct)(record.progressPct)) {
            this._restoringOriginalProgress = false;
            const memoryTop = Math.max(0, Math.round(this._originalScrollTop || 0));
            if (memoryTop > 0)
                this.restoreOriginalScrollTop(memoryTop);
            return;
        }
        this._originalReadingProgress = record.progressPct;
        const stashedTop = Math.max(0, Math.round(Number(record.scrollTopPx) || 0));
        if (stashedTop > 0)
            this._originalScrollTop = stashedTop;
        this.setData({ originalReadingProgress: record.progressPct });
        this.restoreOriginalScrollFromRecord(record);
    },
    restoreOriginalScrollFromRecord(record, attempt = 0) {
        if (!(0, box_reading_progress_1.isRestorableProgressPct)(record.progressPct) || !this.data.showOriginal) {
            this._restoringOriginalProgress = false;
            return;
        }
        const maxAttempts = 10;
        this._restoringOriginalProgress = true;
        wx.createSelectorQuery()
            .in(this)
            .select('#originalBodyScroll')
            .scrollOffset()
            .select('#originalBodyScroll')
            .boundingClientRect()
            .exec((res) => {
            if (!this.data.showOriginal) {
                this._restoringOriginalProgress = false;
                return;
            }
            const scroll = (res && res[0]);
            const rect = (res && res[1]);
            const scrollHeight = Number(scroll === null || scroll === void 0 ? void 0 : scroll.scrollHeight) || 0;
            const viewportH = Number(rect === null || rect === void 0 ? void 0 : rect.height) || this.originalViewportHeightPx();
            if (viewportH > 0)
                this._originalViewportH = viewportH;
            const maxScroll = (0, box_reading_progress_1.maxScrollFromMetrics)(scrollHeight, viewportH);
            const target = (0, box_reading_progress_1.resolveRestoreScrollTop)(record, maxScroll);
            const ready = maxScroll > 0 && scrollHeight >= Math.max(viewportH * 1.2, 120);
            if (ready || attempt >= maxAttempts) {
                if (!(maxScroll > 0)) {
                    this._restoringOriginalProgress = false;
                    return;
                }
                this._originalScrollTop = target;
                this.restoreOriginalScrollTop(target);
                if (target > 0) {
                    wx.showToast({ title: '已回到上次阅读位置', icon: 'none', duration: 1600 });
                }
                return;
            }
            if (this._restoreOriginalScrollTimer) {
                clearTimeout(this._restoreOriginalScrollTimer);
                this._restoreOriginalScrollTimer = null;
            }
            this._restoreOriginalScrollTimer = setTimeout(() => {
                this._restoreOriginalScrollTimer = null;
                this.restoreOriginalScrollFromRecord(record, attempt + 1);
            }, 48 + attempt * 28);
        });
    },
    applyOriginalScrollTop(target, after) {
        const safeTarget = Math.max(0, target);
        if (safeTarget <= 0) {
            after === null || after === void 0 ? void 0 : after();
            return;
        }
        const prev = this.data.originalScrollAssign;
        const bump = prev === safeTarget
            ? safeTarget - 0.01
            : safeTarget;
        // 定位后保留数字绑定；用户滚动时在 onOriginalScroll 里静默同步，避免被拽回旧值
        this.setData({ originalScrollAssign: bump }, () => {
            if (bump !== safeTarget) {
                this.setData({ originalScrollAssign: safeTarget }, after);
            }
            else {
                after === null || after === void 0 ? void 0 : after();
            }
        });
    },
    restoreOriginalScrollTop(target, attempt = 0) {
        if (!this.data.showOriginal) {
            this._restoringOriginalProgress = false;
            return;
        }
        const safeTarget = Math.max(0, target);
        if (safeTarget <= 0) {
            this.unlockOriginalProgressSoon();
            return;
        }
        const maxAttempts = 8;
        wx.createSelectorQuery()
            .in(this)
            .select('#originalBodyScroll')
            .scrollOffset()
            .select('#originalBodyScroll')
            .boundingClientRect()
            .exec((res) => {
            if (!this.data.showOriginal) {
                this._restoringOriginalProgress = false;
                return;
            }
            const scroll = (res && res[0]);
            const rect = (res && res[1]);
            const scrollHeight = Number(scroll === null || scroll === void 0 ? void 0 : scroll.scrollHeight) || 0;
            const viewportH = Number(rect === null || rect === void 0 ? void 0 : rect.height) || 0;
            const ready = scrollHeight >= safeTarget + Math.max(viewportH * 0.35, 64);
            if (ready || attempt >= maxAttempts) {
                this.applyOriginalScrollTop(safeTarget, () => this.unlockOriginalProgressSoon());
                return;
            }
            if (this._restoreOriginalScrollTimer) {
                clearTimeout(this._restoreOriginalScrollTimer);
                this._restoreOriginalScrollTimer = null;
            }
            this._restoreOriginalScrollTimer = setTimeout(() => {
                this._restoreOriginalScrollTimer = null;
                this.restoreOriginalScrollTop(safeTarget, attempt + 1);
            }, 40 + attempt * 24);
        });
    },
    onOriginalScroll(e) {
        if (!this.data.showOriginal || this._restoringOriginalProgress || this._originalProgressHydrating)
            return;
        const d = e.detail || { scrollTop: 0, scrollHeight: 0 };
        const scrollTop = d.scrollTop || 0;
        const scrollHeight = d.scrollHeight || 0;
        const viewportH = this.originalViewportHeightPx();
        const maxScroll = (0, box_reading_progress_1.maxScrollFromMetrics)(scrollHeight, viewportH);
        const pct = (0, box_reading_progress_1.progressPctFromScroll)(scrollTop, maxScroll);
        this._originalScrollTop = scrollTop;
        this._originalReadingProgress = pct;
        // 静默同步绑定值，避免后续只改进度条的 setData 把正文拽回恢复点
        this.data.originalScrollAssign = scrollTop;
        this.schedulePersistOriginalReadingProgress(false);
        if (pct === this.data.originalReadingProgress)
            return;
        this.setData({ originalReadingProgress: pct });
    },
    goOriginal() {
        this.hideSelectionBar();
        this.cancelOriginalProgressRestore();
        this._originalProgressApplied = false;
        // 优先使用之前缓存的数据
        const ref = this._rawOriginalRef;
        if (ref != null) {
            const parsed = this._parseOriginalRef(ref);
            if (parsed && (parsed.items.length > 0 || parsed.fallback.length > 0)) {
                this.setData({
                    showOriginal: true,
                    originalScrollAssign: '',
                    originalTitle: parsed.title,
                    originalSourceWork: parsed.sourceWork,
                    originalItems: parsed.items,
                    originalFallback: parsed.fallback,
                    originalEmpty: false,
                    originalLoading: false,
                }, () => {
                    this.bindOriginalSelectionContext();
                    void this.tryRestoreOriginalReadingProgress();
                });
                return;
            }
        }
        // 无缓存，重新请求
        this.setData({ showOriginal: true, originalScrollAssign: '', originalLoading: true, originalEmpty: true });
        const run = async () => {
            try {
                const enc = (0, encode_path_segment_1.encodePathSegment)(this.data.boxId);
                const res = await (0, api_1.request)(`/boxes/${enc}/original-ref`, { auth: (0, api_1.hasToken)(), softAuth: true });
                const parsed = this._parseOriginalRef(res.data.originalRef);
                if (!parsed || (!parsed.items.length && !parsed.fallback.length)) {
                    this.setData({
                        originalLoading: false,
                        originalEmpty: true,
                        originalTitle: '',
                        originalSourceWork: '',
                        originalItems: [],
                        originalFallback: '',
                    });
                    return;
                }
                this.setData({
                    originalLoading: false,
                    originalEmpty: false,
                    originalTitle: parsed.title,
                    originalSourceWork: parsed.sourceWork,
                    originalItems: parsed.items,
                    originalFallback: parsed.fallback,
                }, () => {
                    this.bindOriginalSelectionContext();
                    void this.tryRestoreOriginalReadingProgress();
                });
            }
            catch {
                this.setData({ originalLoading: false, originalEmpty: true });
                wx.showToast({ title: '原文暂时无法加载，请稍后重试', icon: 'none' });
            }
        };
        void run();
    },
    closeOriginal() {
        this.hideSelectionBar();
        this.cancelOriginalProgressRestore();
        this.schedulePersistOriginalReadingProgress(true);
        this.setData({ showOriginal: false, originalScrollAssign: '' });
    },
    copyOriginalLink(e) {
        var _a, _b;
        const url = (_b = (_a = e.currentTarget) === null || _a === void 0 ? void 0 : _a.dataset) === null || _b === void 0 ? void 0 : _b.url;
        if (url) {
            wx.setClipboardData({ data: url });
            wx.showToast({ title: '链接已复制', icon: 'success' });
        }
    },
    onGraphNodeTap(_e) {
        // 短按仅高亮；长按选字由图谱 cover-view 浮层处理
        if (this.data.selectionBarVisible)
            this.hideSelectionBar();
    },
    onGraphNodeLongPress(e) {
        var _a;
        const selected = String(((_a = e.detail) === null || _a === void 0 ? void 0 : _a.text) || '').trim();
        if (!selected)
            return;
        this.setData({
            selectionBarText: selected,
            correctionSourceType: 'relation_graph_selection',
        });
    },
    onGraphSelectionCopy(e) {
        var _a;
        const text = String(((_a = e.detail) === null || _a === void 0 ? void 0 : _a.text) || this.data.selectionBarText || '').trim();
        if (!text)
            return;
        wx.setClipboardData({
            data: text,
            success: () => wx.showToast({ title: '已复制', icon: 'success' }),
        });
    },
    onGraphSelectionQuery(e) {
        var _a;
        const text = String(((_a = e.detail) === null || _a === void 0 ? void 0 : _a.text) || this.data.selectionBarText || '').trim();
        if (!text)
            return;
        this.setData({
            dictionaryVisible: true,
            dictionaryQuery: text,
            correctionSourceType: 'relation_graph_selection',
        });
    },
    onGraphSelectionCorrection(e) {
        var _a;
        const text = String(((_a = e.detail) === null || _a === void 0 ? void 0 : _a.text) || this.data.selectionBarText || '').trim();
        if (!text)
            return;
        this.setData({ correctionSourceType: 'relation_graph_selection' });
        this.openCorrectionModal(text);
    },
    onGraphSelectionNote(e) {
        var _a;
        const text = String(((_a = e.detail) === null || _a === void 0 ? void 0 : _a.text) || this.data.selectionBarText || '').trim();
        if (!text)
            return;
        this.setData({ correctionSourceType: 'relation_graph_selection' });
        this.openNoteModal(text);
    },
    noop() { },
    /** 标记本次tap来自底部操作栏，阻止导航栏切换 */
    markTapFromBar() { this._ignoreTapFromBar = true; },
    onGraphZoomIn() {
        var _a, _b, _c;
        const c = this.selectComponent('#bdRelationGraph');
        (_a = c === null || c === void 0 ? void 0 : c.zoomIn) === null || _a === void 0 ? void 0 : _a.call(c);
        const label = this.formatGraphScaleLabel((_c = (_b = c === null || c === void 0 ? void 0 : c.getZoomScale) === null || _b === void 0 ? void 0 : _b.call(c)) !== null && _c !== void 0 ? _c : 1);
        if (label !== this.data.graphScaleLabel) {
            this.setData({ graphScaleLabel: label }, () => { var _a; return (_a = c === null || c === void 0 ? void 0 : c.paintCached) === null || _a === void 0 ? void 0 : _a.call(c); });
        }
    },
    onGraphZoomOut() {
        var _a, _b, _c;
        const c = this.selectComponent('#bdRelationGraph');
        (_a = c === null || c === void 0 ? void 0 : c.zoomOut) === null || _a === void 0 ? void 0 : _a.call(c);
        const label = this.formatGraphScaleLabel((_c = (_b = c === null || c === void 0 ? void 0 : c.getZoomScale) === null || _b === void 0 ? void 0 : _b.call(c)) !== null && _c !== void 0 ? _c : 1);
        if (label !== this.data.graphScaleLabel) {
            this.setData({ graphScaleLabel: label }, () => { var _a; return (_a = c === null || c === void 0 ? void 0 : c.paintCached) === null || _a === void 0 ? void 0 : _a.call(c); });
        }
    },
    onGraphZoomReset() {
        var _a;
        const c = this.selectComponent('#bdRelationGraph');
        (_a = c === null || c === void 0 ? void 0 : c.resetZoom) === null || _a === void 0 ? void 0 : _a.call(c);
        if (this.data.graphScaleLabel !== '100%') {
            this.setData({ graphScaleLabel: '100%' }, () => { var _a; return (_a = c === null || c === void 0 ? void 0 : c.paintCached) === null || _a === void 0 ? void 0 : _a.call(c); });
        }
    },
    onGraphZoomChange(e) {
        var _a;
        // 双指缩放：松手后由组件触发；过程中不 setData
        const scale = (_a = e.detail) === null || _a === void 0 ? void 0 : _a.scale;
        if (scale == null)
            return;
        const c = this.selectComponent('#bdRelationGraph');
        const label = this.formatGraphScaleLabel(scale);
        if (label === this.data.graphScaleLabel)
            return;
        this.setData({ graphScaleLabel: label }, () => { var _a; return (_a = c === null || c === void 0 ? void 0 : c.paintCached) === null || _a === void 0 ? void 0 : _a.call(c); });
    },
    onDetailScroll(e) {
        var _a;
        const d = e.detail || { scrollTop: 0, scrollHeight: 0 };
        const scrollTop = d.scrollTop || 0;
        const scrollHeight = d.scrollHeight || 0;
        const viewportH = this.detailViewportHeightPx();
        const maxScroll = (0, box_reading_progress_1.maxScrollFromMetrics)(scrollHeight, viewportH);
        const pct = (0, box_reading_progress_1.progressPctFromScroll)(scrollTop, maxScroll);
        if (this._restoringReadingProgress || this._progressHydrating) {
            return;
        }
        // 静默同步绑定值，避免后续只改进度条的 setData 把正文拽回旧位置
        this.data.bodyScrollTop = scrollTop;
        if (this.data.tab === 'content') {
            this.schedulePersistReadingProgress(false);
        }
        if (pct !== this.data.readingProgress) {
            this.setData({ readingProgress: pct });
        }
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
        if (this.data.selectionBarVisible) {
            this.hideSelectionBar();
            return;
        }
        if (this.data.showOriginal || this.data.showContentSearch)
            return;
        if (this.data.contentSearchBrowseActive)
            return;
        if (this.data.tab === 'content' && !this._ignoreTapFromBar) {
            this.onToggleUI(!this.data.uiFocused);
        }
        this._ignoreTapFromBar = false;
    },
    openContentSearch() {
        this.hideSelectionBar();
        const history = (0, box_detail_search_history_1.readBoxDetailSearchHistory)(this.data.boxId);
        this.bindContentSearchKeyboard();
        // 从浏览态「全部结果」回来时保留关键词与结果
        const keepResults = this.data.contentSearchBrowseActive &&
            this.data.contentSearchHasSearched &&
            this.data.contentSearchResults.length > 0;
        this.setData({
            showContentSearch: true,
            contentSearchKeyword: keepResults ? this.data.contentSearchKeyword : '',
            contentSearchHasSearched: keepResults,
            contentSearchResults: keepResults ? this.data.contentSearchResults : [],
            contentSearchHistory: history,
            contentSearchEmptyHint: keepResults
                ? this.data.contentSearchResults.length
                    ? ''
                    : '未找到匹配段落'
                : '',
            contentSearchFocus: !keepResults,
            contentSearchTruncated: keepResults ? this.data.contentSearchTruncated : false,
            uiFocused: true,
        });
        this.applyContentSearchSheetLayout(0);
    },
    closeContentSearch() {
        this.unbindContentSearchKeyboard();
        this.setData({
            showContentSearch: false,
            contentSearchEmptyHint: '',
            contentSearchFocus: false,
            contentSearchKeyboardHeight: 0,
            contentSearchModalStyle: '',
            contentSearchCardStyle: '',
            contentSearchBodyStyle: '',
        });
    },
    onContentSearchInput(e) {
        var _a;
        this.setData({ contentSearchKeyword: String(((_a = e.detail) === null || _a === void 0 ? void 0 : _a.value) || '') });
    },
    onContentSearchClear() {
        this.setData({
            contentSearchKeyword: '',
            contentSearchEmptyHint: '',
            contentSearchHasSearched: false,
            contentSearchResults: [],
            contentSearchHistory: (0, box_detail_search_history_1.readBoxDetailSearchHistory)(this.data.boxId),
            contentSearchFocus: true,
            contentSearchTruncated: false,
        });
    },
    /** 右侧「搜索」按钮：空词空态；否则出匹配段落列表并写入本篇历史 */
    runContentSearch() {
        const keyword = String(this.data.contentSearchKeyword || '').trim().slice(0, 50);
        if (!keyword) {
            this.setData({
                contentSearchHasSearched: true,
                contentSearchResults: [],
                contentSearchEmptyHint: '请输入搜索词',
                contentSearchFocus: false,
                contentSearchTruncated: false,
            });
            return;
        }
        const paragraphs = this.contentSearchParagraphs();
        const results = (0, box_detail_search_1.searchDetailParagraphs)(paragraphs, keyword);
        (0, box_detail_search_history_1.addBoxDetailSearchHistory)(this.data.boxId, keyword);
        const truncated = results.length >= box_detail_search_1.DETAIL_SEARCH_MAX_RESULTS;
        this.setData({
            contentSearchKeyword: keyword,
            contentSearchHasSearched: true,
            contentSearchResults: results,
            contentSearchHistory: (0, box_detail_search_history_1.readBoxDetailSearchHistory)(this.data.boxId),
            contentSearchEmptyHint: results.length ? '' : '未找到匹配段落',
            contentSearchFocus: false,
            contentSearchTruncated: truncated,
        });
    },
    contentSearchParagraphs() {
        var _a, _b;
        const paras = this.data.detailParagraphs;
        if (paras.length)
            return paras.map((p) => p.plain);
        const blurb = String(((_b = (_a = this.data.header) === null || _a === void 0 ? void 0 : _a.box) === null || _b === void 0 ? void 0 : _b.blurb) || '').trim();
        if (blurb) {
            const segs = this.data.blurbSegs;
            const plain = segs.length ? segs.map((s) => s.text).join('') : blurb;
            return [plain];
        }
        return [];
    },
    onContentSearchHistoryTap(e) {
        var _a, _b;
        const k = String(((_b = (_a = e.currentTarget) === null || _a === void 0 ? void 0 : _a.dataset) === null || _b === void 0 ? void 0 : _b.k) || '').trim();
        if (!k)
            return;
        this.setData({ contentSearchKeyword: k }, () => {
            this.runContentSearch();
        });
    },
    onContentSearchHistoryClearAll() {
        (0, box_detail_search_history_1.clearBoxDetailSearchHistory)(this.data.boxId);
        this.setData({ contentSearchHistory: [] });
    },
    onContentSearchResultTap(e) {
        var _a;
        const ds = (_a = e.currentTarget) === null || _a === void 0 ? void 0 : _a.dataset;
        const index = Number(ds === null || ds === void 0 ? void 0 : ds.index);
        if (!Number.isFinite(index) || index < 0)
            return;
        this.enterContentSearchBrowse(index);
    },
    contentSearchBrowseCounterText(index, total) {
        if (total <= 0)
            return '0/0';
        return `${index + 1}/${total}`;
    },
    enterContentSearchBrowse(index) {
        const results = this.data.contentSearchResults;
        if (!results.length)
            return;
        const i = Math.max(0, Math.min(Math.floor(index), results.length - 1));
        this.closeContentSearch();
        this.setData({
            contentSearchBrowseActive: true,
            contentSearchBrowseIndex: i,
            contentSearchBrowseCounter: this.contentSearchBrowseCounterText(i, results.length),
            uiFocused: true,
        });
        this.jumpToSearchBrowseHit(i, true);
    },
    exitContentSearchBrowse() {
        this.clearSearchFlashTimers();
        this.setData({
            contentSearchBrowseActive: false,
            contentSearchBrowseIndex: 0,
            contentSearchBrowseCounter: '',
            searchBrowseParaIndex: -1,
            searchFlashParaIndex: -1,
            uiFocused: true,
        });
    },
    /** 浏览态底栏：回到结果半屏（保留关键词与列表） */
    onSearchBrowseAllResults() {
        if (!this.data.contentSearchBrowseActive)
            return;
        this.openContentSearch();
    },
    onSearchBrowsePrev() {
        if (!this.data.contentSearchBrowseActive)
            return;
        const i = this.data.contentSearchBrowseIndex;
        if (i <= 0) {
            wx.showToast({ title: '已是第一条', icon: 'none' });
            return;
        }
        this.goSearchBrowseIndex(i - 1);
    },
    onSearchBrowseNext() {
        if (!this.data.contentSearchBrowseActive)
            return;
        const results = this.data.contentSearchResults;
        const i = this.data.contentSearchBrowseIndex;
        if (i >= results.length - 1) {
            wx.showToast({ title: '已是最后一条', icon: 'none' });
            return;
        }
        this.goSearchBrowseIndex(i + 1);
    },
    goSearchBrowseIndex(index) {
        const results = this.data.contentSearchResults;
        if (!results.length)
            return;
        const i = Math.max(0, Math.min(Math.floor(index), results.length - 1));
        this.setData({
            contentSearchBrowseIndex: i,
            contentSearchBrowseCounter: this.contentSearchBrowseCounterText(i, results.length),
        });
        this.jumpToSearchBrowseHit(i, true);
    },
    jumpToSearchBrowseHit(index, flash) {
        const results = this.data.contentSearchResults;
        const hit = results[index];
        if (!hit)
            return;
        const paragraphIndex = hit.paragraphIndex;
        const id = (0, box_detail_search_1.detailParaAnchorId)(paragraphIndex);
        this.clearSearchFlashTimers();
        this.setData({
            noteScrollIntoView: '',
            searchBrowseParaIndex: paragraphIndex,
            searchFlashParaIndex: -1,
        }, () => {
            const next = { noteScrollIntoView: id };
            if (flash)
                next.searchFlashParaIndex = paragraphIndex;
            this.setData(next);
            if (flash) {
                this._searchFlashClearTimer = setTimeout(() => {
                    this._searchFlashClearTimer = null;
                    if (this.data.searchFlashParaIndex === paragraphIndex) {
                        this.setData({ searchFlashParaIndex: -1 });
                    }
                }, 1800);
            }
        });
    },
    scrollToDetailParagraph(paragraphIndex) {
        const id = (0, box_detail_search_1.detailParaAnchorId)(paragraphIndex);
        this.clearSearchFlashTimers();
        this.setData({ noteScrollIntoView: '', searchFlashParaIndex: -1 }, () => {
            this.setData({ noteScrollIntoView: id, searchFlashParaIndex: paragraphIndex });
            this._searchFlashClearTimer = setTimeout(() => {
                this._searchFlashClearTimer = null;
                if (this.data.searchFlashParaIndex === paragraphIndex) {
                    this.setData({ searchFlashParaIndex: -1 });
                }
            }, 1800);
        });
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
    toggleReadComplete() {
        if (!(0, api_1.hasToken)()) {
            (0, read_complete_1.promptLoginForReadComplete)();
            return;
        }
        const boxId = this.data.boxId;
        const next = !this.data.isReadComplete;
        const run = async () => {
            try {
                if (next) {
                    await (0, read_complete_1.markBoxReadComplete)(boxId);
                    wx.showToast({ title: '已标记读完', icon: 'success' });
                }
                else {
                    await (0, read_complete_1.unmarkBoxReadComplete)(boxId);
                    wx.showToast({ title: '已取消标记', icon: 'none' });
                }
                this.setData({ isReadComplete: next });
            }
            catch (e) {
                const msg = e instanceof Error ? e.message : '操作失败';
                wx.showToast({ title: msg, icon: 'none' });
            }
        };
        void run();
    },
    hideSelectionBar() {
        this.setData({
            selectionBarVisible: false,
            selectionBarText: '',
        });
        if (this.data.showOriginal)
            this.clearOriginalSelection();
        else
            this.clearDetailSelection();
    },
    onOriginalSheetTap() {
        if (this.data.selectionBarVisible)
            this.hideSelectionBar();
    },
    onDetailSelectionChange(e) {
        if (this.data.tab !== 'content' || this.data.showOriginal || this.data.showContentSearch)
            return;
        const detail = (e.detail || {});
        const selected = String(detail.selectedString || '').trim();
        if (detail.isCollapsed || !selected) {
            this.hideSelectionBar();
            return;
        }
        const anchor = (0, selection_bar_position_1.resolveSelectionBarAnchor)(detail.firstRangeRect, {
            left: this.data.selectionBarLeft,
            top: this.data.selectionBarTop,
            placement: this.data.selectionBarPlacement,
        }, { buttonCount: 5 });
        this.setData({
            selectionBarVisible: true,
            selectionBarText: selected,
            selectionBarLeft: anchor.left,
            selectionBarTop: anchor.top,
            selectionBarPlacement: anchor.placement,
            correctionSourceType: 'box_detail_selection',
        });
    },
    onOriginalSelectionChange(e) {
        if (!this.data.showOriginal)
            return;
        const detail = (e.detail || {});
        const selected = String(detail.selectedString || '').trim();
        if (detail.isCollapsed || !selected) {
            this.hideSelectionBar();
            return;
        }
        const anchor = (0, selection_bar_position_1.resolveSelectionBarAnchor)(detail.firstRangeRect, {
            left: this.data.selectionBarLeft,
            top: this.data.selectionBarTop,
            placement: this.data.selectionBarPlacement,
        }, { buttonCount: 4 });
        this.setData({
            selectionBarVisible: true,
            selectionBarText: selected,
            selectionBarLeft: anchor.left,
            selectionBarTop: anchor.top,
            selectionBarPlacement: anchor.placement,
            correctionSourceType: 'box_original_selection',
        });
    },
    async onSelectionShare() {
        const text = this.data.selectionBarText;
        this.hideSelectionBar();
        if (!text)
            return;
        await this.openSharePoster(text);
    },
    closeSharePoster() {
        wx.hideLoading();
        this.setData({ sharePosterVisible: false });
    },
    onSelectionCopy() {
        const text = this.data.selectionBarText;
        this.hideSelectionBar();
        if (!text)
            return;
        wx.setClipboardData({
            data: text,
            success: () => wx.showToast({ title: '已复制', icon: 'success' }),
        });
    },
    onSelectionQuery() {
        const text = this.data.selectionBarText;
        this.hideSelectionBar();
        if (!text)
            return;
        this.setData({
            dictionaryVisible: true,
            dictionaryQuery: text,
        });
    },
    closeDictionary() {
        this.setData({ dictionaryVisible: false, dictionaryQuery: '' });
        this.clearDetailSelection();
    },
    onSelectionCorrection() {
        const text = this.data.selectionBarText;
        this.hideSelectionBar();
        if (!text)
            return;
        this.openCorrectionModal(text);
    },
    onSelectionNote() {
        if (this.data.showOriginal)
            return;
        const text = this.data.selectionBarText;
        this.hideSelectionBar();
        if (!text)
            return;
        this.openNoteModal(text);
    },
    applyDetailHighlights() {
        const highlights = this.data.detailHighlights;
        const focusId = this.data.focusNoteId || 0;
        const rawParas = this._rawDetailParagraphs.length
            ? this._rawDetailParagraphs
            : this.data.detailParagraphs;
        const rawBlurb = this._rawBlurbSegs.length ? this._rawBlurbSegs : this.data.blurbSegs;
        this.setData({
            detailParagraphs: rawParas.map((p) => ({
                plain: p.plain,
                segs: (0, note_highlight_1.applyHighlightsToSegs)(p.segs, highlights, focusId),
            })),
            blurbSegs: (0, note_highlight_1.applyHighlightsToSegs)(rawBlurb, highlights, focusId),
        });
    },
    async loadDetailHighlights() {
        const boxId = this.data.boxId;
        if (!boxId || !(0, api_1.hasToken)())
            return;
        try {
            const highlights = await (0, note_1.fetchNoteHighlights)(boxId, 'box_detail_selection');
            this.setData({ detailHighlights: highlights });
            this.applyDetailHighlights();
        }
        catch {
            // 未登录或接口失败时保持原文
        }
    },
    async loadRelationHighlights() {
        const boxId = this.data.boxId;
        if (!boxId || !(0, api_1.hasToken)())
            return;
        try {
            const highlights = await (0, note_1.fetchNoteHighlights)(boxId, 'relation_graph_selection');
            this.setData({
                relationNotedNames: highlights.map((h) => h.selectedText).filter(Boolean),
            });
        }
        catch {
            this.setData({ relationNotedNames: [] });
        }
    },
    scrollToNoteAnchor(noteId) {
        if (!noteId)
            return;
        const id = (0, note_highlight_1.highlightAnchorId)(noteId);
        this.setData({ noteScrollIntoView: '' }, () => {
            this.setData({ noteScrollIntoView: id });
        });
    },
    focusRelationNoteIfNeeded() {
        var _a;
        const name = String(this._focusNoteName || '').trim();
        if (!name)
            return;
        const c = this.selectComponent('#bdRelationGraph');
        (_a = c === null || c === void 0 ? void 0 : c.focusNodeByName) === null || _a === void 0 ? void 0 : _a.call(c, name);
    },
    openNoteModal(selectedText) {
        this.clearDetailSelection();
        (0, note_1.requireLoginForNote)(() => {
            var _a;
            const header = this.data.header;
            const { civ, dynasty } = readBoxLocationNames(header === null || header === void 0 ? void 0 : header.box);
            this.setData({
                noteVisible: true,
                noteSubmitting: false,
                noteSelectedText: selectedText,
                noteBoxTitle: ((_a = header === null || header === void 0 ? void 0 : header.box) === null || _a === void 0 ? void 0 : _a.title) || this.data.navTitle,
                noteCivilizationName: civ,
                noteDynastyName: dynasty,
            });
        });
    },
    closeNote() {
        this.setData({ noteVisible: false, noteSubmitting: false });
        this.clearDetailSelection();
    },
    async onNoteSubmit(e) {
        var _a;
        const noteText = String(((_a = e.detail) === null || _a === void 0 ? void 0 : _a.noteText) || '');
        const boxId = this.data.boxId;
        if (!boxId || this.data.noteSubmitting)
            return;
        this.setData({ noteSubmitting: true });
        try {
            const sourceType = (this.data.correctionSourceType || 'box_detail_selection');
            await (0, note_1.submitNote)({
                boxId,
                sourceType,
                selectedText: this.data.noteSelectedText,
                noteText,
            });
            wx.showToast({ title: '笔记已保存', icon: 'success' });
            this.setData({ noteVisible: false, noteSubmitting: false });
            if (sourceType === 'relation_graph_selection') {
                void this.loadRelationHighlights();
            }
            else {
                void this.loadDetailHighlights();
            }
        }
        catch (err) {
            this.setData({ noteSubmitting: false });
            const msg = err instanceof Error ? err.message : '保存失败，请稍后重试';
            wx.showToast({ title: msg, icon: 'none' });
        }
    },
    openCorrectionModal(selectedText) {
        this.clearDetailSelection();
        (0, correction_1.requireLoginForCorrection)(() => {
            const header = this.data.header;
            const box = header === null || header === void 0 ? void 0 : header.box;
            const { civ, dynasty } = readBoxLocationNames(box);
            this.setData({
                correctionVisible: true,
                correctionSubmitting: false,
                correctionBoxTitle: (box === null || box === void 0 ? void 0 : box.title) || this.data.navTitle,
                correctionCivilizationName: civ,
                correctionDynastyName: dynasty,
                correctionSelectedText: selectedText,
            });
        });
    },
    closeCorrection() {
        this.setData({ correctionVisible: false, correctionSubmitting: false });
        this.clearDetailSelection();
    },
    async onCorrectionSubmit(e) {
        var _a;
        const reason = String(((_a = e.detail) === null || _a === void 0 ? void 0 : _a.reason) || '');
        const boxId = this.data.boxId;
        if (!boxId || this.data.correctionSubmitting)
            return;
        this.setData({ correctionSubmitting: true });
        try {
            await (0, correction_1.submitCorrection)({
                boxId,
                sourceType: this.data.correctionSourceType || 'box_detail_selection',
                reason,
                selectedText: this.data.correctionSelectedText,
            });
            wx.showToast({ title: '提交成功，感谢反馈', icon: 'success' });
            this.setData({ correctionVisible: false, correctionSubmitting: false });
        }
        catch (err) {
            this.setData({ correctionSubmitting: false });
            const msg = err instanceof Error ? err.message : '提交失败，请稍后重试';
            wx.showToast({ title: msg, icon: 'none' });
        }
    },
});
