import { hasToken, request } from '../../native-utils/api'
import { FootprintCardView, FootprintItemRaw, toFootprintCardView } from '../../native-utils/favorite-display'
import { ROUTES, navigateTo } from '../../native-utils/router'

Page({
  data: {
    hasToken: false,
    loaded: false,
    total: 0,
    summaryText: '',
    items: [] as FootprintCardView[],
  },
  onShow() {
    const ok = hasToken()
    this.setData({
      hasToken: ok,
      loaded: false,
      items: [],
      total: 0,
      summaryText: '',
    })
    if (ok) void this.load()
  },
  goLogin() {
    navigateTo(ROUTES.login)
  },
  async load() {
    try {
      const all: FootprintItemRaw[] = []
      let page = 1
      const pageSize = 50
      let total = 0
      while (true) {
        const res = await request<{ items: FootprintItemRaw[]; total: number }>(
          `/footprints/boxes?page=${page}&pageSize=${pageSize}`,
          { auth: true }
        )
        const batch = res.data.items || []
        all.push(...batch)
        total = res.data.total ?? all.length
        if (batch.length < pageSize || all.length >= total) break
        page += 1
      }
      const items = all.map(toFootprintCardView)
      this.setData({
        items,
        total,
        summaryText: total > 0 ? `共 ${total} 条 · 按访问时间由近及远` : '',
        loaded: true,
      })
    } catch {
      this.setData({ items: [], total: 0, summaryText: '', loaded: true })
    }
  },
  go(e: WechatMiniprogram.BaseEvent) {
    const id = (e.currentTarget as WechatMiniprogram.IAnyObject).dataset.id as string
    if (!id) return
    navigateTo(ROUTES.boxDetail, { boxId: id })
  },
})
