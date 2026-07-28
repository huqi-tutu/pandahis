import { hasToken, request } from '../../native-utils/api'
import {
  FavoriteCardView,
  FavoriteItemRaw,
  UnitFavoriteCardView,
  UnitFavoriteItemRaw,
  toFavoriteCardView,
  toUnitFavoriteCardView,
} from '../../native-utils/favorite-display'
import { ROUTES, navigateTo } from '../../native-utils/router'
import { computePageTopPadPx } from '../../native-utils/nav-metrics'

type TabKey = 'dynasty' | 'shilue'

async function fetchAllBoxFavorites(): Promise<FavoriteItemRaw[]> {
  const all: FavoriteItemRaw[] = []
  let page = 1
  const pageSize = 50
  while (true) {
    const res = await request<{ items: FavoriteItemRaw[]; total: number }>(
      `/favorites/boxes?page=${page}&pageSize=${pageSize}`,
      { auth: true }
    )
    const batch = res.data.items || []
    all.push(...batch)
    const total = res.data.total ?? all.length
    if (batch.length < pageSize || all.length >= total) break
    page += 1
  }
  return all
}

async function fetchAllUnitFavorites(): Promise<UnitFavoriteItemRaw[]> {
  const all: UnitFavoriteItemRaw[] = []
  let page = 1
  const pageSize = 50
  while (true) {
    const res = await request<{ items: UnitFavoriteItemRaw[]; total: number }>(
      `/favorites/units?page=${page}&pageSize=${pageSize}`,
      { auth: true }
    )
    const batch = res.data.items || []
    all.push(...batch)
    const total = res.data.total ?? all.length
    if (batch.length < pageSize || all.length >= total) break
    page += 1
  }
  return all
}

Page({
  data: {
    hasToken: false,
    loaded: false,
    activeTab: 'dynasty' as TabKey,
    dynastyCount: 0,
    shilueCount: 0,
    visibleItems: [] as Array<FavoriteCardView | UnitFavoriteCardView>,
    dynastyItems: [] as UnitFavoriteCardView[],
    shilueItems: [] as FavoriteCardView[],
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
      const [unitRaw, boxRaw] = await Promise.all([
        fetchAllUnitFavorites(),
        fetchAllBoxFavorites(),
      ])
      const dynasty = unitRaw.map(toUnitFavoriteCardView)
      const shilue = boxRaw.map(toFavoriteCardView)
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
    const ds = (e.currentTarget as WechatMiniprogram.IAnyObject).dataset as {
      id?: string
      kind?: TabKey
    }
    const id = ds.id || ''
    if (!id) return
    if (ds.kind === 'dynasty' || this.data.activeTab === 'dynasty') {
      navigateTo(ROUTES.dynastyDetail, { unitId: id })
      return
    }
    navigateTo(ROUTES.boxDetail, { boxId: id })
  },
})
