Page({
  data: {
    title: '',
    author: '',
    book: '',
    era: '',
    body: '',
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
    this.setData({
      title: decodeURIComponent(query.title || ''),
      author: decodeURIComponent(query.author || ''),
      book: decodeURIComponent(query.book || ''),
      era: decodeURIComponent(query.era || ''),
      body: decodeURIComponent(query.body || ''),
    })
  },
})
