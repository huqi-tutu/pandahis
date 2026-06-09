const protoPage = require('../../behaviors/proto-page.js')

Page({
  behaviors: [protoPage],

  data: {
    title: '黄帝',
    sub: '约前2717—前2599 · 华夏 · 君纪',
    tabs: ['详情', '关系', '评述', '见证'],
    tabActive: 1
  },

  onLoad(options) {
    const title = options.title ? decodeURIComponent(options.title) : '黄帝'
    if (title !== '黄帝') {
      this.setData({ title, sub: '示例 · 关系 Tab' })
    }
  },

  onTabTap(e) {
    const i = Number(e.currentTarget.dataset.i)
    if (i === 1) return
    const q = encodeURIComponent(this.data.title)
    const urls = [
      `/pages/box-detail/box-detail?title=${q}`,
      '',
      `/pages/box-critique/box-critique?title=${q}`,
      `/pages/box-relics/box-relics?title=${q}`
    ]
    wx.redirectTo({ url: urls[i] })
  }
})
