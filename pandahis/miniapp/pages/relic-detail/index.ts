import { computePageTopPadPx } from '../../native-utils/nav-metrics'

Page({
  data: {
    name: '',
    museum: '',
    detail: '',
    imageUrl: '',
    pageTopPadPx: 88,
  },
  onLoad(query: Record<string, string | undefined>) {
    try {
      this.setData({ pageTopPadPx: computePageTopPadPx() })
    } catch {
      this.setData({ pageTopPadPx: 88 })
    }
    this.setData({
      name: decodeURIComponent(query.name || ''),
      museum: decodeURIComponent(query.museum || ''),
      detail: decodeURIComponent(query.detail || ''),
      imageUrl: decodeURIComponent(query.imageUrl || ''),
    })
  },
})
