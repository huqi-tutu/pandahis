import { computePageTopPadPx } from '../../native-utils/nav-metrics'

Page({
  data: {
    navTitle: '',
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
    const title = decodeURIComponent(query.title || '')
    const navTitle = decodeURIComponent(query.navTitle || '') || title || '评述详情'
    this.setData({
      navTitle,
      title,
      author: decodeURIComponent(query.author || ''),
      book: decodeURIComponent(query.book || ''),
      era: decodeURIComponent(query.era || ''),
      body: decodeURIComponent(query.body || ''),
    })
  },
})
