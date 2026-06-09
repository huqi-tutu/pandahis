import { hasToken, request } from '../../native-utils/api'
import {
  addLocalSearchHistory,
  readLocalSearchHistory,
  removeLocalSearchHistory,
} from '../../native-utils/search-history-storage'
import { getNavBarMetrics } from '../../native-utils/nav-metrics'
import { ROUTES, navigateTo } from '../../native-utils/router'

type Suggest = {
  hotKeywords: { keyword: string; isHot: boolean }[]
  historyKeywords: { keyword: string; lastSearchedAt: string }[]
}

Page({
  data: {
    keyword: '',
    hotKeywords: [] as Suggest['hotKeywords'],
    historyKeywords: [] as Suggest['historyKeywords'],
    topbarStyle: '',
  },
  onLoad() {
    void getNavBarMetrics()
      .then((m) => {
        this.setData({
          topbarStyle: `padding-top:${m.statusBarHeight}px;padding-left:${m.paddingLeft}px;padding-right:${m.paddingRight}px;`,
        })
      })
      .catch(() => {})
  },
  onShow() {
    const tab = typeof this.getTabBar === 'function' ? this.getTabBar() : null
    if (tab && typeof (tab as WechatMiniprogram.IAnyObject).setSelected === 'function') {
      ;(tab as WechatMiniprogram.IAnyObject).setSelected(1)
    }
    void this.loadSuggest()
  },
  async loadSuggest() {
    let hotKeywords: Suggest['hotKeywords'] = []
    let historyKeywords: Suggest['historyKeywords'] = []
    try {
      const res = await request<Suggest>('/search/suggest')
      hotKeywords = res.data.hotKeywords || []
      if (hasToken()) {
        historyKeywords = res.data.historyKeywords || []
      }
    } catch {
      // 离线时仍展示本地历史
    }
    if (!hasToken()) {
      historyKeywords = readLocalSearchHistory().map((keyword) => ({
        keyword,
        lastSearchedAt: '',
      }))
    }
    this.setData({ hotKeywords, historyKeywords })
  },
  onInput(e: WechatMiniprogram.Input) {
    this.setData({ keyword: e.detail.value || '' })
  },
  onConfirm() {
    void this.doSearch()
  },
  onBack() {
    wx.switchTab({ url: ROUTES.home })
  },
  onClear() {
    this.setData({ keyword: '' })
  },
  async doSearch() {
    const keyword = (this.data.keyword || '').trim()
    if (!keyword) {
      wx.showToast({ title: '请输入关键词', icon: 'none' })
      return
    }
    navigateTo(ROUTES.searchResult, { q: keyword })
  },
  tapKeyword(e: WechatMiniprogram.BaseEvent) {
    const k = (e.currentTarget as WechatMiniprogram.IAnyObject).dataset.k as string
    if (!k) return
    if (!hasToken()) addLocalSearchHistory(k)
    navigateTo(ROUTES.searchResult, { q: k })
  },
  async removeHistory(e: WechatMiniprogram.BaseEvent) {
    const k = (e.currentTarget as WechatMiniprogram.IAnyObject).dataset.k as string
    if (!k) return
    if (hasToken()) {
      try {
        const qs = `keyword=${encodeURIComponent(k)}`
        await request(`/search/history?${qs}`, { method: 'DELETE', auth: true })
        await this.loadSuggest()
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : '清除失败'
        if (msg === 'UNAUTHORIZED') {
          wx.showToast({ title: '请先登录', icon: 'none' })
          return
        }
        wx.showToast({ title: msg, icon: 'none' })
      }
      return
    }
    removeLocalSearchHistory(k)
    await this.loadSuggest()
  },
})
