import { hasToken, request } from '../../native-utils/api'
import {
  addLocalSearchHistory,
  readLocalSearchHistory,
  removeLocalSearchHistory,
} from '../../native-utils/search-history-storage'
import { ROUTES, navigateTo } from '../../native-utils/router'
import { computePageTopPadPx } from '../../native-utils/nav-metrics'

type Suggest = {
  hotKeywords: { keyword: string; isHot: boolean }[]
  historyKeywords: { keyword: string; lastSearchedAt: string }[]
}

function dedupeHotKeywords(
  list: Suggest['hotKeywords']
): Suggest['hotKeywords'] {
  const seen = new Set<string>()
  const out: Suggest['hotKeywords'] = []
  for (const item of list) {
    const keyword = String(item?.keyword || '').trim()
    if (!keyword || seen.has(keyword)) continue
    seen.add(keyword)
    out.push({ keyword, isHot: Boolean(item.isHot) })
  }
  return out
}

Page({
  data: {
    keyword: '',
    hotKeywords: [] as Suggest['hotKeywords'],
    historyKeywords: [] as Suggest['historyKeywords'],
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
      hotKeywords = dedupeHotKeywords(res.data.hotKeywords || [])
      if (hasToken()) {
        historyKeywords = res.data.historyKeywords || []
      }
    } catch {
      // 离线时仍展示本地历史
    }
    // 未登录，或登录态服务端暂无历史时，回退本地最近搜索
    if (!historyKeywords.length) {
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
  onClear() {
    this.setData({ keyword: '' })
  },
  async doSearch() {
    const keyword = (this.data.keyword || '').trim()
    if (!keyword) {
      wx.showToast({ title: '请输入关键词', icon: 'none' })
      return
    }
    // 本地始终记一笔，保证「最近搜索」可展示；登录态另由 /search 写入服务端
    addLocalSearchHistory(keyword)
    navigateTo(ROUTES.searchResult, { q: keyword })
  },
  tapKeyword(e: WechatMiniprogram.BaseEvent) {
    const k = (e.currentTarget as WechatMiniprogram.IAnyObject).dataset.k as string
    if (!k) return
    addLocalSearchHistory(k)
    navigateTo(ROUTES.searchResult, { q: k })
  },
  async removeHistory(e: WechatMiniprogram.BaseEvent) {
    const k = (e.currentTarget as WechatMiniprogram.IAnyObject).dataset.k as string
    if (!k) return
    // 本地始终清除，避免服务端清空后被本地回退重新展示
    removeLocalSearchHistory(k)
    if (hasToken()) {
      try {
        const qs = `keyword=${encodeURIComponent(k)}`
        await request(`/search/history?${qs}`, { method: 'DELETE', auth: true })
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : '清除失败'
        if (msg === 'UNAUTHORIZED') {
          wx.showToast({ title: '请先登录', icon: 'none' })
          await this.loadSuggest()
          return
        }
        wx.showToast({ title: msg, icon: 'none' })
        await this.loadSuggest()
        return
      }
    }
    await this.loadSuggest()
  },
})
