"use strict";
/** 史略详情正文页内搜索：按段匹配、摘录、关键词高亮 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.detailParaAnchorId = exports.searchDetailParagraphs = exports.highlightExcerptSegs = exports.buildExcerptAround = exports.splitSentenceSpans = exports.findKeywordMatches = exports.DETAIL_SEARCH_MAX_RESULTS = exports.DETAIL_SEARCH_MAX_EXCERPT = void 0;
/** 约 3 行中文（详情字号下） */
exports.DETAIL_SEARCH_MAX_EXCERPT = 96;
/** 单次搜索最多返回条数，避免高频字撑爆 setData */
exports.DETAIL_SEARCH_MAX_RESULTS = 50;
const SENTENCE_END = /[。！？；\n]/;
function escapeRegExp(s) {
    return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}
/** 在 plain 中找全部不重叠命中起点（大小写不敏感） */
function findKeywordMatches(plain, keyword) {
    const needle = String(keyword || '').trim();
    const hay = String(plain || '');
    if (!needle || !hay)
        return [];
    const re = new RegExp(escapeRegExp(needle), 'gi');
    const starts = [];
    let m;
    while ((m = re.exec(hay)) !== null) {
        starts.push(m.index);
        if (m[0].length === 0) {
            re.lastIndex += 1;
            if (re.lastIndex > hay.length)
                break;
        }
    }
    return starts;
}
exports.findKeywordMatches = findKeywordMatches;
/** 按句号类标点切句，标点归入前句 */
function splitSentenceSpans(plain) {
    const text = String(plain || '');
    if (!text)
        return [];
    const spans = [];
    let start = 0;
    for (let i = 0; i < text.length; i += 1) {
        if (SENTENCE_END.test(text[i])) {
            const end = i + 1;
            if (end > start)
                spans.push({ start, end });
            start = end;
        }
    }
    if (start < text.length)
        spans.push({ start, end: text.length });
    return spans.length ? spans : [{ start: 0, end: text.length }];
}
exports.splitSentenceSpans = splitSentenceSpans;
function sentenceIndexAt(spans, offset) {
    for (let i = 0; i < spans.length; i += 1) {
        const s = spans[i];
        if (offset >= s.start && offset < s.end)
            return i;
        if (offset === s.end && i === spans.length - 1)
            return i;
    }
    // 命中恰在句末标点上
    for (let i = 0; i < spans.length; i += 1) {
        const s = spans[i];
        if (offset >= s.start && offset <= s.end)
            return i;
    }
    return Math.max(0, spans.length - 1);
}
/**
 * 取命中处前后最多 2 句，总长不超过 maxLen。
 * 优先：含命中句；若短则再拼下一句，否则拼上一句（二者取一，不拼成三句）。
 */
