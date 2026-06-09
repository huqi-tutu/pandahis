import { hasToken, request } from '../../native-utils/api'
import { encodePathSegment } from '../../native-utils/encode-path-segment'
import {
  favoriteBox,
  fetchFavoritedBoxIdSet,
  promptLoginForFavorite,
  unfavoriteBox,
} from '../../native-utils/favorite-box'
import { ROUTES, navigateTo } from '../../native-utils/router'
import {
  buildBoxNarrationScript,
  getNarrationState,
  startNarration,
  stopNarration,
  toggleNarrationPlayback,
  type NarrationState,
} from '../../native-utils/box-narration'
import { promptContentShareUnavailable } from '../../native-utils/share-invite'

type TabAccess = { locked?: boolean; lockedReason?: string | null; unlockAction?: { type?: string } | null }

type BoxHeader = {
  box: {
    id: string
    title: string
    subText: string
    blurb?: string | null
    categoryKey: string
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

type RelicVm = {
  name: string
  imageUrl?: string | null
  summary?: string | null
  description?: string | null
  museum: string
  priorityCode?: string | null
  thumbLabel: string
  teaser: string
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
  _k: number
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
    return {
      ...it,
      displayAuthor,
      eraMeta,
      bodyQuote,
      avatarLetter: displayAuthor.charAt(0) || '评',
      _k: idx,
    }
  })
}

