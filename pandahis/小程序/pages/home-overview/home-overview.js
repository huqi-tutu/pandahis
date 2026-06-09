const protoPage = require('../../behaviors/proto-page.js')

const CIV_SPOTS = [
  { id: 'huaxia',   name: '华夏',   color: '#C42828', img: '/配图/文明tab配图/01_华夏.png',   x: 68, y: 35 },
  { id: 'chaoxian', name: '朝鲜',   color: '#5B8DEF', img: '/配图/文明tab配图/02_朝鲜.png',   x: 73, y: 28 },
  { id: 'japan',    name: '日本',   color: '#E88FB5', img: '/配图/文明tab配图/03_日本.png',   x: 78, y: 30 },
  { id: 'sea',      name: '东南亚', color: '#5D8D8A', img: '/配图/文明tab配图/04_东南亚.png', x: 70, y: 48 },
  { id: 'india',    name: '南亚',   color: '#E88B3F', img: '/配图/文明tab配图/07_南亚.png',   x: 56, y: 42 },
  { id: 'persia',   name: '西亚',   color: '#B87A3A', img: '/配图/文明tab配图/08_西亚.png',   x: 46, y: 36 },
  { id: 'egypt',    name: '北非',   color: '#D6A84A', img: '/配图/文明tab配图/13_北非.png',   x: 36, y: 38 },
  { id: 'eeu',      name: '东欧',   color: '#8974B8', img: '/配图/文明tab配图/10_东欧.png',   x: 32, y: 25 },
  { id: 'medi',     name: '南欧',   color: '#4A80D0', img: '/配图/文明tab配图/09_南欧.png',   x: 28, y: 30 },
  { id: 'weu',      name: '西欧',   color: '#7F96B8', img: '/配图/文明tab配图/11_西欧.png',   x: 22, y: 26 },
  { id: 'wafrica',  name: '西非',   color: '#B55E3F', img: '/配图/文明tab配图/14_西非.png',   x: 26, y: 52 },
  { id: 'camer',    name: '中美',   color: '#D16848', img: '/配图/文明tab配图/16_中美.png',   x: 10, y: 45 },
  { id: 'andes',    name: '南美',   color: '#A27548', img: '/配图/文明tab配图/18_南美.png',   x: 12, y: 65 },
]

Page({
  behaviors: [protoPage],

  data: {
    civSpots: CIV_SPOTS
  },

  goMatrix() {
    wx.navigateBack({
      fail: () => wx.switchTab({ url: '/pages/home-matrix/home-matrix' })
    })
  },

  onSpotTap(e) {
    const { id, name } = e.currentTarget.dataset
    this._enterCiv(id, name)
  },

  onCivCardTap(e) {
    const id = e.currentTarget.dataset.id
    const spot = CIV_SPOTS.find(s => s.id === id)
    if (spot) this._enterCiv(spot.id, spot.name)
  },

  _enterCiv(id, name) {
    wx.switchTab({
      url: '/pages/home-matrix/home-matrix',
      success: () => {
        // 跳转后通知 home-matrix 切换到对应文明（通过全局变量）
        const app = getApp()
        app.globalData = app.globalData || {}
        app.globalData.pendingCiv = id
      }
    })
  }
})