function buildExcerptAround(plain, matchStart, matchLen, maxLen = exports.DETAIL_SEARCH_MAX_EXCERPT) {
    const text = String(plain || '');
    const len = Math.max(0, matchLen);
    const start = Math.max(0, Math.min(matchStart, text.length));
    if (!text)
        return { excerpt: '', excerptStart: 0 };
    const spans = splitSentenceSpans(text);
    const si = sentenceIndexAt(spans, start);
    let from = spans[si].start;
    let to = spans[si].end;
    const tryExpand = (nextFrom, nextTo) => {
        if (nextTo - nextFrom <= maxLen) {
            from = nextFrom;
            to = nextTo;
            return true;
        }
        return false;
    };
    // 优先下一句；放不下再试上一句（始终最多两句）
    let expanded = false;
    if (si + 1 < spans.length) {
        expanded = tryExpand(from, spans[si + 1].end);
    }
    if (!expanded && si > 0) {
        tryExpand(spans[si - 1].start, to);
    }
    // 仍超长：以命中为中心裁切
    if (to - from > maxLen) {
        const half = Math.floor((maxLen - len) / 2);
        from = Math.max(0, start - Math.max(0, half));
        to = Math.min(text.length, from + maxLen);
        if (to - from < maxLen)
            from = Math.max(0, to - maxLen);
    }
    const rawSlice = text.slice(from, to);
    const lead = (rawSlice.match(/^\s+/) || [''])[0].length;
    const trail = (rawSlice.match(/\s+$/) || [''])[0].length;
    const excerptStart = from + lead;
    const excerptBody = text.slice(excerptStart, to - trail);
    const prefix = excerptStart > 0 ? '…' : '';
    const suffix = excerptStart + excerptBody.length < text.length ? '…' : '';
    return { excerpt: `${prefix}${excerptBody}${suffix}`, excerptStart };
}
exports.buildExcerptAround = buildExcerptAround;
/** 在摘录上高亮 keyword（相对 plain 的 matchStart / matchLen） */
function highlightExcerptSegs(plain, excerpt, excerptStart, keyword, matchStart) {
    const needle = String(keyword || '').trim();
    const body = String(excerpt || '');
    if (!body)
        return [];
    // 去掉展示用省略号后对齐 plain 偏移
    let local = body;
    let base = excerptStart;
    if (local.startsWith('…')) {
        local = local.slice(1);
        // excerptStart 已是正文起点
    }
    if (local.endsWith('…')) {
        local = local.slice(0, -1);
    }
    if (!needle || !local) {
        return body ? [{ text: body, hl: false }] : [];
    }
    const rel = matchStart - base;
    const nLen = needle.length;
    // 在 local 内标记本次命中；同时把摘录内其它同词也标上
    const marks = new Array(local.length).fill(false);
    const re = new RegExp(escapeRegExp(needle), 'gi');
    let m;
    while ((m = re.exec(local)) !== null) {
        for (let k = 0; k < m[0].length; k += 1)
            marks[m.index + k] = true;
        if (m[0].length === 0) {
            re.lastIndex += 1;
            if (re.lastIndex > local.length)
                break;
        }
    }
    // 确保主命中也被标上（防 trim/省略号错位）
    if (rel >= 0 && rel < local.length) {
        for (let k = 0; k < nLen && rel + k < local.length; k += 1)
            marks[rel + k] = true;
    }
    const segs = [];
    let i = 0;
    while (i < local.length) {
        const hl = marks[i];
        let j = i + 1;
        while (j < local.length && marks[j] === hl)
            j += 1;
        segs.push({ text: local.slice(i, j), hl });
        i = j;
    }
    // 还原首尾省略号
    const out = [];
    if (body.startsWith('…'))
        out.push({ text: '…', hl: false });
    out.push(...segs);
    if (body.endsWith('…'))
        out.push({ text: '…', hl: false });
    return out.length ? out : [{ text: body, hl: false }];
}
exports.highlightExcerptSegs = highlightExcerptSegs;
function searchDetailParagraphs(paragraphs, keyword, maxExcerpt = exports.DETAIL_SEARCH_MAX_EXCERPT, maxResults = exports.DETAIL_SEARCH_MAX_RESULTS) {
    const needle = String(keyword || '').trim();
    if (!needle)
        return [];
    const hits = [];
    for (let paragraphIndex = 0; paragraphIndex < paragraphs.length; paragraphIndex += 1) {
        const text = String(paragraphs[paragraphIndex] || '');
        const starts = findKeywordMatches(text, needle);
        for (let hitIndex = 0; hitIndex < starts.length; hitIndex += 1) {
            if (hits.length >= maxResults)
                return hits;
            const matchStart = starts[hitIndex];
            const { excerpt, excerptStart } = buildExcerptAround(text, matchStart, needle.length, maxExcerpt);
            const segs = highlightExcerptSegs(text, excerpt, excerptStart, needle, matchStart);
            hits.push({
                key: `p${paragraphIndex}-h${hitIndex}-${matchStart}`,
                paragraphIndex,
                hitIndex,
                matchStart,
                excerpt,
                segs,
            });
        }
    }
    return hits;
}
exports.searchDetailParagraphs = searchDetailParagraphs;
function detailParaAnchorId(paragraphIndex) {
    return `detail-para-${paragraphIndex}`;
}
exports.detailParaAnchorId = detailParaAnchorId;
