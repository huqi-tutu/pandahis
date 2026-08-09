import { hasToken, request } from '../../../native-utils/api'
import {
  buildBoxNarrationScript,
  getNarrationState,
  seekNarration,
  seekNarrationPct,
  setPlaybackRate,
  startNarration,
  stopNarration,
  toggleNarrationPlayback,
  type NarrationState,
} from '../../../native-utils/box-narration'
import { encodePathSegment } from '../../../native-utils/encode-path-segment'
import { decodeQueryValue } from '../../../native-utils/query-value'
import {
  favoriteBox,
  fetchFavoritedBoxIdSet,
  promptLoginForFavorite,
  unfavoriteBox,
} from '../../../native-utils/favorite-box'
import { formatHistoryYear } from '../../../native-utils/year-format'
import { ROUTES, navigateTo } from '../../../native-utils/router'
import { buildSharePosterSheetState } from '../../../native-utils/share-poster-open'
import {
  requireLoginForCorrection,
  submitCorrection,
} from '../../../native-utils/correction'
import { categoryLabel, isPersonBoxCategory } from '../../../native-utils/category-label'
import {
  markBoxReadComplete,
  promptLoginForReadComplete,
  unmarkBoxReadComplete,
} from '../../../native-utils/read-complete'
import { resolveSelectionBarAnchor } from '../../../native-utils/selection-bar-position'
import { NARRATION_COVER_LOGO_URL } from '../../../native-utils/brand-assets'

type TabAccess = { locked?: boolean; lockedReason?: string | null; unlockAction?: { type?: string } | null }

type BoxHeader = {
  box: {
    id: string
    title: string
    subText: string
    blurb?: string | null
    categoryKey: string
    civilizationName?: string
    dynastyName?: string
    civilization_name?: string
    dynasty_name?: string
    startYear: number
    endYear: number
  }
  isFavorite: boolean
  isReadComplete: boolean
  tabSummary: { hasGraph: boolean; hasCritiques: boolean; hasRelics: boolean; hasOriginal: boolean }
  access: {
    boxLocked: boolean
    tabs: { graph: TabAccess; critique: TabAccess; relic: TabAccess; original: TabAccess }
  }
}

type CritiqueVm = {
  id?: number | null
  title?: string | null
  blurb?: string | null
  author?: string | null
  eraText?: string | null
  year?: number | null
  content?: string | null
  source?: string | null
  displayAuthor: string
  eraMeta: string
  bodyQuote: string
  avatarLetter: string
  cardTitle: string
  cardMeta: string
  cardSummary: string
  _k: number
}

type RelicVm = {
  id?: number | null
  name: string
  imageUrl?: string | null
  summary?: string | null
  description?: string | null
  museum: string
  priorityCode?: string | null
  thumbLabel: string
  teaser: string
  location: string
  cardMeta: string
}

function relicThumbLabel(name: string): string {
  const n = (name || '').trim()
  if (!n) return '—'
  if (n.length <= 4) return n
  return n.slice(-4)
}

/** 从「史略名称·评述角度」取 · 后的评述角度 */
function critiqueAngleTitle(fullTitle: string): string {
  const t = String(fullTitle || '').trim()
  if (!t) return ''
  const dotIdx = t.indexOf('·')
  if (dotIdx >= 0) {
    const rest = t.slice(dotIdx + 1).trim()
    return rest || t
  }
  return t
}

const TRADITIONAL_DYNASTIES = [
  '北宋', '南宋', '西汉', '东汉', '南北朝',
  '战国末期', '战国', '春秋末期', '春秋', '五帝', '三皇', '上古',
  '东晋', '西晋', '三国', '五代', '魏晋',
  '夏', '商', '周', '秦', '隋', '唐', '宋', '元', '明', '清',
] as const

const MODERN_PERIOD_LABELS = [
  '近现代', '近代', '现代', '当代', '中华民国', '二十世纪', '20世纪',
] as const

function isYearLikeFragment(text: string): boolean {
  const s = String(text || '').trim()
  if (!s) return false
  return /^(约)?\s*公元前/u.test(s)
    || /^(约)?\s*[\d０-９]+/u.test(s)
    || /世纪|年代|^\d+年$/u.test(s)
}

/** 从评述年代取传统朝代（清及以前），去掉括号内年份与 · 后的具体时间 */
function critiqueDynastyLabel(eraText: string): string {
  let s = String(eraText || '').trim()
  if (!s) return ''

  const trailing = s.match(/[（(]([^）)]+)[）)]\s*$/)
  const beforeParens = s.replace(/[（(][^）)]+[）)]/gu, '').trim()
  if (isYearLikeFragment(beforeParens) && trailing && isDynastyLikeLabel(trailing[1])) {
    s = trailing[1].trim()
  } else {
    s = s.replace(/[（(][^）)]+[）)]/gu, '').trim()
  }

  for (const sep of ['·', '・']) {
    if (s.includes(sep)) {
      const head = s.split(sep)[0]?.trim()
      if (head) {
        s = head
        break
      }
    }
  }

  s = s.replace(/\s+约?公元前.*$/u, '').trim()
  s = s.replace(/[，,]\s*约?.*$/u, '').trim()
  s = s.replace(/\s+约?\d+.*$/u, '').trim()

  for (const d of [...TRADITIONAL_DYNASTIES, ...MODERN_PERIOD_LABELS].sort((a, b) => b.length - a.length)) {
    if (s === d || s.startsWith(d)) return d
  }

  const short = s.match(/^(清|明|元|宋|唐|隋|秦|周|商|夏)/u)
  if (short) return short[1]

  return s
}

function isDynastyLikeLabel(text: string): boolean {
  const s = String(text || '').trim()
  if (!s) return false
  if ([...TRADITIONAL_DYNASTIES, ...MODERN_PERIOD_LABELS].some((d) => s === d || s.startsWith(d))) return true
  return /^(春|战|西|东|南|北|五|三|上|近|现)/u.test(s)
}

function isTraditionalDynasty(label: string): boolean {
  const s = String(label || '').trim()
  if (!s || isYearLikeFragment(s)) return false
  if (MODERN_PERIOD_LABELS.some((m) => s === m || s.startsWith(m))) return false
  return TRADITIONAL_DYNASTIES.some((d) => s === d || s.startsWith(d))
    || /^(清|明|元|宋|唐|隋|秦|周|商|夏)/u.test(s)
}

/** 1912 年后无法归入传统朝代时，提取年份/世纪/年代 */
function critiqueYearLabel(eraText: string): string {
  const raw = String(eraText || '').trim()
  if (!raw) return ''

  const parenParts: string[] = []
  const parenRe = /[（(]([^）)]+)[）)]/gu
  let parenMatch: RegExpExecArray | null
  while ((parenMatch = parenRe.exec(raw)) !== null) {
    const part = parenMatch[1].trim()
    if (isYearLikeFragment(part)) parenParts.push(part)
  }
  if (parenParts.length) {
    const exact = parenParts.find((t) => /^\d+年$/u.test(t))
    if (exact) return exact
    const withYear = parenParts.find((t) => /\d/u.test(t))
    if (withYear) return withYear.replace(/^约\s*/u, '约')
  }

  for (const sep of ['·', '・']) {
    if (raw.includes(sep)) {
      const tail = raw.split(sep).slice(1).join(sep).replace(/[（(][^）)]+[）)]/gu, '').trim()
      if (tail && isYearLikeFragment(tail)) return tail.replace(/^约\s*/u, '约')
    }
  }

  const stripped = raw.replace(/[（(][^）)]+[）)]/gu, '').trim()
  if (isYearLikeFragment(stripped)) return stripped.replace(/^约\s*/u, '约')

  const embedded = stripped.match(/(\d{4}年(?:代)?|20世纪[^\s，,）)]*|约?\d+世纪[^\s，,）)]*|\d{2,4}年代)/u)
  if (embedded) return embedded[1]

  return ''
}

