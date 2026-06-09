const protoPage = require('../../behaviors/proto-page.js')

Page({
  behaviors: [protoPage],

  data: {
    title: '乌台诗案',
    sub: '1079 · 华夏 · 事略',
    tabs: ['详情', '关系', '评述', '见证'],
    tabActive: 3,
    list: [
      { badge: '寒食帖', name: '黄州寒食帖', desc: '苏轼被贬黄州第三年寒食节所写。天下第三行书，笔意苍茫郁结。', museum: '台北故宫博物院' },
      { badge: '词稿', name: '赤壁赋卷', desc: '苏轼亲笔行书，完整保留《前赤壁赋》全文，纸色古朴。', museum: '台北故宫博物院' },
      { badge: '砚', name: '东坡铭端砚', desc: '黄州时期随身之物，背面刻有苏轼亲书铭文，端溪老坑石料。', museum: '北京故宫博物院' }
    ]
  },

  onLoad(options) {
    const title = options.title ? decodeURIComponent(options.title) : '乌台诗案'
    this.setData({ title })
  },

  onTabTap(e) {
    const i = Number(e.currentTarget.dataset.i)
    if (i === 3) return
    const q = encodeURIComponent(this.data.title)
    const urls = [
      `/pages/box-detail/box-detail?title=${q}`,
      `/pages/box-graph/box-graph?title=${q}`,
      `/pages/box-critique/box-critique?title=${q}`,
      ''
    ]
    wx.redirectTo({ url: urls[i] })
  },

  openRelic(e) {
    const name = e.currentTarget.dataset.name
    wx.navigateTo({
      url: `/pages/relic-detail/relic-detail?name=${encodeURIComponent(name)}`
    })
  }
})