function mapRelicItems(raw: any[]): RelicVm[] {
  return (raw || []).slice(0, 3).map((it) => ({
    name: it.name || '',
    imageUrl: it.imageUrl,
    summary: it.summary,
    description: it.description,
    museum: it.museum || '馆藏待补充',
    priorityCode: it.priorityCode,
    thumbLabel: relicThumbLabel(it.name || ''),
    teaser: String(it.summary || it.description || '').trim(),
  }))
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
  return y < 0 ? `前${Math.abs(y)}` : String(y)
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

function splitDetailParagraphs(md: string): string[] {
  const raw = String(md || '').trim()
  if (!raw) return []
  const parts = raw.split(/\n{2,}/).map((s) => s.trim()).filter(Boolean)
  return parts.length ? parts : [raw]
}

Page({
  data: {
    boxId: '',
    navTitle: '史略盒子',
    header: null as BoxHeader | null,
    stickyTabsTopPx: 88,
    tab: 'content' as 'content' | 'relations' | 'reviews' | 'relics',
    isFav: false,
    detailMd: '',
    detailParagraphs: [] as string[],
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
    graphScaleLabel: '100%',
  },
  onUnload() {
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
  onShareTap() {
    promptContentShareUnavailable()
  },
  async onLoad(query: Record<string, string | undefined>) {
    const boxId = query.boxId || query.id
    if (!boxId) return
    const menu = wx.getMenuButtonBoundingClientRect()
    const sys = wx.getSystemInfoSync()
    const stickyTabsTopPx = Math.max(Math.ceil(menu.bottom), (sys.statusBarHeight || 0) + 44)
    this.setData({ boxId, stickyTabsTopPx })
    try {
      const res = await request<BoxHeader>(`/boxes/${encodePathSegment(boxId)}`)
      const header = res.data
      this.setData({
        header,
        navTitle: header.box.title,
        detailMetaDisplay: buildDetailMetaFromBox(header.box),
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
        this.setData({
          detailMd: md,
          detailParagraphs: splitDetailParagraphs(md),
          detailErr: '',
          detailReady: true,
          detailFetched: true,
        })
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
        const res = await request<{ items: any[] }>(`/boxes/${enc}/critiques`, { auth: hasToken() })
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
        const res = await request<{ items: any[] }>(`/boxes/${enc}/relics`, { auth: hasToken() })
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
    const h = this.data.header as BoxHeader | null
    if (tab === 'reviews' && h?.access?.tabs?.critique?.locked) {
      this.promptLockedTab(h.access.tabs.critique)
      return
    }
    if (tab === 'relics' && h?.access?.tabs?.relic?.locked) {
      this.promptLockedTab(h.access.tabs.relic)
      return
    }
    this.setData({ tab })
    void this.ensureTab(tab)
  },
  onCritiqueTap(e: WechatMiniprogram.BaseEvent) {
    const idx = Number((e.currentTarget as any).dataset.idx)
    const list = this.data.critiques as CritiqueVm[]
    const c = list[idx]
    if (!c) return
    const body = [c.content, c.blurb, c.bodyQuote, c.source].filter(Boolean).join('\n\n')
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
      detail: [r.teaser, r.description].filter(Boolean).join('\n\n'),
      imageUrl: r.imageUrl || '',
    })
  },
  async onPlayIntro() {
    const cur = getNarrationState()
    if (cur === 'playing' || cur === 'paused') {
      this.setData({ audioOpen: true })
      toggleNarrationPlayback()
      this.setData({ narrationState: getNarrationState() })
      return
    }
    if (cur === 'loading') {
      stopNarration()
      this.setData({ narrationState: 'idle', audioOpen: false })
      wx.hideLoading()
      return
    }

    if (!this.data.detailFetched) {
      await this.ensureTab('content')
    }
    const h = this.data.header as BoxHeader | null
    const script = buildBoxNarrationScript({
      title: h?.box?.title,
      meta: this.data.detailMetaDisplay,
      paragraphs: this.data.detailParagraphs,
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
      this.setData({ audioOpen: true, audioProgress: 0, audioCurrentTime: '0:00', audioDuration: '0:00' })
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
    this.setData({ audioOpen: true })
    if (getNarrationState() === 'idle') void this.onPlayIntro()
  },
  toggleAudioPlayback() {
    toggleNarrationPlayback()
    this.setData({ narrationState: getNarrationState() })
  },
  formatGraphScaleLabel(scale: number) {
    return `${Math.round((scale || 1) * 100)}%`
  },
  refreshGraphScaleLabel() {
    const c = this.selectComponent('#bdRelationGraph') as { getZoomScale?: () => number } | null
    const scale = c?.getZoomScale?.() ?? 1
    this.setData({ graphScaleLabel: this.formatGraphScaleLabel(scale) })
  },
  goOriginal() {
    const h = this.data.header as BoxHeader | null
    const o = h?.access?.tabs?.original
    if (o?.locked) {
      this.promptLockedTab(o)
      return
    }
    navigateTo(ROUTES.originalText, { boxId: this.data.boxId })
  },
  onGraphNodeTap(e: WechatMiniprogram.CustomEvent<{ key?: string; targetBoxId?: string }>) {
    const key = e.detail?.key
    const targetId = e.detail?.targetBoxId
    const boxId = this.data.boxId
    if (targetId && targetId !== boxId) {
      navigateTo(ROUTES.boxDetail, { boxId: targetId })
      return
    }
    if (key && boxId) {
      navigateTo(ROUTES.relationDetail, { boxId, nodeKey: key })
    }
  },
  noop() {},
  onGraphZoomIn() {
    const c = this.selectComponent('#bdRelationGraph') as { zoomIn?: () => void } | null
    c?.zoomIn?.()
    this.refreshGraphScaleLabel()
  },
  onGraphZoomOut() {
    const c = this.selectComponent('#bdRelationGraph') as { zoomOut?: () => void } | null
    c?.zoomOut?.()
    this.refreshGraphScaleLabel()
  },
  onGraphZoomReset() {
    const c = this.selectComponent('#bdRelationGraph') as { resetZoom?: () => void } | null
    c?.resetZoom?.()
    this.refreshGraphScaleLabel()
  },
  onGraphZoomChange(e: WechatMiniprogram.CustomEvent<{ scale?: number }>) {
    const scale = e.detail?.scale ?? 1
    this.setData({ graphScaleLabel: this.formatGraphScaleLabel(scale) })
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
})