/** 列表/详情时代展示：传统朝代只显示朝代；1912 年后只显示年份，不同时出现 */
function critiqueEraDisplay(eraText: string): string {
  const era = String(eraText || '').trim()
  if (!era) return ''

  const dynasty = critiqueDynastyLabel(era)
  if (isTraditionalDynasty(dynasty)) return dynasty

  const year = critiqueYearLabel(era)
  if (year) return year

  if (dynasty && !isYearLikeFragment(dynasty)) return dynasty
  return ''
}

function mapCritiqueItems(raw: any[]): CritiqueVm[] {
  return (raw || []).map((it, idx) => {
    const idNum = Number(it.id)
    const author = String(it.author || '').trim()
    const title = String(it.title || '').trim()
    const angleTitle = critiqueAngleTitle(title)
    const displayAuthor = author || angleTitle || title || '佚名'
    const era = String(it.eraText || '').trim()
    const dynasty = critiqueEraDisplay(era)
    const content = String(it.content || '').trim()
    const blurb = String(it.blurb || '').trim()
    const bodyQuote = content || blurb
    const source = String(it.source || it.book || '').trim()
    const cardTitle = angleTitle || displayAuthor
    const metaParts: string[] = []
    if (title && author) metaParts.push(author)
    if (dynasty) metaParts.push(dynasty)
    if (source) metaParts.push(source)
    const cardMeta = metaParts.filter(Boolean).join(' · ')
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
    }
  })
}

function mapRelicItems(raw: any[]): RelicVm[] {
  return (raw || []).map((it) => {
    const idNum = Number(it.id)
    const full = String(it.description || it.summary || '').trim()
    // 列表简介：优先用服务端 summary；勿把截断摘要拼进详情全文
    const teaser = String(it.summary || it.description || '').trim()
    const museum = it.museum || '馆藏待补充'
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
    }
  })
}

function formatDetailMetaLine(subText: string): string {
  return String(subText || '')
    .replace(/\s*~\s*/g, ' — ')
    .replace(/~/g, '—')
    .replace(/\s*·\s*/g, ' · ')
    .trim()
}

function yearLabel(y: number): string {
  if (!Number.isFinite(y) || y === 0) return ''
  return formatHistoryYear(y)
}

/** 君王/诸侯的起止年语义为在位年，展示时加「在位」前缀，避免被读成生卒 */
const REIGN_YEAR_CATEGORY_KEYS = new Set(['junji', 'zhuhou'])

function buildDetailMetaFromBox(box: BoxHeader['box']): string {
  const cat = String(box.categoryKey || '').trim()
  const y0 = yearLabel(box.startYear)
  const y1 = yearLabel(box.endYear)
  const raw = box as Record<string, unknown>
  const civ = String(raw.civilizationName ?? raw.civilization_name ?? '').trim()
  const catName = categoryLabel(cat)

  if (REIGN_YEAR_CATEGORY_KEYS.has(cat) && y0) {
    const range = y1 && y1 !== y0 ? `${y0} — ${y1}` : y0
    const parts = [`在位 ${range}`]
    if (civ) parts.push(civ)
    if (catName) parts.push(catName)
    return parts.join(' · ')
  }

  const fromSub = formatDetailMetaLine(box.subText)
  if (fromSub) return fromSub
  const parts: string[] = []
  if (y0 && y1 && y0 !== y1) parts.push(`${y0} — ${y1}`)
  else if (y0) parts.push(y0)
  return parts.join(' · ')
}

function readBoxLocationNames(box: BoxHeader['box'] | null | undefined): { civ: string; dynasty: string } {
  if (!box) return { civ: '', dynasty: '' }
  const raw = box as Record<string, unknown>
  return {
    civ: String(raw.civilizationName ?? raw.civilization_name ?? '').trim(),
    dynasty: String(raw.dynastyName ?? raw.dynasty_name ?? '').trim(),
  }
}

type TextSegment = { text: string; bold: boolean }

type DetailParagraph = {
  segs: TextSegment[]
  plain: string
}

const QUOTE_CLOSER: Record<string, string> = { '「': '」', '『': '』' }
const QUOTE_OPENERS = new Set(Object.keys(QUOTE_CLOSER))
const QUOTE_CLOSERS = new Set(Object.values(QUOTE_CLOSER))

function stripMarkdownBold(text: string): string {
  return text.replace(/\*\*([^*]+)\*\*/g, '$1')
}

const MIN_QUOTE_BOLD_CHARS = 5

const REF_PARA_RE = /^[\s*]*参考著作\s*[:：]/

/** 参考著作节：标题加粗 + 编号书目列表（兼容 *参考著作* / - 列表 / 同行连写） */
function parseReferenceParagraph(raw: string): DetailParagraph {
  let body = raw.trim()
  body = body.replace(/^[\s*]*参考著作\s*[:：]\s*[\s*]*/u, '')
  body = body.replace(/^\*+|\*+$/g, '').trim()

  const titles: string[] = []
  const bookRe = /《[^》]+》/g
  let m: RegExpExecArray | null
  while ((m = bookRe.exec(body)) !== null) {
    titles.push(m[0])
  }

  const segs: TextSegment[] = [{ text: '参考著作：', bold: true }]
  if (!titles.length) {
    if (body) segs.push({ text: `\n${body}`, bold: false })
    const plain = segs.map((s) => s.text).join('')
    return { segs, plain }
  }
  titles.forEach((t, i) => {
    segs.push({ text: '\n', bold: false })
    segs.push({ text: `${i + 1}. ${t}`, bold: false })
  })
  const plain = segs.map((s) => s.text).join('')
  return { segs, plain }
}

