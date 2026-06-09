const protoPage = require('../../behaviors/proto-page.js')
const { getCritiques } = require('../../data/data-loader.js')

const AVATAR_COLORS = ['#92ADA4', '#C9825A', '#7BA87B', '#B85A5A', '#84572F', '#5A8FA8']

Page({
  behaviors: [protoPage],

  data: {
    title: '乌台诗案',
    sub: '1079 · 华夏 · 事略',
    tabs: ['详情', '关系', '评述', '见证'],
    tabActive: 2,
    list: [],
  },

  onLoad(options) {
    const title = options.title ? decodeURIComponent(options.title) : '乌台诗案'
    const critiques = getCritiques(title)

    const list = critiques.map((c, idx) => ({
      author: c.author,
      era: c.era,
      title: c.title,
      book: c.book,
      content: c.content,
      summary: c.summary,
      avatar: c.author ? c.author[0] : '',
      color: AVATAR_COLORS[idx % AVATAR_COLORS.length],
    }))

    this.setData({
      title,
      list,
    })
  },

  onTabTap(e) {
    const i = Number(e.currentTarget.dataset.i)
    if (i === 2) return
    const q = encodeURIComponent(this.data.title)
    const urls = [
      `/pages/box-detail/box-detail?title=${q}`,
      `/pages/box-graph/box-graph?title=${q}`,
      '',
      `/pages/box-relics/box-relics?title=${q}`,
    ]
    wx.redirectTo({ url: urls[i] })
  },

  openItem(e) {
    const idx = Number(e.currentTarget.dataset.idx)
    const c = this.data.list[idx]
    wx.navigateTo({
      url: `/pages/critique-detail/critique-detail?title=${encodeURIComponent(c.title)}&author=${encodeURIComponent(c.author)}&book=${encodeURIComponent(c.book)}&era=${encodeURIComponent(c.era)}&content=${encodeURIComponent(c.content)}`,
    })
  },
})
