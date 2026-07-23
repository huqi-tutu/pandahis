import { hasToken, request } from '../../native-utils/api'
import {
  ReadCompleteCardView,
  ReadCompleteItemRaw,
  toReadCompleteCardView,
} from '../../native-utils/favorite-display'
import { unmarkBoxReadComplete } from '../../native-utils/read-complete'
import { ROUTES, navigateTo } from '../../native-utils/router'

const ACTION_WIDTH_RPX = 168

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
    total: 0,
    summaryText: '',
    items: [] as ReadCompleteRow[],
    headerPadPx: 88,
    openBoxId: '',
    draggingBoxId: '',
  },
  _actionWidthPx: 84,
  _swipe: null as SwipeSession | null,
  onLoad() {
    try {
      const sys = wx.getSystemInfoSync()
      const navPx = 88 * (sys.windowWidth / 750)
      this._actionWidthPx = ACTION_WIDTH_RPX * (sys.windowWidth / 750)
      this.setData({ headerPadPx: (sys.statusBarHeight || 20) + navPx })
    } catch {
      this.setData({ headerPadPx: 88 })
    }
  },
  onShow() {
    const ok = hasToken()
    this._swipe = null
    this.setData({
      hasToken: ok,
      loaded: false,
      items: [],
      total: 0,
      summaryText: '',
      openBoxId: '',
      draggingBoxId: '',
    })
    if (ok) void this.load()
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
    return items.map((item) => ({
      ...toReadCompleteCardView(item),
      swipeX: item.boxId === openBoxId ? -actionWidthPx : 0,
    }))
  },
  async load() {
    try {
      const all: ReadCompleteItemRaw[] = []
      let page = 1
      const pageSize = 50
      let total = 0
      while (true) {
        const res = await request<{ items: ReadCompleteItemRaw[]; total: number }>(
          `/read-complete/boxes?page=${page}&pageSize=${pageSize}`,
          { auth: true }
        )
        const batch = res.data.items || []
        all.push(...batch)
        total = res.data.total ?? all.length
        if (batch.length < pageSize || all.length >= total) break
        page += 1
      }
      const openBoxId = this.data.openBoxId
      const stillOpen = openBoxId && all.some((item) => item.boxId === openBoxId) ? openBoxId : ''
      this.setData({
        openBoxId: stillOpen,
        items: this.toRows(all),
        total,
        summaryText: this.buildSummary(total),
        loaded: true,
      })
    } catch {
      this.setData({ items: [], total: 0, summaryText: '', loaded: true, openBoxId: '' })
    }
  },
  updateRowSwipe(boxId: string, swipeX: number, extra?: Record<string, unknown>) {
    const items = this.data.items.map((item) =>
      item.boxId === boxId ? { ...item, swipeX } : item
    )
    this.setData({ items, ...(extra || {}) })
  },
  closeAllRows() {
    const items = this.data.items.map((item) => ({ ...item, swipeX: 0 }))
    this.setData({ items, openBoxId: '' })
  },
  onSwipeStart(e: WechatMiniprogram.TouchEvent) {
    const boxId = String((e.currentTarget as WechatMiniprogram.IAnyObject).dataset.id || '')
    if (!boxId) return
    const item = this.data.items.find((row) => row.boxId === boxId)
    if (!item) return
    if (this.data.openBoxId && this.data.openBoxId !== boxId) {
      this.closeAllRows()
    }
    const current = this.data.items.find((row) => row.boxId === boxId)
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
    const item = this.data.items.find((row) => row.boxId === session.boxId)
    const current = item?.swipeX ?? 0
    const open = Math.abs(current) > this._actionWidthPx * 0.38
    const swipeX = open ? -this._actionWidthPx : 0
    this.updateRowSwipe(session.boxId, swipeX, { openBoxId: open ? session.boxId : '' })
  },
  go(e: WechatMiniprogram.BaseEvent) {
    const id = String((e.currentTarget as WechatMiniprogram.IAnyObject).dataset.id || '')
    if (!id) return
    const item = this.data.items.find((row) => row.boxId === id)
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
      const items = this.data.items.filter((item) => item.boxId !== boxId)
      const total = Math.max(0, this.data.total - 1)
      const openBoxId = this.data.openBoxId === boxId ? '' : this.data.openBoxId
      this.setData({
        items,
        total,
        openBoxId,
        summaryText: this.buildSummary(total),
      })
      wx.showToast({ title: '已取消标记', icon: 'none' })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '操作失败'
      wx.showToast({ title: msg, icon: 'none' })
    }
  },
})