/** 直角引号「」『』内正文 ≥5 字时，引号与原文整体加粗；正文勿写 ** markdown 加粗 */
function parseDisplaySegments(raw: string): TextSegment[] {
  const text = stripMarkdownBold(raw)
  type Piece = { text: string; bold: boolean | null }
  const pieces: Piece[] = []
  type Frame = { inner: string; pieceStart: number }
  const stack: Frame[] = []

  let plain = ''
  const flushPlain = () => {
    if (!plain) return
    pieces.push({ text: plain, bold: null })
    plain = ''
  }

  const markRange = (start: number, end: number, bold: boolean) => {
    for (let i = start; i <= end; i++) {
      const piece = pieces[i]
      if (!piece) continue
      if (bold) {
        if (piece.bold !== false) piece.bold = true
      } else {
        piece.bold = false
      }
    }
  }

  for (let i = 0; i < text.length; i++) {
    const ch = text[i]
    if (QUOTE_OPENERS.has(ch)) {
      flushPlain()
      for (const frame of stack) frame.inner += ch
      stack.push({ inner: '', pieceStart: pieces.length })
      pieces.push({ text: ch, bold: null })
      continue
    }
    if (QUOTE_CLOSERS.has(ch)) {
      const frame = stack.pop()
      if (!frame) {
        plain += ch
        continue
      }
      for (const f of stack) f.inner += ch
      pieces.push({ text: ch, bold: null })
      markRange(frame.pieceStart, pieces.length - 1, frame.inner.length >= MIN_QUOTE_BOLD_CHARS)
      continue
    }
    if (stack.length) {
      for (const frame of stack) frame.inner += ch
      pieces.push({ text: ch, bold: null })
    } else {
      plain += ch
    }
  }
  flushPlain()

  const segs: TextSegment[] = []
  for (const piece of pieces) {
    const bold = piece.bold === true
    const prev = segs[segs.length - 1]
    if (prev && prev.bold === bold) {
      prev.text += piece.text
    } else {
      segs.push({ text: piece.text, bold })
    }
  }
  return segs
}

function splitDetailParagraphs(md: string): DetailParagraph[] {
  const raw = String(md || '').trim()
  if (!raw) return []
  const fixed = raw.replace(/\\n/g, '\n')
  const parts = fixed.split(/\n{2,}/).map((s) => s.trim()).filter(Boolean)
  const list = parts.length ? parts : [fixed]
  return list.map((p) => {
    if (REF_PARA_RE.test(p)) {
      return parseReferenceParagraph(p)
    }
    const segs = parseDisplaySegments(p)
    const plain = segs.map((s) => s.text).join('')
    return { segs, plain }
  })
}



