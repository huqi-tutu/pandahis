import { hasToken, request } from '../../native-utils/api'
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
} from '../../native-utils/box-narration'
import { encodePathSegment } from '../../native-utils/encode-path-segment'
import { decodeQueryValue } from '../../native-utils/query-value'
import {
  favoriteBox,
  fetchFavoritedBoxIdSet,
  promptLoginForFavorite,
  unfavoriteBox,
} from '../../native-utils/favorite-box'
import { formatHistoryYear } from '../../native-utils/year-format'
import { ROUTES, navigateTo } from '../../native-utils/router'
import { buildSharePosterSheetState } from '../../native-utils/share-poster-open'
import {
  requireLoginForCorrection,
  submitCorrection,
} from '../../native-utils/correction'
import { categoryLabel, isPersonBoxCategory } from '../../native-utils/category-label'
import { resolveSelectionBarAnchor } from '../../native-utils/selection-bar-position'

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
  tabSummary: { hasGraph: boolean; hasCritiques: boolean; hasRelics: boolean; hasOriginal: boolean }
  access: {
    boxLocked: boolean
    tabs: { graph: TabAccess; critique: TabAccess; relic: TabAccess; original: TabAccess }
  }
}

type CritiqueVm = {
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
  name: string
  imageUrl?: string | null
  summary?: string | null
  description?: string | null
  museum: string
  priorityCode?: string | null
  thumbLabel: string
  teaser: string
  location: string
}

function relicThumbLabel(name: string): string {
  const n = (name || '').trim()
  if (!n) return '—'
  if (n.length <= 4) return n
  return n.slice(-4)
}

function mapCritiqueItems(raw: any[]): CritiqueVm[] {
  return (raw || []).map((it, idx) => {
    const author = String(it.author || '').trim()
    const title = String(it.title || '').trim()
    const displayAuthor = author || title || '佚名'
    const era = String(it.eraText || '').trim()
    const yv = it.year
    const y = yv != null && yv !== '' ? Number(yv) : NaN
    const yearStr = Number.isFinite(y) && y !== 0 ? String(y) : ''
    const eraMeta = [era, yearStr].filter(Boolean).join(' · ')
    const content = String(it.content || '').trim()
    const blurb = String(it.blurb || '').trim()
    const bodyQuote = content || blurb
    const source = String(it.source || it.book || '').trim()
    const cardTitle = title || displayAuthor
    const cardMeta = [author, eraMeta, source].filter(Boolean).join(' · ')
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
    }
  })
}

