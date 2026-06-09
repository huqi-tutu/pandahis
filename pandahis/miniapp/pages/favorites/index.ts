import { hasToken, request } from '../../native-utils/api'
import {
  FavoriteCardView,
  FavoriteItemRaw,
  splitFavorites,
} from '../../native-utils/favorite-display'
import { ROUTES, navigateTo } from '../../native-utils/router'

type TabKey = 'dynasty' | 'shilue'

Page({
  data: {
    hasToken: false,
    loaded: false,
    activeTab: 'dynasty' as TabKey,
    dynastyCount: 0,
    shilueCount: 0,
    visibleItems: [] as FavoriteCardView[],
    dynastyItems: [] as FavoriteCardView[],
    shilueItems: [] as FavoriteCardView[],
  },
  onShow() {
    const ok = hasToken()
    this.setData({
      hasToken: ok,
      loaded: false,
      visibleItems: [],
      dynastyItems: [],
      shilueItems: [],
      dynastyCount: 0,
      shilueCount: 0,
    })
    if (ok) void this.load()
  },
  goLogin() {
    navigateTo(ROUTES.login)
  },
  onTab(e: WechatMiniprogram.BaseEvent) {
    const tab = (e.currentTarget as WechatMiniprogram.IAnyObject).dataset.tab as TabKey
    if (!tab || tab === this.data.activeTab) return
    this.applyTab(tab)
  },
  applyTab(tab: TabKey) {
    const visibleItems = tab === 'dynasty' ? this.data.dynastyItems : this.data.shilueItems
    this.setData({ activeTab: tab, visibleItems })
  },
  async load() {
    try {
      const all: FavoriteItemRaw[] = []
      let page = 1
      const pageSize = 50
      let total = 0
      while (true) {
        const res = await request<{ items: FavoriteItemRaw[]; total: number }>(
          `/favorites/boxes?page=${page}&pageSize=${pageSize}`,
          { auth: true }
        )
        const batch = res.data.items || []
        all.push(...batch)
        total = res.data.total ?? all.length
        if (batch.length < pageSize || all.length >= total) break
        page += 1
      }
      const { dynasty, shilue } = splitFavorites(all)
      const activeTab: TabKey =
        dynasty.length > 0 ? 'dynasty' : shilue.length > 0 ? 'shilue' : 'dynasty'
      const visibleItems = activeTab === 'dynasty' ? dynasty : shilue
      this.setData({
        dynastyItems: dynasty,
        shilueItems: shilue,
        dynastyCount: dynasty.length,
        shilueCount: shilue.length,
        activeTab,
        visibleItems,
        loaded: true,
      })
    } catch {
      this.setData({
        dynastyItems: [],
        shilueItems: [],
        visibleItems: [],
        dynastyCount: 0,
        shilueCount: 0,
        loaded: true,
      })
    }
  },
  go(e: WechatMiniprogram.BaseEvent) {
    const id = (e.currentTarget as WechatMiniprogram.IAnyObject).dataset.id as string
    if (!id) return
    navigateTo(ROUTES.boxDetail, { boxId: id })
  },
})
