const protoPage = require('../../behaviors/proto-page.js')

const HOT_KEYWORDS = [
  { kw: '王安石变法', highlight: true },
  { kw: '唐玄宗', highlight: false },
  { kw: '奥斯曼帝国', highlight: false },
  { kw: '文艺复兴', highlight: true },
  { kw: '玛雅', highlight: false },
  { kw: '乌台诗案', highlight: false },
  { kw: '郑和下西洋', highlight: false },
]

Page({
  behaviors: [protoPage],

  data: {
    keyword: '',
    autoFocus: false,
    hot: HOT_KEYWORDS,
    history: [],
  },

  onShow() {
    try {
      const h = wx.getStorageSync('search_history') || []
      this.setData({ history: h.slice(0, 8) })
    } catch (e) {}
  },

  onInput(e) {
    this.setData({ keyword: e.detail.value })
  },

  clearInput() {
    this.setData({ keyword: '' })
  },

  onConfirm(e) {
    const kw = (e.detail.value || this.data.keyword).trim()
    if (!kw) return
    this._addHistory(kw)
    wx.navigateTo({ url: `/pages/search-result/search-result?keyword=${encodeURIComponent(kw)}` })
  },

  tapHot(e) {
    const kw = e.currentTarget.dataset.kw
    this._addHistory(kw)
    wx.navigateTo({ url: `/pages/search-result/search-result?keyword=${encodeURIComponent(kw)}` })
  },

  tapHist(e) {
    const kw = e.currentTarget.dataset.kw
    wx.navigateTo({ url: `/pages/search-result/search-result?keyword=${encodeURIComponent(kw)}` })
  },

  delHist(e) {
    const kw = e.currentTarget.dataset.kw
    const h = this.data.history.filter(i => i !== kw)
    wx.setStorageSync('search_history', h)
    this.setData({ history: h })
  },

  _addHistory(kw) {
    let h = wx.getStorageSync('search_history') || []
    h = [kw, ...h.filter(i => i !== kw)].slice(0, 20)
    wx.setStorageSync('search_history', h)
    this.setData({ history: h.slice(0, 8) })
  }
})