Page({
  data: {
    boxId: '',
    navTitle: '史略详情',
    header: null as BoxHeader | null,
    tabTop: 88,
    bodyTop: 160,
    graphCanvasH: 400,
    critColors: ['#A2734F', '#63899C', '#B99D5B', '#9A798F', '#7D8A6A', '#A46A65'],
    tab: 'content' as 'content' | 'relations' | 'reviews' | 'relics',
    showRelationsTab: false,
    isFav: false,
    isReadComplete: false,
    detailMd: '',
    detailParagraphs: [] as DetailParagraph[],
    detailMetaDisplay: '',
    detailReady: false,
    detailErr: '',
    graph: { centerNodeKey: '', nodes: [] as any[], edges: [] as any[] },
    graphNodeCount: 0,
    graphPhase: 'idle' as 'idle' | 'loading' | 'ready' | 'error',
    graphReady: false,
    graphLoading: false,
    graphRenderHint: '',
    graphErr: '',
    critiques: [] as CritiqueVm[],
    critReady: false,
    critErr: '',
    relics: [] as RelicVm[],
    relicReady: false,
    relicErr: '',
    detailFetched: false,
    graphFetched: false,
    critFetched: false,
    relicFetched: false,
    narrationState: 'idle' as NarrationState,
    narrationCoverLogoUrl: NARRATION_COVER_LOGO_URL,
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
    correctionVisible: false,
    dictionaryVisible: false,
    dictionaryQuery: '',
    correctionSubmitting: false,
    correctionBoxTitle: '',
    correctionCivilizationName: '',
    correctionDynastyName: '',
    correctionSelectedText: '',
    selectionBarVisible: false,
    selectionBarLeft: 0,
    selectionBarTop: 0,
    selectionBarPlacement: 'above' as 'above' | 'below',
    selectionBarText: '',
    selectionMountKey: 1,
    sharePosterVisible: false,
    sharePosterQuote: '',
    sharePosterSourceLine1: '',
    sharePosterSourceLine2: '',
    sharePosterUserName: '历史读者',
    sharePosterUserAvatar: '',
    sharePosterExcerptDate: '',
  },
  _selectionContext: null as WechatMiniprogram.IAnyObject | null,
  /** 详情 Tab 实时滚动位置（沉浸态判定用） */
  _detailScrollTop: 0,
  /** 离开详情 Tab 时缓存的阅读进度（当次访问有效） */
  _contentScrollTop: 0,
  _contentReadingProgress: 0,
  _tabBarPx: 0,
  _suppressChromeHide: false,
  _suppressChromeHideTimer: null as ReturnType<typeof setTimeout> | null,
  _restoreContentScrollTimer: null as ReturnType<typeof setTimeout> | null,
  _rawOriginalRef: null,
  onReady() {
    this.bindDetailSelectionContext()
  },
  bindDetailSelectionContext() {
    wx.createSelectorQuery()
      .in(this)
      .select('#detailBodySelection')
      .context((res) => {
        this._selectionContext = (res as WechatMiniprogram.IAnyObject)?.context ?? null
      })
      .exec()
  },
  clearDetailSelection() {
    const ctx = this._selectionContext as { removeSelection?: () => void } | null
    if (ctx && typeof ctx.removeSelection === 'function') {
      try {
        ctx.removeSelection()
        return
      } catch {
        // fallback to remount below
      }
    }
    this.setData({ selectionMountKey: this.data.selectionMountKey + 1 }, () => {
      this.bindDetailSelectionContext()
    })
  },
  onUnload() {
    if (this._suppressChromeHideTimer) {
      clearTimeout(this._suppressChromeHideTimer)
      this._suppressChromeHideTimer = null
    }
    if (this._restoreContentScrollTimer) {
      clearTimeout(this._restoreContentScrollTimer)
      this._restoreContentScrollTimer = null
    }
    stopNarration()
    this.setData({ audioOpen: false })
  },
  /** 强制设置 scroll-view 的 scroll-top（同值时需先 bump 再设回） */
  applyBodyScrollTop(target: number, after?: () => void) {
    const safeTarget = Math.max(0, target)
    const bump = this.data.bodyScrollTop === safeTarget
      ? (safeTarget === 0 ? 0.01 : safeTarget - 0.01)
      : safeTarget
    this.setData({ bodyScrollTop: bump }, () => {
      if (bump !== safeTarget) {
        this.setData({ bodyScrollTop: safeTarget }, after)
      } else {
        after?.()
      }
    })
  },
  /** 详情 DOM 重建后恢复阅读进度（scrollHeight 就绪前会短间隔重试） */
  restoreContentScrollTop(target: number, attempt = 0) {
    const safeTarget = Math.max(0, target)
    if (safeTarget <= 0) {
      this.applyBodyScrollTop(0, () => this.bindDetailSelectionContext())
      return
    }
    const maxAttempts = 8
    wx.createSelectorQuery()
      .in(this)
      .select('#boxBodyScroll')
      .scrollOffset()
      .select('#boxBodyScroll')
      .boundingClientRect()
      .exec((res) => {
        const scroll = (res && res[0]) as { scrollHeight?: number } | undefined
        const rect = (res && res[1]) as { height?: number } | undefined
        const scrollHeight = Number(scroll?.scrollHeight) || 0
        const viewportH = Number(rect?.height) || 0
        const ready = scrollHeight >= safeTarget + Math.max(viewportH * 0.35, 64)
        if (ready || attempt >= maxAttempts) {
          this.applyBodyScrollTop(safeTarget, () => this.bindDetailSelectionContext())
          return
        }
        this._restoreContentScrollTimer = setTimeout(() => {
          this._restoreContentScrollTimer = null
          this.restoreContentScrollTop(safeTarget, attempt + 1)
        }, 40 + attempt * 24) as unknown as number
      })
  },
  onShareAppMessage() {
    const h = this.data.header as BoxHeader | null
    const id = this.data.boxId
    const title = h?.box?.title || '史略详情'
    const path = id ? `/package-graph/pages/box-detail/index?boxId=${encodeURIComponent(id)}` : '/package-graph/pages/box-detail/index'
    return { title, path }
  },
  /** 底部「分享」：与选文分享同一套海报 UI，默认用详情第一段 */
  async onShareTap() {
    const paragraphs = this.data.detailParagraphs as DetailParagraph[]
    const firstPara = String(paragraphs?.[0]?.plain || '').trim()
    const blurb = String((this.data.header as BoxHeader | null)?.box?.blurb || '').trim()
    const quote = firstPara || blurb
    if (!quote) {
      wx.showToast({ title: '暂无可分享内容', icon: 'none' })
      return
    }
    await this.openSharePoster(quote)
  },
  /** 打开摘录分享海报（选文 / 底栏共用） */
  async openSharePoster(quoteText: string) {
    const text = String(quoteText || '').trim()
    if (!text) return
    wx.showLoading({ title: '生成海报…', mask: true })
    try {
      const header = this.data.header as BoxHeader | null
      const box = header?.box
      const { civ, dynasty } = readBoxLocationNames(box)
      const title = box?.title || this.data.navTitle || '史略'
      const typeLabel = categoryLabel(box?.categoryKey || '') || '史略'
      const sourceLine1 = `/${[civ, dynasty, typeLabel, title].filter(Boolean).join('・')}`
      const posterState = await buildSharePosterSheetState(text, sourceLine1, '')
      this.setData(posterState)
    } catch {
      wx.hideLoading()
      wx.showToast({ title: '海报生成失败', icon: 'none' })
    }
  },
  async onLoad(query: Record<string, string | undefined>) {
    const boxId = query.boxId || query.id
    if (!boxId) return
    const provisionalTitle = decodeQueryValue(query.title || query.displayName)
    const sys = wx.getSystemInfoSync()
    const navH = Math.round(88 * (sys.windowWidth / 750))
    const tabTop = (sys.statusBarHeight || 20) + navH
    const tabBarPx = Math.round(72 * (sys.windowWidth / 750))
    const bodyTop = tabTop + tabBarPx
    const zoomBarPx = 0
    const graphCanvasH = Math.max(400, Math.floor((sys.windowHeight || 667) - bodyTop - zoomBarPx))

    this._tabBarPx = tabBarPx
    this.setData({
      boxId,
      navTitle: provisionalTitle || '史略详情',
      tabTop,
      bodyTop,
      graphCanvasH,
    })
    try {
      const res = await request<BoxHeader>(`/boxes/${encodePathSegment(boxId)}`, {
        auth: hasToken(),
        softAuth: true,
      })
      const header = res.data
      const y0 = yearLabel(header.box.startYear)
      const y1 = yearLabel(header.box.endYear)
      const timeRange = y0 && y1 ? y0 + ' — ' + y1 : (y0 || y1 || '')
      const { civ, dynasty } = readBoxLocationNames(header.box)
      const showRelationsTab = isPersonBoxCategory(header.box.categoryKey)
      const tab =
        !showRelationsTab && this.data.tab === 'relations' ? 'content' : this.data.tab
      this.setData({
        header,
        navTitle: header.box.title,
        detailMetaDisplay: buildDetailMetaFromBox(header.box),
        audioTimeRange: timeRange,
        audioCategoryPath: [civ, dynasty].filter(Boolean).join(' · '),
        blurbSegs: parseDisplaySegments(header.box.blurb || ''),
        showRelationsTab,
        tab,
        isReadComplete: !!header.isReadComplete,
      })
      await this.refreshFavState()
      await this.recordFootprint()
      await this.ensureTab('content')
      // 详情正文就绪后预取关系图，切换 Tab 时无需再等
      if (showRelationsTab) {
        this.loadRelationsGraph()
      }
    } catch (e: any) {
      wx.showToast({ title: e?.message || '加载失败', icon: 'none' })
    }
  },
  async recordFootprint() {
    if (!hasToken()) return
    const boxId = this.data.boxId
    try {
      await request(`/footprints/boxes/${encodePathSegment(boxId)}/view`, { method: 'POST', auth: true })
    } catch {
      // 静默失败
    }
  },
  async refreshFavState() {
    const boxId = this.data.boxId
    if (!hasToken()) {
      this.setData({ isFav: false })
      return
    }
    const favorited = await fetchFavoritedBoxIdSet()
    this.setData({ isFav: favorited.has(boxId) })
  },
  promptLockedTab(access: TabAccess | undefined) {
    const reason = access?.lockedReason || ''
    const action = access?.unlockAction?.type || ''
    if (reason === 'LOGIN_REQUIRED' || action === 'OPEN_LOGIN') {
      wx.showModal({
        title: '需要登录',
        content: '登录后可使用阅读点查看评述、见证与原文。',
        confirmText: '去登录',
        success: (r) => {
          if (r.confirm) navigateTo(ROUTES.login)
        },
      })
      return
    }
    if (
      reason === 'INSUFFICIENT_READS' ||
      reason === 'NEED_MEMBERSHIP_OR_READS' ||
      action === 'OPEN_INVITE_PAGE' ||
      action === 'OPEN_MEMBERSHIP_PAGE'
    ) {
      wx.showModal({
        title: '需要阅读点',
        content: '深度阅读需消耗阅读点。可邀请好友注册获取阅读点，或稍后再试。',
        confirmText: '去邀请',
        success: (r) => {
          if (r.confirm) wx.switchTab({ url: ROUTES.invite })
        },
      })
    }
  },

  /** 关系 Tab：独立拉取，避免 ensureTab 早退导致 Network 无 /graph 请求 */
  loadRelationsGraph() {
    if (!this.data.showRelationsTab) return
    if (!this.data.boxId) {
      this.setData({
        graphErr: '史略信息未就绪，请返回后重试',
        graphPhase: 'error',
        graphReady: true,
        graphLoading: false,
      })
      return
    }
    if (this.data.graphFetched && this.data.graphPhase === 'ready') return
    void this.fetchRelationsGraph()
  },

  async fetchRelationsGraph() {
    if ((this as any)._graphInflight) return (this as any)._graphInflight as Promise<void>

    const boxId = this.data.boxId
    const enc = encodePathSegment(boxId)
    this.setData({
      graphLoading: true,
      graphPhase: 'loading',
      graphErr: '',
      graphRenderHint: '',
    })
    console.info('[box-detail] GET /boxes/' + boxId + '/graph')

    const task = (async () => {
      try {
        const res = await request<{ centerNodeKey: string | null; nodes: any[]; edges: any[] }>(
          `/boxes/${enc}/graph`
        )
        const nodes = res.data.nodes || []
        const edges = res.data.edges || []
        const nodeCount = nodes.length
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
        })
        console.info('[box-detail] graph loaded nodes=', nodeCount)
      } catch (e: any) {
        console.warn('[box-detail] graph fetch failed', e?.message || e)
        this.setData({
          graphErr: e?.message || '加载失败',
          graph: { centerNodeKey: '', nodes: [], edges: [] },
          graphNodeCount: 0,
          graphPhase: 'error',
          graphReady: true,
          graphFetched: true,
          graphLoading: false,
        })
      }
    })()

    ;(this as any)._graphInflight = task.finally(() => {
      ;(this as any)._graphInflight = undefined
    })
    return task
  },

  async ensureTab(tab: 'content' | 'relations' | 'reviews' | 'relics') {
    const boxId = this.data.boxId
    const enc = encodePathSegment(boxId)
    if (tab === 'content') {
      if (this.data.detailFetched) return
      try {
        const res = await request<{
          detailMd: string
          originalRef: unknown
          detailMdFlash?: string | null
          detailMdPro?: string | null
        }>(`/boxes/${enc}/detail`)
        const md = res.data.detailMd || ''
        const parsed = splitDetailParagraphs(md)
        this.setData({
          detailMd: md,
          detailParagraphs: parsed,
          detailErr: '',
          detailReady: true,
          detailFetched: true,
        }, () => {
          this.bindDetailSelectionContext()
        })
        this._rawOriginalRef = res.data.originalRef ?? null
      } catch (e: any) {
        this.setData({
          detailErr: e?.message || '加载失败',
          detailMd: '',
          detailParagraphs: [],
          detailReady: true,
          detailFetched: true,
        })
      }
      return
    }
    if (tab === 'relations') {
      this.loadRelationsGraph()
      return
    }
    if (tab === 'reviews') {
      if (this.data.critFetched) return
      try {
        const res = await request<{ items: any[] }>(`/boxes/${enc}/critiques`)
        this.setData({
          critiques: mapCritiqueItems(res.data.items || []),
          critErr: '',
          critReady: true,
          critFetched: true,
        })
      } catch (e: any) {
        const msg = String(e?.message || '')
        let err = msg || '加载失败'
        if (msg === 'UNAUTHORIZED' || msg.includes('login required')) {
          err = '请先登录后查看评述'
        } else if (msg.includes('INSUFFICIENT_READS') || msg.includes('NEED_MEMBERSHIP_OR_READS')) {
          err = '阅读点不足，可前往「邀请」页邀请好友获取'
        }
        this.setData({
          critiques: [],
          critErr: err,
          critReady: true,
          critFetched: true,
        })
      }
      return
    }
    if (tab === 'relics') {
      if (this.data.relicFetched) return
      try {
        const res = await request<{ items: any[] }>(`/boxes/${enc}/relics`)
        const items = mapRelicItems(res.data.items || [])
        this.setData({ relics: items, relicErr: '', relicReady: true, relicFetched: true })
      } catch (e: any) {
        const msg = String(e?.message || '')
        let err = msg || '加载失败'
        if (msg === 'UNAUTHORIZED' || msg.includes('login required')) {
          err = '请先登录后查看见证'
        } else if (msg.includes('INSUFFICIENT_READS') || msg.includes('NEED_MEMBERSHIP_OR_READS')) {
          err = '阅读点不足，可前往「邀请」页邀请好友获取'
        }
        this.setData({
          relics: [],
          relicErr: err,
          relicReady: true,
          relicFetched: true,
        })
      }
    }
  },





  onShow() {
    if (
      this.data.tab === 'relations'
      && this.data.showRelationsTab
      && this.data.graphPhase !== 'ready'
      && this.data.graphPhase !== 'error'
    ) {
      this.loadRelationsGraph()
    }
  },

  onGraphRenderHint(e: WechatMiniprogram.CustomEvent) {
    const hint = String((e.detail as { hint?: string })?.hint || '').trim()
    this.setData({ graphRenderHint: hint })
  },

  setTab(e: WechatMiniprogram.BaseEvent) {
    const tab = (e.currentTarget as any).dataset.tab as 'content' | 'relations' | 'reviews' | 'relics'
    if (!tab) return
    if (tab === 'relations' && !this.data.showRelationsTab) return
    if (tab === this.data.tab) {
      if (tab === 'relations' && this.data.graphPhase !== 'ready') {
        this.loadRelationsGraph()
      }
      return
    }
    this.hideSelectionBar()

    const prevTab = this.data.tab
    // 离开详情 Tab：缓存当次阅读进度
    if (prevTab === 'content') {
      this._contentScrollTop = this._detailScrollTop || 0
      this._contentReadingProgress = this.data.readingProgress || 0
    }

    // 防止同一次点击冒泡到 onPageTap 后又被切成阅读全屏态
    this._ignoreTapFromBar = true
    this._suppressChromeHide = true
    if (this._suppressChromeHideTimer) {
      clearTimeout(this._suppressChromeHideTimer)
    }
    this._suppressChromeHideTimer = setTimeout(() => {
      this._suppressChromeHide = false
      this._suppressChromeHideTimer = null
    }, 280) as unknown as number

    if (this._restoreContentScrollTimer) {
      clearTimeout(this._restoreContentScrollTimer)
      this._restoreContentScrollTimer = null
    }

    const restoreContent = tab === 'content'
    const restoreTop = restoreContent ? Math.max(0, this._contentScrollTop || 0) : 0
    this._detailScrollTop = restoreTop

    // 切换 Tab 时始终显示顶部四 Tab（非详情阅读沉浸态）
    this.setData({
      tab,
      uiFocused: true,
      readingProgress: restoreContent ? this._contentReadingProgress || 0 : 0,
    }, () => {
      if (restoreContent) {
        this.applyBodyScrollTop(0)
        this._restoreContentScrollTimer = setTimeout(() => {
          this._restoreContentScrollTimer = null
          this.restoreContentScrollTop(restoreTop)
        }, 32) as unknown as number
      } else {
        this.applyBodyScrollTop(0)
      }
      if (tab === 'relations') {
        this.loadRelationsGraph()
      } else {
        void this.ensureTab(tab).then(() => {
          if (restoreContent) this.bindDetailSelectionContext()
        })
      }
    })
  },
  onCritiqueTap(e: WechatMiniprogram.BaseEvent) {
    const idx = Number((e.currentTarget as any).dataset.idx)
    const list = this.data.critiques as CritiqueVm[]
    const c = list[idx]
    if (!c) return
    const critiqueId = Number(c.id || 0)
    if (!(critiqueId > 0)) {
      wx.showToast({ title: '评述暂不可用', icon: 'none' })
      return
    }
    navigateTo(ROUTES.critiqueDetail, { critiqueId })
  },
  onRelicTap(e: WechatMiniprogram.BaseEvent) {
    const idx = Number((e.currentTarget as any).dataset.idx)
    const list = this.data.relics as RelicVm[]
    const r = list[idx]
    if (!r) return
    const relicId = Number(r.id || 0)
    if (!(relicId > 0)) {
      wx.showToast({ title: '见证暂不可用', icon: 'none' })
      return
    }
    navigateTo(ROUTES.relicDetail, { relicId })
  },
  async onPlayIntro() {
    const cur = getNarrationState()
    if (cur === 'playing' || cur === 'paused') {
      const audioTitle = this.data.detailMetaDisplay || this.data.navTitle || '史略解说'
      this.setData({ audioOpen: true, audioTitle })
      toggleNarrationPlayback()
      this.setData({ narrationState: getNarrationState() })
      return
    }
    if (cur === 'loading') {
      wx.showToast({
        title: this.data.audioOpen ? '正在加载音频…' : '正在准备朗读…',
        icon: 'none',
        duration: 1500,
      })
      return
    }

    if (!this.data.detailFetched) {
      await this.ensureTab('content')
    }
    const h = this.data.header as BoxHeader | null
    const script = buildBoxNarrationScript({
      title: h?.box?.title,
      meta: this.data.detailMetaDisplay,
      paragraphs: this.data.detailParagraphs.map((p: DetailParagraph) => p.plain),
      blurb: h?.box?.blurb,
    })
    if (!script.trim()) {
      wx.showToast({ title: '暂无正文可朗读', icon: 'none' })
      return
    }

    let loadingVisible = false
    let initialReady = false
    try {
      wx.showLoading({ title: '正在准备朗读', mask: true })
      loadingVisible = true
      const audioTitle = this.data.detailMetaDisplay || this.data.navTitle || '史略解说'
      this.setData({ audioOpen: true, audioTitle, audioProgress: 0, audioCurrentTime: '0:00', audioDuration: '0:00', audioActivePara: -1 })
      await startNarration(
        script,
        (s) => {
          if (s === 'playing' && loadingVisible) {
            wx.hideLoading()
            loadingVisible = false
            initialReady = true
          }
          // 拖进度到未缓存片：短暂提示，不关浮层
          if (s === 'loading' && initialReady && this.data.audioOpen) {
            wx.showToast({ title: '加载中…', icon: 'none', duration: 800 })
          }
          // seek 完成进入 playing/paused 后再允许 timeUpdate 写回进度
          if ((s === 'playing' || s === 'paused' || s === 'idle') && this._audioSeeking) {
            this._audioSeeking = false
          }
          // 仅在已经成功开播过之后，idle 才关闭浮层（避免启动失败/重启时闪退）
          if (s === 'idle' && initialReady) {
            this.setData({ audioOpen: false, audioProgress: 0 })
          }
          this.setData({ narrationState: s })
        },
        (p) => {
          // 拖动进度条时以手势为准，避免 timeUpdate 回跳
          if (this._audioSeeking) {
            this.setData({ audioDuration: p.duration })
            return
          }
          this.setData({
            audioProgress: p.progress,
            audioCurrentTime: p.current,
            audioDuration: p.duration,
          })
        }
      )
      // start 成功返回时若仍未 playing（极端情况），以当前引擎状态为准
      if (getNarrationState() === 'playing' || getNarrationState() === 'paused') {
        initialReady = true
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '朗读失败'
      wx.showToast({ title: msg.slice(0, 28), icon: 'none', duration: 2800 })
      // 启动失败保留浮层，便于用户重试；仅复位状态
      this.setData({ narrationState: 'idle' })
    } finally {
      if (loadingVisible) wx.hideLoading()
    }
  },
  toggleAudioOverlay() {
    const open = !this.data.audioOpen
    if (!open) {
      stopNarration()
      this.setData({ audioOpen: false, narrationState: 'idle', audioProgress: 0 })
      return
    }
    const audioTitle = this.data.detailMetaDisplay || this.data.navTitle || '史略解说'
    this.setData({ audioOpen: true, audioTitle })
    if (getNarrationState() === 'idle') void this.onPlayIntro()
  },
  toggleAudioPlayback() {
    const cur = getNarrationState()
    if (cur === 'loading') {
      wx.showToast({ title: '正在加载音频…', icon: 'none', duration: 1200 })
      return
    }
    toggleNarrationPlayback()
    this.setData({ narrationState: getNarrationState() })
  },

  onAudioSkipBack() {
    seekNarration(-15)
  },

  onAudioSkipFwd() {
    seekNarration(15)
  },

  _audioSeekStartX: 0,
  _audioSeeking: false,

  onAudioSeekStart() {
    this._audioSeekStartX = 0
    this._audioSeeking = true
  },

  _formatAudioMmSs(sec: number): string {
    if (!Number.isFinite(sec) || sec < 0) return '0:00'
    const m = Math.floor(sec / 60)
    const s = Math.floor(sec % 60)
    return `${m}:${s < 10 ? '0' : ''}${s}`
  },

  _parseAudioMmSs(text: string): number {
    const m = String(text || '0:00').match(/^(\d+):(\d{1,2})$/)
    if (!m) return 0
    return Number(m[1]) * 60 + Number(m[2])
  },

  onAudioSeekMove(e: WechatMiniprogram.TouchEvent) {
    const touch = e.touches?.[0]
    if (!touch) return
    const query = wx.createSelectorQuery().in(this)
    query.select('.box-audio-scrub-track').boundingClientRect((rect) => {
      if (!rect || rect.width <= 0) return
      const x = touch.clientX - rect.left
      const ratio = Math.max(0, Math.min(1, x / rect.width))
      const pct = Math.round(ratio * 100)
      const totalSec = this._parseAudioMmSs(this.data.audioDuration)
      const curSec = totalSec > 0 ? (pct / 100) * totalSec : 0
      this.setData({
        audioProgress: pct,
        audioCurrentTime: this._formatAudioMmSs(curSec),
      })
    }).exec()
  },

  onAudioSeekEnd(e: WechatMiniprogram.TouchEvent) {
    const touch = e.changedTouches?.[0]
    if (!touch) {
      // 保持 _audioSeeking，等 playing 回调再清，避免旧 timeUpdate 回跳
      setTimeout(() => {
        if (this._audioSeeking && getNarrationState() !== 'loading') this._audioSeeking = false
      }, 600)
      return
    }
    const query = wx.createSelectorQuery().in(this)
    query.select('.box-audio-scrub-track').boundingClientRect((rect) => {
      if (!rect || rect.width <= 0) {
        this._audioSeeking = false
        return
      }
      const x = touch.clientX - rect.left
      const ratio = Math.max(0, Math.min(1, x / rect.width))
      const pct = Math.round(ratio * 100)
      this.setData({ audioProgress: pct })
      // 松手后仍短暂锁进度，待引擎 seek 完成（state→playing）再解锁
      seekNarrationPct(pct)
      setTimeout(() => {
        if (this._audioSeeking && getNarrationState() !== 'loading') this._audioSeeking = false
      }, 1200)
    }).exec()
  },

  onSpeedToggle() {
    const speeds = [0.75, 1, 1.25, 1.5, 2]
    const cur = this.data.audioSpeed
    let idx = speeds.indexOf(cur)
    if (idx === -1 || idx === speeds.length - 1) idx = 0
    else idx += 1
    const next = speeds[idx]
    setPlaybackRate(next)
    this.setData({ audioSpeed: next, audioSpeedLabel: next + 'x' })
    wx.showToast({ title: '倍速 ' + next + 'x', icon: 'none', duration: 1200 })
  },
  formatGraphScaleLabel(scale: number) {
    return `${Math.round((scale || 1) * 100)}%`
  },
  refreshGraphScaleLabel() {
    const c = this.selectComponent('#bdRelationGraph') as { getZoomScale?: () => number } | null
    const scale = c?.getZoomScale?.() ?? 1
    this.setData({ graphScaleLabel: this.formatGraphScaleLabel(scale) })
  },
  /** 解析原文引用（同 pages/original-text） */
  _parseOriginalRef(ref: unknown): { title: string; sourceWork: string; items: any[]; fallback: string } | null {
    if (ref == null || (Array.isArray(ref) && ref.length === 0) || (typeof ref === 'object' && Object.keys(ref as object).length === 0)) return null
    if (typeof ref === 'string') {
      const t = ref.trim()
      return t ? { title: '母本原文', sourceWork: '', items: [], fallback: t } : null
    }
    if (typeof ref !== 'object' || ref === null) return null
    const o = ref as Record<string, unknown>
    const title = typeof o.title === 'string' && o.title.trim() ? o.title.trim() : '母本原文'
    const sourceWork =
      (typeof o.sourceWork === 'string' ? o.sourceWork.trim() : '') ||
      (typeof o.primarySource === 'string' ? o.primarySource.trim() : '')

    const textField =
      (typeof o.text === 'string' ? o.text.trim() : '') ||
      (typeof o.originalText === 'string' ? o.originalText.trim() : '')
    if (textField) {
      return { title, sourceWork, items: [], fallback: textField }
    }

    // 索引侧 paragraphs: [{ text }] 或 string[]
    if (Array.isArray(o.paragraphs)) {
      const parts: string[] = []
      for (const p of o.paragraphs) {
        if (typeof p === 'string' && p.trim()) parts.push(p.trim())
        else if (p && typeof p === 'object') {
          const t = String((p as Record<string, unknown>).text ?? '').trim()
          if (t) parts.push(t)
        }
      }
      if (parts.length) return { title, sourceWork, items: [], fallback: parts.join('\n') }
    }

    const rawItems = o.items
    const items: any[] = []
    if (Array.isArray(rawItems)) {
      for (const it of rawItems) {
        if (!it || typeof it !== 'object') continue
        const x = it as Record<string, unknown>
        items.push({
          work: String(x.work ?? '').trim(),
          chapter: String(x.chapter ?? '').trim(),
          excerpt: String(x.excerpt ?? '').trim().replace(/\\r\\n/g, '\n').replace(/\\n/g, '\n'),
          url: String(x.url ?? '').trim(),
        })
      }
    }
    const hasStructured = items.some((i: any) => i.work || i.chapter || i.excerpt || i.url)
    // 无法识别的结构：不向用户展示 JSON 字符串
    if (!hasStructured) return null
    return { title, sourceWork, items, fallback: '' }
  },

  goOriginal() {
    // 优先使用之前缓存的数据
    const ref = this._rawOriginalRef
    if (ref != null) {
      const parsed = this._parseOriginalRef(ref)
      if (parsed && (parsed.items.length > 0 || parsed.fallback.length > 0)) {
        this.setData({
          showOriginal: true,
          originalTitle: parsed.title,
          originalSourceWork: parsed.sourceWork,
          originalItems: parsed.items,
          originalFallback: parsed.fallback,
          originalEmpty: false,
          originalLoading: false,
        })
        return
      }
    }

    // 无缓存，重新请求
    this.setData({ showOriginal: true, originalLoading: true, originalEmpty: true })
    const run = async () => {
      try {
        const enc = encodePathSegment(this.data.boxId)
        const res = await request<{ originalRef: unknown }>(`/boxes/${enc}/original-ref`, { auth: hasToken(), softAuth: true })
        const parsed = this._parseOriginalRef(res.data.originalRef)
        if (!parsed || (!parsed.items.length && !parsed.fallback.length)) {
          this.setData({
            originalLoading: false,
            originalEmpty: true,
            originalTitle: '',
            originalSourceWork: '',
            originalItems: [],
            originalFallback: '',
          })
          return
        }
        this.setData({
          originalLoading: false,
          originalEmpty: false,
          originalTitle: parsed.title,
          originalSourceWork: parsed.sourceWork,
          originalItems: parsed.items,
          originalFallback: parsed.fallback,
        })
      } catch {
        this.setData({ originalLoading: false, originalEmpty: true })
        wx.showToast({ title: '原文暂时无法加载，请稍后重试', icon: 'none' })
      }
    }
    void run()
  },

  closeOriginal() {
    this.setData({ showOriginal: false })
  },

  copyOriginalLink(e: WechatMiniprogram.TouchEvent) {
    const url = e.currentTarget?.dataset?.url
    if (url) {
      wx.setClipboardData({ data: url })
      wx.showToast({ title: '链接已复制', icon: 'success' })
    }
  },
  onGraphNodeTap(_e: WechatMiniprogram.CustomEvent<{ key?: string; targetBoxId?: string; nodeType?: string }>) {
    // 关系图谱暂不支持点击跳转
  },
  noop() {},
  /** 标记本次tap来自底部操作栏，阻止导航栏切换 */
  markTapFromBar() { this._ignoreTapFromBar = true; },
  onGraphZoomIn() {
    const c = this.selectComponent('#bdRelationGraph') as {
      zoomIn?: () => void
      getZoomScale?: () => number
      paintCached?: () => void
    } | null
    c?.zoomIn?.()
    const label = this.formatGraphScaleLabel(c?.getZoomScale?.() ?? 1)
    if (label !== this.data.graphScaleLabel) {
      this.setData({ graphScaleLabel: label }, () => c?.paintCached?.())
    }
  },
  onGraphZoomOut() {
    const c = this.selectComponent('#bdRelationGraph') as {
      zoomOut?: () => void
      getZoomScale?: () => number
      paintCached?: () => void
    } | null
    c?.zoomOut?.()
    const label = this.formatGraphScaleLabel(c?.getZoomScale?.() ?? 1)
    if (label !== this.data.graphScaleLabel) {
      this.setData({ graphScaleLabel: label }, () => c?.paintCached?.())
    }
  },
  onGraphZoomReset() {
    const c = this.selectComponent('#bdRelationGraph') as {
      resetZoom?: () => void
      paintCached?: () => void
    } | null
    c?.resetZoom?.()
    if (this.data.graphScaleLabel !== '100%') {
      this.setData({ graphScaleLabel: '100%' }, () => c?.paintCached?.())
    }
  },
  onGraphZoomChange(e: WechatMiniprogram.CustomEvent<{ scale?: number }>) {
    // 双指缩放：松手后由组件触发；过程中不 setData
    const scale = e.detail?.scale
    if (scale == null) return
    const c = this.selectComponent('#bdRelationGraph') as { paintCached?: () => void } | null
    const label = this.formatGraphScaleLabel(scale)
    if (label === this.data.graphScaleLabel) return
    this.setData({ graphScaleLabel: label }, () => c?.paintCached?.())
  },
  onDetailScroll(e: WechatMiniprogram.ScrollViewScroll) {
    const d = e.detail || { scrollTop: 0, scrollHeight: 0 }
    const scrollTop = d.scrollTop || 0
    const scrollHeight = d.scrollHeight || 0
    const sysInfo = wx.getSystemInfoSync()
    const bodyTop = this.data.bodyTop
    const viewportH = sysInfo.windowHeight - bodyTop
    const maxScroll = Math.max(scrollHeight - viewportH, 1)
    const pct = Math.min(Math.round((scrollTop / maxScroll) * 100), 100)
    this.setData({ readingProgress: pct })

    // 自动隐藏 tab 栏（仅详情 Tab），使用 CSS transition 实现无抖动显隐
    if (this.data.tab === 'content' && !this._suppressChromeHide) {
      const prevScrollTop = this._detailScrollTop ?? 0
      const delta = scrollTop - prevScrollTop
      this._detailScrollTop = scrollTop

      if (scrollTop <= 5) {
        // 顶部自动显示
        if (!this.data.uiFocused) this.setData({ uiFocused: true })
      } else if (delta > 5) {
        // 下划 > 5px 隐藏
        if (this.data.uiFocused) this.setData({ uiFocused: false })
      } else if (delta < -5) {
        // 上划 > 5px 显示
        if (!this.data.uiFocused) this.setData({ uiFocused: true })
      }
    } else if (this.data.tab === 'content') {
      this._detailScrollTop = scrollTop
    }
  },

  /** 切换 tab 栏显隐（悬浮 overlay，不影响正文布局，无跳变） */
  onToggleUI(focused: boolean) {
    if (this.data.tab !== 'content') return
    this.setData({ uiFocused: focused })
  },



  /** 点击屏幕切换导航栏显隐 */
  onPageTap() {
    if (this.data.showOriginal) return
    if (this.data.selectionBarVisible) {
      this.hideSelectionBar()
      return
    }
    if (this.data.tab === 'content' && !this._ignoreTapFromBar) {
      this.onToggleUI(!this.data.uiFocused)
    }
    this._ignoreTapFromBar = false
  },
  toggleFav() {
    if (!hasToken()) {
      promptLoginForFavorite()
      return
    }
    const boxId = this.data.boxId
    const next = !this.data.isFav
    const run = async () => {
      try {
        if (next) {
          await favoriteBox(boxId)
          wx.showToast({ title: '已收藏', icon: 'success' })
        } else {
          await unfavoriteBox(boxId)
          wx.showToast({ title: '已取消收藏', icon: 'success' })
        }
        await this.refreshFavState()
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : '操作失败'
        wx.showToast({ title: msg, icon: 'none' })
      }
    }
    void run()
  },
  toggleReadComplete() {
    if (!hasToken()) {
      promptLoginForReadComplete()
      return
    }
    const boxId = this.data.boxId
    const next = !this.data.isReadComplete
    const run = async () => {
      try {
        if (next) {
          await markBoxReadComplete(boxId)
          wx.showToast({ title: '已标记读完', icon: 'success' })
        } else {
          await unmarkBoxReadComplete(boxId)
          wx.showToast({ title: '已取消标记', icon: 'none' })
        }
        this.setData({ isReadComplete: next })
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : '操作失败'
        wx.showToast({ title: msg, icon: 'none' })
      }
    }
    void run()
  },
  hideSelectionBar() {
    this.setData({
      selectionBarVisible: false,
      selectionBarText: '',
    })
    this.clearDetailSelection()
  },
  onDetailSelectionChange(e: WechatMiniprogram.CustomEvent) {
    if (this.data.tab !== 'content') return
    const detail = (e.detail || {}) as {
      isCollapsed?: boolean
      selectedString?: string
      firstRangeRect?: { left?: number; top?: number; width?: number; height?: number }
    }
    const selected = String(detail.selectedString || '').trim()
    if (detail.isCollapsed || !selected) {
      this.hideSelectionBar()
      return
    }
    const anchor = resolveSelectionBarAnchor(detail.firstRangeRect, {
      left: this.data.selectionBarLeft,
      top: this.data.selectionBarTop,
      placement: this.data.selectionBarPlacement,
    })
    this.setData({
      selectionBarVisible: true,
      selectionBarText: selected,
      selectionBarLeft: anchor.left,
      selectionBarTop: anchor.top,
      selectionBarPlacement: anchor.placement,
    })
  },
  async onSelectionShare() {
    const text = this.data.selectionBarText
    this.hideSelectionBar()
    if (!text) return
    await this.openSharePoster(text)
  },
  closeSharePoster() {
    wx.hideLoading()
    this.setData({ sharePosterVisible: false })
  },
  onSelectionCopy() {
    const text = this.data.selectionBarText
    this.hideSelectionBar()
    if (!text) return
    wx.setClipboardData({
      data: text,
      success: () => wx.showToast({ title: '已复制', icon: 'success' }),
    })
  },
  onSelectionQuery() {
    const text = this.data.selectionBarText
    this.hideSelectionBar()
    if (!text) return
    this.clearDetailSelection()
    this.setData({
      dictionaryVisible: true,
      dictionaryQuery: text,
    })
  },
  closeDictionary() {
    this.setData({ dictionaryVisible: false, dictionaryQuery: '' })
    this.clearDetailSelection()
  },
  onSelectionCorrection() {
    const text = this.data.selectionBarText
    this.hideSelectionBar()
    if (!text) return
    this.openCorrectionModal(text)
  },
  openCorrectionModal(selectedText: string) {
    this.clearDetailSelection()
    requireLoginForCorrection(() => {
      const header = this.data.header as BoxHeader | null
      const box = header?.box
      const { civ, dynasty } = readBoxLocationNames(box)
      this.setData({
        correctionVisible: true,
        correctionSubmitting: false,
        correctionBoxTitle: box?.title || this.data.navTitle,
        correctionCivilizationName: civ,
        correctionDynastyName: dynasty,
        correctionSelectedText: selectedText,
      })
    })
  },
  closeCorrection() {
    this.setData({ correctionVisible: false, correctionSubmitting: false })
    this.clearDetailSelection()
  },
  async onCorrectionSubmit(e: WechatMiniprogram.CustomEvent) {
    const reason = String((e.detail as { reason?: string })?.reason || '')
    const boxId = this.data.boxId
    if (!boxId || this.data.correctionSubmitting) return
    this.setData({ correctionSubmitting: true })
    try {
      await submitCorrection({
        boxId,
        sourceType: 'box_detail_selection',
        reason,
        selectedText: this.data.correctionSelectedText,
      })
      wx.showToast({ title: '提交成功，感谢反馈', icon: 'success' })
      this.setData({ correctionVisible: false, correctionSubmitting: false })
    } catch (err: unknown) {
      this.setData({ correctionSubmitting: false })
      const msg = err instanceof Error ? err.message : '提交失败，请稍后重试'
      wx.showToast({ title: msg, icon: 'none' })
    }
  },
})
