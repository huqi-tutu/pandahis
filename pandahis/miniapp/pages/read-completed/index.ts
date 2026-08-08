import { hasToken, request } from '../../native-utils/api'
import {
  appendGroupedItems,
  DateGroup,
  formatClockTime,
  groupByDateKey,
} from '../../native-utils/date-grouped-list'
import {
  ReadCompleteCardView,
  ReadCompleteItemRaw,
  toReadCompleteCardView,
} from '../../native-utils/favorite-display'
import { unmarkBoxReadComplete } from '../../native-utils/read-complete'
import { ROUTES, navigateTo } from '../../native-utils/router'
import { computePageTopPadPx } from '../../native-utils/nav-metrics'

const ACTION_WIDTH_RPX = 168
const PAGE_SIZE = 50

type ReadCompleteRow = ReadCompleteCardView & { swipeX: number }

type SwipeSession = {
  boxId: string
  startX: number
  startOffset: number
}

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
    groups: [] as DateGroup<ReadCompleteRow>[],
    pageTopPadPx: 88,
    openBoxId: '',
    draggingBoxId: '',
  },
  _actionWidthPx: 84,
  _swipe: null as SwipeSession | null,
  _loading: false,
  onLoad() {
    try {
      const sys = wx.getSystemInfoSync()
      this._actionWidthPx = ACTION_WIDTH_RPX * (sys.windowWidth / 750)
      this.setData({ pageTopPadPx: computePageTopPadPx(sys) })
    } catch {
      this.setData({ pageTopPadPx: 88 })
    }
  },
  onShow() {
    const ok = hasToken()
    this._swipe = null
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
        openBoxId: '',
        draggingBoxId: '',
      })
      return
    }
    const silent = this.data.groups.length > 0
    this.setData({ hasToken: true, openBoxId: '', draggingBoxId: '' })
    void this.load({ reset: true, silent })
  },
  onReachBottom() {
    if (!this.data.hasToken || !this.data.hasMore || this.data.loadingMore || this._loading) return
    void this.load({ reset: false, silent: true })
  },
  goLogin() {
    navigateTo(ROUTES.login)
  },
  buildSummary(total: number) {
    if (total <= 0) return ''
    return `共 ${total} 条 · 按标记时间由近及远 · 左滑可取消`
  },
  toRows(items: ReadCompleteItemRaw[]): ReadCompleteRow[] {
    const openBoxId = this.data.openBoxId
    const actionWidthPx = this._actionWidthPx
    return items.map((item) => {
      const view = toReadCompleteCardView(item)
      return {
        ...view,
        timeLabel: formatClockTime(item.completedAt) || view.timeLabel,
        swipeX: item.boxId === openBoxId ? -actionWidthPx : 0,
      }
    })
  },
  mapGroupsSwipe(
    groups: DateGroup<ReadCompleteRow>[],
    updater: (row: ReadCompleteRow) => ReadCompleteRow
  ): DateGroup<ReadCompleteRow>[] {
    return groups.map((g) => ({
      ...g,
      items: g.items.map(updater),
    }))
  },
  findRow(boxId: string): ReadCompleteRow | undefined {
    for (const g of this.data.groups) {
      const hit = g.items.find((row) => row.boxId === boxId)
      if (hit) return hit
    }
    return undefined
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
      const res = await request<{ items: ReadCompleteItemRaw[]; total: number }>(
        `/read-complete/boxes?page=${nextPage}&pageSize=${PAGE_SIZE}`,
        { auth: true }
      )
      const batch = this.toRows(res.data.items || [])
      const total = res.data.total ?? 0
      const prevGroups = this.data.groups as DateGroup<ReadCompleteRow>[]
      let groups = reset
        ? groupByDateKey<ReadCompleteRow>(batch, (item) => item.completedAt)
        : appendGroupedItems<ReadCompleteRow>(
            prevGroups,
            batch,
            (item) => item.completedAt,
            (item) => item.boxId
          )
      const openBoxId = this.data.openBoxId
      const stillOpen =
        openBoxId && groups.some((g) => g.items.some((item) => item.boxId === openBoxId))
          ? openBoxId
          : ''
      if (stillOpen !== openBoxId) {
        groups = this.mapGroupsSwipe(groups, (row) => ({ ...row, swipeX: 0 }))
      }
      const loadedCount = groups.reduce((n, g) => n + g.items.length, 0)
      const hasMore = batch.length >= PAGE_SIZE && loadedCount < total
      this.setData({
        openBoxId: stillOpen,
        groups,
        total,
        page: nextPage,
        hasMore,
        loadFinished: !hasMore && loadedCount > 0,
        summaryText: this.buildSummary(total),
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
          openBoxId: '',
        })
      } else {
        this.setData({ loadingMore: false })
        wx.showToast({ title: '加载失败', icon: 'none' })
      }
    } finally {
      this._loading = false
    }
  },
  updateRowSwipe(boxId: string, swipeX: number, extra?: Record<string, unknown>) {
    const groups = this.mapGroupsSwipe(this.data.groups, (item) =>
      item.boxId === boxId ? { ...item, swipeX } : item
    )
    this.setData({ groups, ...(extra || {}) })
  },
  closeAllRows() {
    const groups = this.mapGroupsSwipe(this.data.groups, (item) => ({ ...item, swipeX: 0 }))
    this.setData({ groups, openBoxId: '' })
  },
  onSwipeStart(e: WechatMiniprogram.TouchEvent) {
    const boxId = String((e.currentTarget as WechatMiniprogram.IAnyObject).dataset.id || '')
    if (!boxId) return
    const item = this.findRow(boxId)
    if (!item) return
    if (this.data.openBoxId && this.data.openBoxId !== boxId) {
      this.closeAllRows()
    }
    const current = this.findRow(boxId)
    this._swipe = {
      boxId,
      startX: e.touches[0].clientX,
      startOffset: current?.swipeX ?? 0,
    }
    this.setData({ draggingBoxId: boxId })
  },
  onSwipeMove(e: WechatMiniprogram.TouchEvent) {
    const session = this._swipe
    if (!session) return
    const dx = e.touches[0].clientX - session.startX
    const max = this._actionWidthPx
    const next = Math.max(-max, Math.min(0, session.startOffset + dx))
    this.updateRowSwipe(session.boxId, next)
  },
  onSwipeEnd() {
    const session = this._swipe
    this._swipe = null
    this.setData({ draggingBoxId: '' })
    if (!session) return
    const item = this.findRow(session.boxId)
    const current = item?.swipeX ?? 0
    const open = Math.abs(current) > this._actionWidthPx * 0.38
    const swipeX = open ? -this._actionWidthPx : 0
    this.updateRowSwipe(session.boxId, swipeX, { openBoxId: open ? session.boxId : '' })
  },
  go(e: WechatMiniprogram.BaseEvent) {
    const id = String((e.currentTarget as WechatMiniprogram.IAnyObject).dataset.id || '')
    if (!id) return
    const item = this.findRow(id)
    if (!item) return
    if (Math.abs(item.swipeX) > 8) {
      this.updateRowSwipe(id, 0, { openBoxId: '' })
      return
    }
    navigateTo(ROUTES.boxDetail, { boxId: id })
  },
  async onUnmark(e: WechatMiniprogram.BaseEvent) {
    const boxId = String((e.currentTarget as WechatMiniprogram.IAnyObject).dataset.id || '')
    if (!boxId) return
    try {
      await unmarkBoxReadComplete(boxId)
      const groups = this.data.groups
        .map((g) => ({
          ...g,
          items: g.items.filter((item) => item.boxId !== boxId),
        }))
        .filter((g) => g.items.length > 0)
      const total = Math.max(0, this.data.total - 1)
      const openBoxId = this.data.openBoxId === boxId ? '' : this.data.openBoxId
      const loadedCount = groups.reduce((n, g) => n + g.items.length, 0)
      const hasMore = this.data.hasMore && loadedCount < total
      this.setData({
        groups,
        total,
        openBoxId,
        summaryText: this.buildSummary(total),
        hasMore,
        loadFinished: !hasMore && loadedCount > 0,
      })
      wx.showToast({ title: '已取消标记', icon: 'none' })
      // 删空当前已加载列表但仍有更多时，自动补一页
      if (hasMore && loadedCount === 0) {
        void this.load({ reset: false, silent: true })
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '操作失败'
      wx.showToast({ title: msg, icon: 'none' })
    }
  },
})

