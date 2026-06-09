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
}

type SwimMatrix = {
  startYear: number
  endYear: number
  endLabel: string
  ticks: { label: string; left: string }[]
  lanes: SwimLane[]
  concurrentItems: string[]
  sheetWidthRpx: number
}

function previewIntro(intro: string): { preview: string; canExpand: boolean } {
  const max = 80
  if (!intro || intro.length <= max) return { preview: intro || '', canExpand: false }
  return { preview: `${intro.slice(0, max)}…`, canExpand: true }
}

function heroDynastyTitle(dynastyTitle: string): string {
  const d = (dynastyTitle || '').trim()
  if (!d) return ''
  if (d.endsWith('朝')) return d
  return `${d}朝`
}

Page({
  swimScrollLeft: 0,
  data: {
    unit: null as UnitHero['unit'] | null,
    dynastyTitle: '',
    navTitle: '',
    heroDynastyTitle: '',
    heroSubLine: '',
    swim: null as SwimMatrix | null,
    concurrentItems: [] as string[],
    relatedUnits: [] as NonNullable<UnitHero['relatedUnits']>,
    nextUnit: null as UnitHero['nextUnit'] | null,
    introPreview: '',
    introCanExpand: false,
    showIntroModal: false,
    matrixBoxIds: [] as string[],
    isFav: false,
    favPartial: false,
    favToggling: false,
    scrollTop: 100,
    swimScrollLeft: 0,
    axisPinned: false,
    overlayVisible: false,
    overlayLabel: '',
    overlayBars: [] as SwimBar[],
  },
  onShow() {
    void this.refreshFavState()
  },
  onShareAppMessage() {
    const u = this.data.unit
    const t = this.data.dynastyTitle || u?.name || '朝代详情'
    const id = u?.id
    const path = id ? `/pages/unit-detail/index?unitId=${encodeURIComponent(id)}` : '/pages/unit-detail/index'
    return { title: t, path }
  },
  async onLoad(query: Record<string, string | undefined>) {
    const unitId = query.unitId || query.id
    if (!unitId) return
    const menu = wx.getMenuButtonBoundingClientRect()
    const sys = wx.getSystemInfoSync()
    const scrollTop = Math.max(Math.ceil(menu.bottom), (sys.statusBarHeight || 0) + 44) + 36

    try {
      const enc = encodePathSegment(unitId)
      const anchorYear = query.anchorYear ? parseInt(query.anchorYear, 10) : NaN
      const [heroRes, swimRes] = await Promise.all([
        request<UnitHero>(`/units/${enc}`),
        request<SwimMatrix>(`/units/${enc}/swim-matrix`),
      ])
      const hero = heroRes.data
      const unit = hero.unit
      const dynastyTitle = (unit.dynastyName && unit.dynastyName.trim()) || unit.name
      const navTitle = dynastyTitle.length <= 4 ? dynastyTitle : dynastyTitle.slice(0, 4)
      const swim = swimRes.data
      const yearRange = `${unit.startYear}–${unit.endYear}`
      const heroSubLine = yearRange

      const matrixBoxIds: string[] = []
      for (const lane of swim.lanes || []) {
        for (const row of lane.collapsedRows || []) {
          for (const bar of row) {
            if (bar.boxId) matrixBoxIds.push(bar.boxId)
          }
        }
      }

      const { preview, canExpand } = previewIntro(unit.summary || '')
      this.setData({
        unit,
        dynastyTitle,
        navTitle,
        heroDynastyTitle: heroDynastyTitle(dynastyTitle),
        heroSubLine,
        swim,
        concurrentItems: swim.concurrentItems || [],
        relatedUnits: hero.relatedUnits || [],
        nextUnit: hero.nextUnit ?? null,
        matrixBoxIds,
        scrollTop,
        introPreview: preview,
        introCanExpand: canExpand,
      })
      void this.refreshFavState()
      if (!Number.isNaN(anchorYear)) {
        setTimeout(() => this.scrollToAnchorYear(anchorYear, swim), 120)
      }
    } catch (e: any) {
      wx.showToast({ title: e?.message || '加载失败', icon: 'none' })
    }
  },
  scrollToAnchorYear(anchorYear: number, swim: SwimMatrix) {
    const span = Math.max(1, swim.endYear - swim.startYear)
    const clamped = Math.max(swim.startYear, Math.min(swim.endYear, anchorYear))
    const sheetPx = (swim.sheetWidthRpx || 1440) * (wx.getSystemInfoSync().windowWidth / 750)
    const targetPx = ((clamped - swim.startYear) / span) * sheetPx
    const bias = wx.getSystemInfoSync().windowWidth * 0.32
    const left = Math.max(0, targetPx - bias)
    this.setData({ swimScrollLeft: left })
  },
  onSwimHScroll(e: WechatMiniprogram.ScrollViewScroll) {
    this.swimScrollLeft = e.detail.scrollLeft
    this.setData({ swimScrollLeft: e.detail.scrollLeft })
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
    const lane = swim.lanes[laneIdx]
    if (!lane) return
    const bars = lane.collapsedRows.flat()
    this.setData({ overlayVisible: true, overlayLabel: label, overlayBars: bars })
  },
  hideOverlay() {
    this.setData({ overlayVisible: false })
  },
  goUnit(e: WechatMiniprogram.BaseEvent) {
    const id = (e.currentTarget as any).dataset.id as string
    navigateTo(ROUTES.unitDetail, { unitId: id })
  },
  goNext() {
    const n = this.data.nextUnit
    if (!n?.unitId) return
    navigateTo(ROUTES.unitDetail, { unitId: n.unitId })
  },
  openIntro() {
    this.setData({ showIntroModal: true })
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