function mapRelicItems(raw: any[]): RelicVm[] {
  return (raw || []).map((it) => {
    const full = String(it.description || it.summary || '').trim()
    // 列表简介：优先用服务端 summary；勿把截断摘要拼进详情全文
    const teaser = String(it.summary || it.description || '').trim()
    const museum = it.museum || '馆藏待补充'
    return {
      name: it.name || '',
      imageUrl: it.imageUrl,
      summary: teaser,
      description: full,
      museum,
      priorityCode: it.priorityCode,
      thumbLabel: relicThumbLabel(it.name || ''),
      teaser,
      location: museum,
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

function buildDetailMetaFromBox(box: BoxHeader['box']): string {
  const fromSub = formatDetailMetaLine(box.subText)
  if (fromSub) return fromSub
  const parts: string[] = []
  const y0 = yearLabel(box.startYear)
  const y1 = yearLabel(box.endYear)
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
  const parts = raw.split(/\n{2,}/).map((s) => s.trim()).filter(Boolean)
  const list = parts.length ? parts : [raw]
  return list.map((p) => {
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
    critColors: ['#92ADA4', '#C9825A', '#7BA87B', '#B85A5A', '#84572F', '#5A8FA8'],
    tab: 'content' as 'content' | 'relations' | 'reviews' | 'relics',
    showRelationsTab: false,
    isFav: false,
    detailMd: '',
    detailParagraphs: [] as DetailParagraph[],
    detailMetaDisplay: '',
    detailReady: false,
    detailErr: '',
    graph: { centerNodeKey: '', nodes: [] as any[], edges: [] as any[] },
    graphReady: false,
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
  _detailScrollTop: 0,
  _tabBarPx: 0,
  _suppressChromeHide: false,
  _suppressChromeHideTimer: null as ReturnType<typeof setTimeout> | null,
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
    stopNarration()
    this.setData({ audioOpen: false })
  },
  onShareAppMessage() {
    const h = this.data.header as BoxHeader | null
    const id = this.data.boxId
    const title = h?.box?.title || '史略详情'
    const path = id ? `/pages/box-detail/index?boxId=${encodeURIComponent(id)}` : '/pages/box-detail/index'
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
    const zoomBarPx = Math.round(130 * (sys.windowWidth / 750))
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
      const res = await request<BoxHeader>(`/boxes/${encodePathSegment(boxId)}`)
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
      })
      await this.refreshFavState()
      await this.recordFootprint()
      await this.ensureTab('content')
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
        content: '登录后可开通会员或使用阅读点查看评述、见证与原文。',
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
        title: '需要会员或阅读点',
        content: '开通会员可免扣点阅读评述、见证与原文；也可邀友助力免费领季卡，或在设置中查看阅读点。',
        confirmText: '去开通',
        success: (r) => {
          if (r.confirm) wx.switchTab({ url: ROUTES.membership })
        },
      })
    }
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
      if (!this.data.showRelationsTab) return
      if (this.data.graphFetched) return
      try {
        const res = await request<{ centerNodeKey: string | null; nodes: any[]; edges: any[] }>(`/boxes/${enc}/graph`)
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
        })
      } catch (e: any) {
        this.setData({
          graphErr: e?.message || '加载失败',
          graph: { centerNodeKey: '', nodes: [], edges: [] },
          graphReady: true,
          graphFetched: true,
        })
      }
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
          err = '需要会员或阅读点，请前往「会员」页开通或邀友助力'
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
          err = '需要会员或阅读点，请前往「会员」页开通或邀友助力'
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





  setTab(e: WechatMiniprogram.BaseEvent) {
    const tab = (e.currentTarget as any).dataset.tab as 'content' | 'relations' | 'reviews' | 'relics'
    if (tab === 'relations' && !this.data.showRelationsTab) return
    if (tab === this.data.tab) return
    this.hideSelectionBar()

    const nextScrollTop = this.data.bodyScrollTop === 0 ? 0.01 : 0

    // 防止同一次点击冒泡到 onPageTap 后又被切成阅读全屏态
    this._ignoreTapFromBar = true
    this._detailScrollTop = 0
    this._suppressChromeHide = true
    if (this._suppressChromeHideTimer) {
      clearTimeout(this._suppressChromeHideTimer)
    }
    this._suppressChromeHideTimer = setTimeout(() => {
      this._suppressChromeHide = false
      this._suppressChromeHideTimer = null
    }, 280) as unknown as number

    // 切换 Tab 时始终显示顶部四 Tab（非详情阅读沉浸态）
    this.setData({
      tab,
      uiFocused: true,
      readingProgress: 0,
      bodyScrollTop: nextScrollTop,
    }, () => {
      if (nextScrollTop !== 0) {
        this.setData({ bodyScrollTop: 0 })
      }
    })
    void this.ensureTab(tab)
  },
  onCritiqueTap(e: WechatMiniprogram.BaseEvent) {
    const idx = Number((e.currentTarget as any).dataset.idx)
    const list = this.data.critiques as CritiqueVm[]
    const c = list[idx]
    if (!c) return
    const body = String(c.content || c.bodyQuote || '').trim()
    navigateTo(ROUTES.critiqueDetail, {
      title: c.title || '',
      author: c.displayAuthor || '',
      book: c.source || '',
      era: c.eraMeta || '',
      body,
    })
  },
  onRelicTap(e: WechatMiniprogram.BaseEvent) {
    const idx = Number((e.currentTarget as any).dataset.idx)
    const list = this.data.relics as RelicVm[]
    const r = list[idx]
    if (!r) return
    navigateTo(ROUTES.relicDetail, {
      name: r.name || '',
      museum: r.museum || '',
      // 只用完整介绍；summary 入库时会截断并加「…」，拼进去会像「没写完」
      detail: String(r.description || r.teaser || '').trim(),
      imageUrl: r.imageUrl || '',
    })
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
      wx.showToast({ title: '正在准备朗读…', icon: 'none', duration: 1500 })
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
          }
          if (s === 'idle') {
            this.setData({ audioOpen: false, audioProgress: 0 })
          }
          this.setData({ narrationState: s })
        },
        (p) => {
          this.setData({
            audioProgress: p.progress,
            audioCurrentTime: p.current,
            audioDuration: p.duration,
          })
        }
      )
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '朗读失败'
      wx.showToast({ title: msg.slice(0, 28), icon: 'none', duration: 2800 })
      this.setData({ narrationState: 'idle', audioOpen: false })
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

  onAudioSeekStart() {
    this._audioSeekStartX = 0
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
      this.setData({ audioProgress: pct })
    }).exec()
  },

  onAudioSeekEnd(e: WechatMiniprogram.TouchEvent) {
    const touch = e.changedTouches?.[0]
    if (!touch) return
    const query = wx.createSelectorQuery().in(this)
    query.select('.box-audio-scrub-track').boundingClientRect((rect) => {
      if (!rect || rect.width <= 0) return
      const x = touch.clientX - rect.left
      const ratio = Math.max(0, Math.min(1, x / rect.width))
      const pct = Math.round(ratio * 100)
      seekNarrationPct(pct)
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
    const h = this.data.header as BoxHeader | null
    const o = h?.access?.tabs?.original
    if (o?.locked) { this.promptLockedTab(o); return }

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
        const res = await request<{ originalRef: unknown }>(`/boxes/${enc}/original-ref`, { auth: hasToken() })
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
      } catch (e: any) {
        const msg = String(e?.message || '')
        if (msg.includes('INSUFFICIENT_READS') || msg.includes('NEED_MEMBERSHIP_OR_READS')) {
          this.setData({ showOriginal: false })
          wx.showModal({
            title: '需要会员或阅读点',
            content: '开通会员可免扣点阅读；也可去会员页邀友助力或查看阅读点。',
            confirmText: '去开通',
            success: (r) => { if (r.confirm) wx.switchTab({ url: ROUTES.membership }) },
          })
        } else {
          this.setData({ originalLoading: false, originalEmpty: true })
          wx.showToast({ title: '加载失败', icon: 'none' })
        }
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
