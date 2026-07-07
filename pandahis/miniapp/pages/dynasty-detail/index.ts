import { hasToken, request } from '../../native-utils/api'
import { encodePathSegment } from '../../native-utils/encode-path-segment'
import {
  computeUnitFavoriteState,
  fetchFavoritedBoxIdSet,
  promptLoginForFavorite,
  setBoxesFavorited,
} from '../../native-utils/favorite-box'
import { ROUTES, navigateTo } from '../../native-utils/router'
import { promptContentShareUnavailable } from '../../native-utils/share-invite'

function collectMatrixBoxIds(swim: { lanes?: { collapsedRows?: { boxId?: string }[][] }[] } | null) {
  const ids: string[] = []
  for (const lane of swim?.lanes || []) {
    for (const row of lane.collapsedRows || []) {
      for (const bar of row) {
        if (bar?.boxId) ids.push(bar.boxId)
      }
    }
  }
  return ids
}

type UnitHero = {
  unit: {
    id: string
    name: string
    rulerName?: string | null
    dynastyName?: string
    crumbText: string
    eraText: string
    startYear: number
    endYear: number
    durationYears: number
    summary: string
  }
  relatedUnits?: { unitId: string; title: string; startYear: number }[]
  nextUnit?: { unitId: string; title: string; startYear: number } | null
}

type SwimBar = {
  title: string
  boxId: string
  left: string
  width: string
  unitLeft: string
  unitWidth: string
  chipLeft: string
  chipWidth: string
  lineLeftW: string
  lineRightL: string
  lineRightW: string
  priority: string
  type: string
  timeRange?: string
  zIndex?: number
}

type SwimLane = {
  label: string
  borderColor: string
  layout: string
  collapsedRows: SwimBar[][]
  hasMore: boolean
  moreCount: number
  extraBars?: SwimBar[]
}

type SwimMatrix = {
  startYear: number
  endYear: number
  endLabel: string
  ticks: { label: string; left: string; edgeStart?: boolean; hideLabel?: boolean }[]
  lanes: SwimLane[]
  concurrentItems: string[]
  sheetWidthRpx: number
}

function splitIntroParagraphs(intro: string): string[] {
  const text = (intro || '').trim() || '空'
  return text.split(/\n\n+/).map((p) => p.trim()).filter(Boolean)
}

/* ── 生成20年间隔时间轴刻度 ── */
function generateTimelineTicks(startYear: number, endYear: number, originalSheetWidthRpx: number) {
  const span = endYear - startYear
  const newSheetWidthRpx = Math.round(originalSheetWidthRpx * (50 / 20))
  const ticks: { label: string; left: string; edgeStart?: boolean; hideLabel?: boolean }[] = []

  // 起始年
  ticks.push({ label: String(startYear), left: '0%', edgeStart: true, hideLabel: false })

  // 首个10的倍数的刻度（>= startYear + 1 的10倍数）
  const firstTick = Math.ceil((startYear + 1) / 10) * 10
  let tickYear = firstTick
  while (tickYear < endYear) {
    const left = ((tickYear - startYear) / span) * 100
    const distToStart = tickYear - startYear
    const distToEnd = endYear - tickYear
    const isPenultimate = tickYear + 20 >= endYear
    // 第2个刻度距起点<20年 → 只画线不标数字
    // 倒数第2个距终点<20年 → 只画线不标数字
    const hideLabel = (tickYear === firstTick && distToStart < 20) || (isPenultimate && distToEnd < 20)
    ticks.push({ label: String(tickYear), left: `${left}%`, hideLabel })
    tickYear += 20
  }

  // 泳道网格线：从第2个刻度开始，与时间轴刻度对齐
  const gridLines = ticks.filter(t => t.left !== '0%').map(t => ({ left: t.left }))

  return { ticks, endLabel: String(endYear), sheetWidthRpx: newSheetWidthRpx, gridLines }
}

function previewIntro(intro: string): { preview: string; canExpand: boolean; paragraphs: string[] } {
  const paragraphs = splitIntroParagraphs(intro)
  if (paragraphs.length <= 1) {
    return { preview: paragraphs[0] || '空', canExpand: false, paragraphs }
  }
  return { preview: paragraphs[0], canExpand: true, paragraphs }
}

