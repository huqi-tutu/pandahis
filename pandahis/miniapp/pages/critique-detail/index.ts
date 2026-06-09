Page({
  data: {
    title: '',
    author: '',
    book: '',
    era: '',
    body: '',
  },
  onLoad(query: Record<string, string | undefined>) {
    this.setData({
      title: decodeURIComponent(query.title || ''),
      author: decodeURIComponent(query.author || ''),
      book: decodeURIComponent(query.book || ''),
      era: decodeURIComponent(query.era || ''),
      body: decodeURIComponent(query.body || ''),
    })
  },
})
