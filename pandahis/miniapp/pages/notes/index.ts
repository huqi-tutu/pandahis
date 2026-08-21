import { hasToken } from '../../native-utils/api'
import { fetchNoteDynasties, type NoteDynastyItem } from '../../native-utils/note'
import { computePageTopPadPx } from '../../native-utils/nav-metrics'
import { ROUTES, navigateTo } from '../../native-utils/router'

Page({
  data: {
    hasToken: false,
    loaded: false,
    items: [] as NoteDynastyItem[],
    pageTopPadPx: 88,
  },
  onLoad() {
    try {
      this.setData({ pageTopPadPx: computePageTopPadPx() })
    } catch {
      this.setData({ pageTopPadPx: 88 })
    }
  },
  onShow() {
    const ok = hasToken()
    this.setData({ hasToken: ok, loaded: false })
    if (ok) void this.load()
    else this.setData({ loaded: true, items: [] })
  },
  goLogin() {
    navigateTo(ROUTES.login)
  },
  async load() {
    try {
      const items = await fetchNoteDynasties()
      this.setData({ items, loaded: true })
    } catch {
      this.setData({ items: [], loaded: true })
    }
  },
  onDynastyTap(e: WechatMiniprogram.BaseEvent) {
    const ds = (e.currentTarget as WechatMiniprogram.IAnyObject).dataset
    const dynastyId = String(ds.id || '').trim()
    if (!dynastyId) {
      wx.showToast({ title: '缺少朝代信息', icon: 'none' })
      return
    }
    navigateTo(ROUTES.noteList, {
      dynastyId,
      dynastyName: String(ds.name || ''),
      civilizationName: String(ds.civ || ''),
    })
  },
})