Page({
  swimScrollLeft: 0,
  _echoMatrix: false,
  _echoAxis: false,
  data: {
    unit: null as UnitHero['unit'] | null,
    dynastyTitle: '',
    navTitle: '',
    heroSubLine: '',
    swim: null as SwimMatrix | null,
    concurrentItems: [] as string[],
    relatedUnits: [] as NonNullable<UnitHero['relatedUnits']>,
    nextUnit: null as UnitHero['nextUnit'] | null,
    introPreview: '',
    introDisplay: '',
    introCanExpand: false,
    introParagraphs: [] as string[],
    showIntroModal: false,
    matrixBoxIds: [] as string[],
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
    overlayBars: [] as SwimBar[],
    loadError: '',
  },
  onShow() {
    void this.refreshFavState()
  },
  onShareAppMessage() {
    const u = this.data.unit
    const t = this.data.dynastyTitle || u?.name || '朝代详情'
    const id = u?.id
    const path = id ? `/pages/dynasty-detail/index?unitId=${encodeURIComponent(id)}` : '/pages/dynasty-detail/index'
    return { title: t, path }
  },
  async onLoad(query: Record<string, string | undefined>) {
    const unitId = query.unitId || query.id
    const dynastyHint = decodeURIComponent(query.dynasty || query.displayName || '')
    if (!unitId && !dynastyHint) return

    const sys = wx.getSystemInfoSync()
    const navH = Math.round(88 * (sys.windowWidth / 750))
    const headerPadPx = (sys.statusBarHeight || 20) + navH
    const tabBarH = Math.round(72 * (sys.windowWidth / 750))
    const scrollTop = headerPadPx + tabBarH
    const anchorYear = query.anchorYear ? parseInt(query.anchorYear, 10) : NaN

    const applyPageData = (
      hero: UnitHero,
      swim: SwimMatrix,
    ) => {
      const unit = hero.unit
      const dynastyTitle = (unit.dynastyName && unit.dynastyName.trim()) || unit.name
      const navTitle = dynastyTitle.length <= 4 ? dynastyTitle : dynastyTitle.slice(0, 4)
      const heroSubLine = `${unit.startYear}–${unit.endYear}`
      const matrixBoxIds = collectMatrixBoxIds(swim)
      const { preview, canExpand, paragraphs } = previewIntro(unit.summary || '')
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
        introDisplay: preview,
        introCanExpand: canExpand,
        introParagraphs: paragraphs,
      })
      void this.refreshFavState()
      if (!Number.isNaN(anchorYear)) {
        setTimeout(() => this.scrollToAnchorYear(anchorYear, swim), 120)
      }
    }

    if (unitId) {
      try {
        const enc = encodePathSegment(unitId)
        const [heroRes, swimRes] = await Promise.all([
          request<UnitHero>(`/units/${enc}`),
          request<SwimMatrix>(`/units/${enc}/swim-matrix`),
        ])
        const enhancedSwim = {
          ...swimRes.data,
          ...generateTimelineTicks(swimRes.data.startYear, swimRes.data.endYear, swimRes.data.sheetWidthRpx),
        }
        applyPageData(heroRes.data, enhancedSwim)
        return
      } catch (e: any) {
        console.error('[dynasty-detail] API failed', e)
        const msg = e?.message || '加载失败'
        this.setData({
          unit: null,
          swim: null,
          loadError: `无法加载朝代数据（${msg}）。请确认后端已启动且已导入 historical_dynasty / historical_box 数据。`,
        })
        wx.showToast({ title: '加载失败', icon: 'none' })
        return
      }
    }

    this.setData({ loadError: '缺少朝代 ID，无法加载' })
  },
  scrollToAnchorYear(anchorYear: number, swim: SwimMatrix) {
    const span = Math.max(1, swim.endYear - swim.startYear)
    const clamped = Math.max(swim.startYear, Math.min(swim.endYear, anchorYear))
    const sheetPx = (swim.sheetWidthRpx || 1440) * (wx.getSystemInfoSync().windowWidth / 750)
    const targetPx = ((clamped - swim.startYear) / span) * sheetPx
    const bias = wx.getSystemInfoSync().windowWidth * 0.32
    const left = Math.max(0, targetPx - bias)
    this.swimScrollLeft = left
    this.setData({ matrixScrollLeft: left, axisScrollLeft: left })
  },
  // 泳道主体横滑：仅在吸顶时把位置同步给顶部固定时间轴
  onMatrixHScroll(e: WechatMiniprogram.ScrollViewScroll) {
    const left = e.detail.scrollLeft
    this.swimScrollLeft = left
    if (this._echoMatrix) {
      this._echoMatrix = false
      return
    }
    if (this.data.axisPinned) {
      this._echoAxis = true
      this.setData({ axisScrollLeft: left })
    }
  },
  // 顶部固定时间轴横滑：回写给泳道主体
  onAxisHScroll(e: WechatMiniprogram.ScrollViewScroll) {
    const left = e.detail.scrollLeft
    this.swimScrollLeft = left
    if (this._echoAxis) {
      this._echoAxis = false
      return
    }
    this._echoMatrix = true
    this.setData({ matrixScrollLeft: left })
  },
  onDynastyScroll(e: WechatMiniprogram.ScrollViewScroll) {
    const top = e.detail.scrollTop
    const pinned = top > 120
    if (pinned !== this.data.axisPinned) {
      this.setData({ axisPinned: pinned })
    }
  },
  onBarTap(e: WechatMiniprogram.BaseEvent) {
    const boxId = (e.currentTarget as any).dataset.box as string
    if (!boxId) return
    navigateTo(ROUTES.boxDetail, { boxId })
  },
  showMoreOverlay(e: WechatMiniprogram.BaseEvent) {
    const label = (e.currentTarget as any).dataset.label as string
    const laneIdx = Number((e.currentTarget as any).dataset.lane)
    const swim = this.data.swim
    if (!swim) return
    const lane = swim.lanes[laneIdx] as SwimLane & { extraBars?: SwimBar[] }
    if (!lane) return
    const bars = (lane.extraBars && lane.extraBars.length)
      ? lane.extraBars
      : lane.collapsedRows.flat()
    this.setData({ overlayVisible: true, overlayLabel: label, overlayBars: bars })
  },
  hideOverlay() {
    this.setData({ overlayVisible: false })
  },
  goUnit(e: WechatMiniprogram.BaseEvent) {
    const id = (e.currentTarget as any).dataset.id as string
    navigateTo(ROUTES.dynastyDetail, { unitId: id })
  },
  goNext() {
    const n = this.data.nextUnit
    if (!n?.unitId) return
    navigateTo(ROUTES.dynastyDetail, { unitId: n.unitId, dynasty: n.title })
  },
  openIntro() {
    if (!this.data.introCanExpand) return
    this.setData({ showIntroModal: true, introModalTitle: (this.data.dynastyTitle || '') + '·朝代简介' })
  },
  closeIntro() {
    this.setData({ showIntroModal: false })
  },
  noop() {},
  async refreshFavState() {
    const boxIds = this.data.matrixBoxIds
    if (!boxIds.length || !hasToken()) {
      this.setData({ isFav: false, favPartial: false })
      return
    }
    const favorited = await fetchFavoritedBoxIdSet()
    const st = computeUnitFavoriteState(boxIds, favorited)
    this.setData({ isFav: st.allFavorited, favPartial: st.anyFavorited && !st.allFavorited })
  },
  async onFavoriteTap() {
    if (this.data.favToggling || !hasToken()) {
      if (!hasToken()) promptLoginForFavorite()
      return
    }
    const boxIds = this.data.matrixBoxIds
    if (!boxIds.length) {
      wx.showToast({ title: '当前朝代暂无史略可收藏', icon: 'none' })
      return
    }
    const favorited = await fetchFavoritedBoxIdSet()
    const st = computeUnitFavoriteState(boxIds, favorited)
    const nextFav = !st.allFavorited
    this.setData({ favToggling: true })
    try {
      await setBoxesFavorited(boxIds, nextFav)
      await this.refreshFavState()
      wx.showToast({ title: nextFav ? '已收藏本朝史略' : '已取消收藏', icon: 'success' })
    } catch (e: unknown) {
      wx.showToast({ title: e instanceof Error ? e.message : '操作失败', icon: 'none' })
    } finally {
      this.setData({ favToggling: false })
    }
  },
  onShareTap() {
    promptContentShareUnavailable()
  },
})
