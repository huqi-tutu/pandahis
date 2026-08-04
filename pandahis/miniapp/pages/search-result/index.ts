import { request } from '../../native-utils/api'
import { categoryLabel } from '../../native-utils/category-label'
import { stripHtml } from '../../native-utils/format'
import { addLocalSearchHistory } from '../../native-utils/search-history-storage'
import { ROUTES, navigateTo } from '../../native-utils/router'
import { computePageTopPadPx } from '../../native-utils/nav-metrics'
import { formatYearRange } from '../../native-utils/year-format'

type SearchApiItem = {
  type: string
  id: string
  pathText?: string
  titleHighlight?: string
  descHighlight?: string
  matchTier?: string
  categoryKey?: string
  categoryName?: string
  coordinateText?: string
  startYear?: number | null
  endYear?: number | null
  personTag?: string | null
}

type SearchResult = {
  total: number
  preciseTotal?: number
  relatedTotal?: number
  preciseItems?: SearchApiItem[]
  relatedItems?: SearchApiItem[]
  items?: SearchApiItem[]
}

type ResultItem = {
  key: string
  type: string
  id: string
  titlePlain: string
  category: string
  coordinateText: string
  yearText: string
  personTag: string
  hasPersonTag: boolean
}

Page({
  data: {
    keyword: '',
    searching: false,
    preciseResults: [] as ResultItem[],
    relatedResults: [] as ResultItem[],
    preciseTotal: 0,
    relatedTotal: 0,
    resultTotal: 0,
    pageTopPadPx: 88,
  },
  onLoad(query: Record<string, string | undefined>) {
    try {
      this.setData({ pageTopPadPx: computePageTopPadPx() })
    } catch {
      this.setData({ pageTopPadPx: 88 })
    }
    const keyword = decodeURIComponent(query.q || query.keyword || '')
    this.setData({ keyword })
    if (keyword) {
      addLocalSearchHistory(keyword)
      void this.doSearch(keyword)
    }
  },
  mapResultItem(it: SearchApiItem): ResultItem | null {
    const id = String(it.id || '').trim()
    if (!id) return null
    const type = String(it.type || 'box').trim() || 'box'
    const titlePlain = stripHtml(it.titleHighlight || '')
    const category =
      String(it.categoryName || '').trim() ||
      categoryLabel(String(it.categoryKey || ''))
    const coordinateText = String(it.coordinateText || '').trim()
    const startYear = typeof it.startYear === 'number' ? it.startYear : undefined
    const endYear = typeof it.endYear === 'number' ? it.endYear : undefined
    const yearText =
      startYear !== undefined || endYear !== undefined
        ? formatYearRange(startYear, endYear, ' — ')
        : ''
    const personTag = String(it.personTag || '').trim()
    return {
      key: `${type}-${id}`,
      type,
      id,
      titlePlain,
      category,
      coordinateText,
      yearText,
      personTag,
      hasPersonTag: personTag.length > 0,
    }
  },
  async doSearch(keyword: string) {
    this.setData({ searching: true })
    try {
      const q = encodeURIComponent(keyword)
      const res = await request<SearchResult>(`/search?q=${q}&page=1&pageSize=50`)
      const preciseRaw = Array.isArray(res.data.preciseItems)
        ? res.data.preciseItems
        : (res.data.items || []).filter((it) => it.matchTier !== 'related')
      const relatedRaw = Array.isArray(res.data.relatedItems)
        ? res.data.relatedItems
        : (res.data.items || []).filter((it) => it.matchTier === 'related')

      const preciseResults = preciseRaw
        .map((it) => this.mapResultItem(it))
        .filter((it): it is ResultItem => Boolean(it))
      const relatedResults = relatedRaw
        .map((it) => this.mapResultItem(it))
        .filter((it): it is ResultItem => Boolean(it))

      const preciseTotal = res.data.preciseTotal ?? preciseResults.length
      const relatedTotal = res.data.relatedTotal ?? relatedResults.length
      this.setData({
        preciseResults,
        relatedResults,
        preciseTotal,
        relatedTotal,
        resultTotal: res.data.total ?? preciseTotal + relatedTotal,
        searching: false,
      })
    } catch (e: unknown) {
      wx.showToast({ title: e instanceof Error ? e.message : '搜索失败', icon: 'none' })
      this.setData({
        searching: false,
        preciseResults: [],
        relatedResults: [],
        preciseTotal: 0,
        relatedTotal: 0,
        resultTotal: 0,
      })
    }
  },
  go(e: WechatMiniprogram.BaseEvent) {
    const ds = (e.currentTarget as WechatMiniprogram.IAnyObject).dataset as {
      type?: string
      id?: string
    }
    const id = String(ds.id || '').trim()
    if (!id) {
      wx.showToast({ title: '条目无效', icon: 'none' })
      return
    }
    // 搜索结果仅返回史略（box）；兼容旧 type
    const type = String(ds.type || 'box').trim()
    if (type === 'unit') {
      navigateTo(ROUTES.dynastyDetail, { unitId: id })
      return
    }
    navigateTo(ROUTES.boxDetail, { boxId: id })
  },
})
