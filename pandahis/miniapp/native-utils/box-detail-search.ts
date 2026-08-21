/** 史略详情正文页内搜索：按段匹配、摘录、关键词高亮 */

export type DetailSearchSeg = {
  text: string
  hl: boolean
}

export type DetailSearchHit = {
  /** 列表 key */
  key: string
  /** 段落下标（detailParagraphs / blurb 视为 0） */
  paragraphIndex: number
  /** 同段内第几次命中（0-based） */
  hitIndex: number
  /** 命中在段落 plain 中的起始下标 */
  matchStart: number
  /** 摘录纯文本 */
  excerpt: string
  /** 摘录高亮片段 */
  segs: DetailSearchSeg[]
}

/** 约 3 行中文（详情字号下） */
export const DETAIL_SEARCH_MAX_EXCERPT = 96

/** 单次搜索最多返回条数，避免高频字撑爆 setData */
export const DETAIL_SEARCH_MAX_RESULTS = 50

const SENTENCE_END = /[。！？；\n]/

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/** 在 plain 中找全部不重叠命中起点（大小写不敏感） */
export function findKeywordMatches(plain: string, keyword: string): number[] {
  const needle = String(keyword || '').trim()
  const hay = String(plain || '')
  if (!needle || !hay) return []
  const re = new RegExp(escapeRegExp(needle), 'gi')
  const starts: number[] = []
  let m: RegExpExecArray | null
  while ((m = re.exec(hay)) !== null) {
    starts.push(m.index)
    if (m[0].length === 0) {
      re.lastIndex += 1
      if (re.lastIndex > hay.length) break
    }
  }
  return starts
}

type SentenceSpan = { start: number; end: number }

/** 按句号类标点切句，标点归入前句 */
export function splitSentenceSpans(plain: string): SentenceSpan[] {
  const text = String(plain || '')
  if (!text) return []
  const spans: SentenceSpan[] = []
  let start = 0
  for (let i = 0; i < text.length; i += 1) {
    if (SENTENCE_END.test(text[i]!)) {
      const end = i + 1
      if (end > start) spans.push({ start, end })
      start = end
    }
  }
  if (start < text.length) spans.push({ start, end: text.length })
  return spans.length ? spans : [{ start: 0, end: text.length }]
}

function sentenceIndexAt(spans: SentenceSpan[], offset: number): number {
  for (let i = 0; i < spans.length; i += 1) {
    const s = spans[i]!
    if (offset >= s.start && offset < s.end) return i
    if (offset === s.end && i === spans.length - 1) return i
  }
  // 命中恰在句末标点上
  for (let i = 0; i < spans.length; i += 1) {
    const s = spans[i]!
    if (offset >= s.start && offset <= s.end) return i
  }
  return Math.max(0, spans.length - 1)
}

/**
 * 取命中处前后最多 2 句，总长不超过 maxLen。
 * 优先：含命中句；若短则再拼下一句，否则拼上一句（二者取一，不拼成三句）。
 */
export function buildExcerptAround(
  plain: string,
  matchStart: number,
  matchLen: number,
  maxLen: number = DETAIL_SEARCH_MAX_EXCERPT
): { excerpt: string; excerptStart: number } {
  const text = String(plain || '')
  const len = Math.max(0, matchLen)
  const start = Math.max(0, Math.min(matchStart, text.length))
  if (!text) return { excerpt: '', excerptStart: 0 }

  const spans = splitSentenceSpans(text)
  const si = sentenceIndexAt(spans, start)
  let from = spans[si]!.start
  let to = spans[si]!.end

  const tryExpand = (nextFrom: number, nextTo: number): boolean => {
    if (nextTo - nextFrom <= maxLen) {
      from = nextFrom
      to = nextTo
      return true
    }
    return false
  }

  // 优先下一句；放不下再试上一句（始终最多两句）
  let expanded = false
  if (si + 1 < spans.length) {
    expanded = tryExpand(from, spans[si + 1]!.end)
  }
  if (!expanded && si > 0) {
    tryExpand(spans[si - 1]!.start, to)
  }

  // 仍超长：以命中为中心裁切
  if (to - from > maxLen) {
    const half = Math.floor((maxLen - len) / 2)
    from = Math.max(0, start - Math.max(0, half))
    to = Math.min(text.length, from + maxLen)
    if (to - from < maxLen) from = Math.max(0, to - maxLen)
  }

  const rawSlice = text.slice(from, to)
  const lead = (rawSlice.match(/^\s+/) || [''])[0].length
  const trail = (rawSlice.match(/\s+$/) || [''])[0].length
  const excerptStart = from + lead
  const excerptBody = text.slice(excerptStart, to - trail)
  const prefix = excerptStart > 0 ? '…' : ''
  const suffix = excerptStart + excerptBody.length < text.length ? '…' : ''
  return { excerpt: `${prefix}${excerptBody}${suffix}`, excerptStart }
}

