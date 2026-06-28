import { request } from '../../native-utils/api'
import { formatSearchPath, highlightEmToRich, stripHtml } from '../../native-utils/format'
import { ROUTES, navigateTo } from '../../native-utils/router'

const FILTER_CATS = ['全部', '君纪', '士臣', '典制', '事略', '民录'] as const

type SearchResult = {
  total: number
  items: { type: string; id: string; pathText: string; titleHighlight: string; descHighlight: string }[]
}

type ResultItem = {
  key: string
  type: string
  id: string
  pathText: string
  titleRich: string
  descRich: string
  hasDesc: boolean
  category: string
}

function extractCategory(pathText: string, type: string): string {
  if (type !== 'box') return ''
  const parts = String(pathText || '')
    .split(/[›>]/g)
    .map((s) => s.trim())
    .filter(Boolean)
  const last = parts[parts.length - 1] || ''
  return (FILTER_CATS as readonly string[]).includes(last) ? last : ''
}

function applyFilter(items: ResultItem[], filterIndex: number): ResultItem[] {
  if (filterIndex <= 0) return items
  const cat = FILTER_CATS[filterIndex]
  return items.filter((it) => it.category === cat)
}

Page({
  data: {
    keyword: '',
    searching: false,
    results: [] as ResultItem[],
    filteredResults: [] as ResultItem[],
    resultTotal: 0,
    filterCats: [...FILTER_CATS],
    filterIndex: 0,
    headerPadPx: 88,
  },
  onLoad(query: Record<string, string | undefined>) {
    try {
      const sys = wx.getSystemInfoSync()
      const navPx = 88 * (sys.windowWidth / 750)
      this.setData({ headerPadPx: (sys.statusBarHeight || 20) + navPx })
    } catch {
      this.setData({ headerPadPx: 88 })
    }
    const keyword = decodeURIComponent(query.q || query.keyword || '')
    this.setData({ keyword })
    if (keyword) void this.doSearch(keyword)
  },
  mapResultItems(items: SearchResult['items']): ResultItem[] {
    return (items || []).map((it) => {
      const pathText = formatSearchPath(it.pathText || '')
      const descPlain = stripHtml(it.descHighlight || '')
      return {
        key: `${it.type}-${it.id}`,
        type: it.type,
        id: it.id,
        pathText,
        titleRich: highlightEmToRich(it.titleHighlight || ''),
        descRich: highlightEmToRich(it.descHighlight || ''),
        hasDesc: descPlain.length > 0,
        category: extractCategory(pathText, it.type),
      }
    })
  },
  async doSearch(keyword: string) {
    this.setData({ searching: true, filterIndex: 0 })
    try {
      const q = encodeURIComponent(keyword)
      const res = await request<SearchResult>(`/search?q=${q}&page=1&pageSize=20`)
      const results = this.mapResultItems(res.data.items || [])
      this.setData({
        results,
        filteredResults: results,
        resultTotal: res.data.total ?? results.length,
        searching: false,
      })
    } catch (e: unknown) {
      wx.showToast({ title: e instanceof Error ? e.message : '搜索失败', icon: 'none' })
      this.setData({ searching: false })
    }
  },
  onFilter(e: WechatMiniprogram.BaseEvent) {
    const i = Number((e.currentTarget as WechatMiniprogram.IAnyObject).dataset.i)
    if (!Number.isFinite(i)) return
    const results = this.data.results as ResultItem[]
    this.setData({
      filterIndex: i,
      filteredResults: applyFilter(results, i),
    })
  },
  go(e: WechatMiniprogram.BaseEvent) {
    const ds = (e.currentTarget as WechatMiniprogram.IAnyObject).dataset as { type: string; id: string }
    if (ds.type === 'unit') {
      navigateTo(ROUTES.unitDetail, { unitId: ds.id })
      return
    }
    if (ds.type === 'box') {
      navigateTo(ROUTES.boxDetail, { boxId: ds.id })
    }
  },
})
