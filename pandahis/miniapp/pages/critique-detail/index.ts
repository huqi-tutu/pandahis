import { computePageTopPadPx } from '../../native-utils/nav-metrics'

Page({
  data: {
    title: '',
    author: '',
    book: '',
    era: '',
    body: '',
    pageTopPadPx: 88,
  },
  onLoad(query: Record<string, string | undefined>) {
    try {
      this.setData({ pageTopPadPx: computePageTopPadPx() })
    } catch {
      this.setData({ pageTopPadPx: 88 })
    }
    this.setData({
      title: decodeURIComponent(query.title || ''),
      author: decodeURIComponent(query.author || ''),
      book: decodeURIComponent(query.book || ''),
      era: decodeURIComponent(query.era || ''),
      body: decodeURIComponent(query.body || ''),
    })
  },
})
