import { hasToken, request } from '../../native-utils/api'
import {
  appendGroupedItems,
  DateGroup,
  formatClockTime,
  groupByDateKey,
} from '../../native-utils/date-grouped-list'
import { FootprintCardView, FootprintItemRaw, toFootprintCardView } from '../../native-utils/favorite-display'
import { computePageTopPadPx } from '../../native-utils/nav-metrics'
import { ROUTES, navigateTo } from '../../native-utils/router'

const PAGE_SIZE = 50

type FootprintRow = FootprintCardView

Page({
  data: {
    hasToken: false,
    loaded: false,
    loadingMore: false,
    hasMore: false,
    loadFinished: false,
    total: 0,
    page: 0,
    summaryText: '',
    groups: [] as DateGroup<FootprintRow>[],
    pageTopPadPx: 88,
  },
  _loading: false,
  onLoad() {
    try {
      this.setData({ pageTopPadPx: computePageTopPadPx() })
    } catch {
      this.setData({ pageTopPadPx: 88 })
    }
  },
  onShow() {
    const ok = hasToken()
    if (!ok) {
      this.setData({
        hasToken: false,
        loaded: true,
        loadingMore: false,
        hasMore: false,
        loadFinished: false,
        total: 0,
        page: 0,
        summaryText: '',
        groups: [],
      })
      return
    }
    const silent = this.data.groups.length > 0
    this.setData({ hasToken: true })
    void this.load({ reset: true, silent })
  },
  onReachBottom() {
    if (!this.data.hasToken || !this.data.hasMore || this.data.loadingMore || this._loading) return
    void this.load({ reset: false, silent: true })
  },
  goLogin() {
    navigateTo(ROUTES.login)
  },
  toRows(items: FootprintItemRaw[]): FootprintRow[] {
    return items.map((item) => {
      const view = toFootprintCardView(item)
      return {
        ...view,
        timeLabel: formatClockTime(item.lastViewedAt) || view.timeLabel,
      }
    })
  },
  async load(opts: { reset: boolean; silent?: boolean }) {
    if (this._loading) return
    this._loading = true
    const reset = opts.reset
    const silent = Boolean(opts.silent)
    const nextPage = reset ? 1 : this.data.page + 1
    if (!silent) {
      this.setData(reset ? { loaded: false } : { loadingMore: true })
    } else if (!reset) {
      this.setData({ loadingMore: true })
    }
    try {
      const res = await request<{ items: FootprintItemRaw[]; total: number }>(
        `/footprints/boxes?page=${nextPage}&pageSize=${PAGE_SIZE}`,
        { auth: true }
      )
      const batch = this.toRows(res.data.items || [])
      const total = res.data.total ?? 0
      const prevGroups = this.data.groups as DateGroup<FootprintRow>[]
      const groups = reset
        ? groupByDateKey<FootprintRow>(batch, (item) => item.lastViewedAt)
        : appendGroupedItems<FootprintRow>(
            prevGroups,
            batch,
            (item) => item.lastViewedAt,
            (item) => item.boxId
          )
      const loadedCount = groups.reduce((n, g) => n + g.items.length, 0)
      const hasMore = batch.length >= PAGE_SIZE && loadedCount < total
      this.setData({
        groups,
        total,
        page: nextPage,
        hasMore,
        loadFinished: !hasMore && loadedCount > 0,
        summaryText: total > 0 ? `共 ${total} 条 · 按访问时间由近及远` : '',
        loaded: true,
        loadingMore: false,
      })
    } catch {
      if (reset) {
        this.setData({
          groups: [],
          total: 0,
          page: 0,
          hasMore: false,
          loadFinished: false,
          summaryText: '',
          loaded: true,
          loadingMore: false,
        })
      } else {
        this.setData({ loadingMore: false })
        wx.showToast({ title: '加载失败', icon: 'none' })
      }
    } finally {
      this._loading = false
    }
  },
  go(e: WechatMiniprogram.BaseEvent) {
    const id = (e.currentTarget as WechatMiniprogram.IAnyObject).dataset.id as string
    if (!id) return
    navigateTo(ROUTES.boxDetail, { boxId: id })
  },
})
