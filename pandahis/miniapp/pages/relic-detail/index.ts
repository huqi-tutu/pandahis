Page({
  data: {
    name: '',
    museum: '',
    detail: '',
    imageUrl: '',
  },
  onLoad(query: Record<string, string | undefined>) {
    this.setData({
      name: decodeURIComponent(query.name || ''),
      museum: decodeURIComponent(query.museum || ''),
      detail: decodeURIComponent(query.detail || ''),
      imageUrl: decodeURIComponent(query.imageUrl || ''),
    })
  },
})