/** 在摘录上高亮 keyword（相对 plain 的 matchStart / matchLen） */
export function highlightExcerptSegs(
  plain: string,
  excerpt: string,
  excerptStart: number,
  keyword: string,
  matchStart: number
): DetailSearchSeg[] {
  const needle = String(keyword || '').trim()
  const body = String(excerpt || '')
  if (!body) return []

  // 去掉展示用省略号后对齐 plain 偏移
  let local = body
  let base = excerptStart
  if (local.startsWith('…')) {
    local = local.slice(1)
    // excerptStart 已是正文起点
  }
  if (local.endsWith('…')) {
    local = local.slice(0, -1)
  }

  if (!needle || !local) {
    return body ? [{ text: body, hl: false }] : []
  }

  const rel = matchStart - base
  const nLen = needle.length

  // 在 local 内标记本次命中；同时把摘录内其它同词也标上
  const marks = new Array(local.length).fill(false)
  const re = new RegExp(escapeRegExp(needle), 'gi')
  let m: RegExpExecArray | null
  while ((m = re.exec(local)) !== null) {
    for (let k = 0; k < m[0].length; k += 1) marks[m.index + k] = true
    if (m[0].length === 0) {
      re.lastIndex += 1
      if (re.lastIndex > local.length) break
    }
  }
  // 确保主命中也被标上（防 trim/省略号错位）
  if (rel >= 0 && rel < local.length) {
    for (let k = 0; k < nLen && rel + k < local.length; k += 1) marks[rel + k] = true
  }

  const segs: DetailSearchSeg[] = []
  let i = 0
  while (i < local.length) {
    const hl = marks[i]!
    let j = i + 1
    while (j < local.length && marks[j] === hl) j += 1
    segs.push({ text: local.slice(i, j), hl })
    i = j
  }

  // 还原首尾省略号
  const out: DetailSearchSeg[] = []
  if (body.startsWith('…')) out.push({ text: '…', hl: false })
  out.push(...segs)
  if (body.endsWith('…')) out.push({ text: '…', hl: false })
  return out.length ? out : [{ text: body, hl: false }]
}

export function searchDetailParagraphs(
  paragraphs: string[],
  keyword: string,
  maxExcerpt: number = DETAIL_SEARCH_MAX_EXCERPT,
  maxResults: number = DETAIL_SEARCH_MAX_RESULTS
): DetailSearchHit[] {
  const needle = String(keyword || '').trim()
  if (!needle) return []
  const hits: DetailSearchHit[] = []
  for (let paragraphIndex = 0; paragraphIndex < paragraphs.length; paragraphIndex += 1) {
    const text = String(paragraphs[paragraphIndex] || '')
    const starts = findKeywordMatches(text, needle)
    for (let hitIndex = 0; hitIndex < starts.length; hitIndex += 1) {
      if (hits.length >= maxResults) return hits
      const matchStart = starts[hitIndex]!
      const { excerpt, excerptStart } = buildExcerptAround(text, matchStart, needle.length, maxExcerpt)
      const segs = highlightExcerptSegs(text, excerpt, excerptStart, needle, matchStart)
      hits.push({
        key: `p${paragraphIndex}-h${hitIndex}-${matchStart}`,
        paragraphIndex,
        hitIndex,
        matchStart,
        excerpt,
        segs,
      })
    }
  }
  return hits
}

export function detailParaAnchorId(paragraphIndex: number): string {
  return `detail-para-${paragraphIndex}`
}
