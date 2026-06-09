const protoPage = require('../../behaviors/proto-page.js')
const { buildSwimData } = require('../../data/mock-dynasty.js')

// 并发 Tab 栏高度（px）：12rpx上 + 48rpx pill + 12rpx下 ≈ 36px
const CONCURRENT_TAB_H = 36

Page({
  behaviors: [protoPage],

  data: {
    dynasty:        null,
    scrollTop:      0,
    isFavorite:     false,
    overlayVisible: false,
    overlayLabel:   '',
    overlayBars:    [],
  },

  onLoad(options) {
    const dynastyName = decodeURIComponent(options.dynasty || '北宋')
    const d = buildSwimData(dynastyName)
    this.setData({ dynasty: d })
  },

  onReady() {
    try {
      const sys = wx.getSystemInfoSync()
      const statusBar = sys.statusBarHeight || 20
      // 状态栏 + 导航栏 44px + 并发 Tab 栏
      const top = statusBar + 44 + CONCURRENT_TAB_H
      this.setData({ scrollTop: top })
    } catch (e) {
      this.setData({ scrollTop: 118 })
    }
  },

  goNext() {
    const next = this.data.dynasty && this.data.dynasty.next
    if (next && next.dynasty) {
      wx.navigateTo({
        url: `/pages/dynasty-detail/dynasty-detail?dynasty=${encodeURIComponent(next.dynasty)}`
      })
    }
  },

  toggleFavorite() {
    const next = !this.data.isFavorite
    this.setData({ isFavorite: next })
    wx.showToast({
      title: next ? '已收藏' : '已取消收藏',
      icon: 'none',
      duration: 1200,
    })
  },

  onShare() {
    wx.showShareMenu({ withShareTicket: true })
  },

  showMoreOverlay(e) {
    const { lane, label } = e.currentTarget.dataset
    const extraBars = this.data.dynasty.lanes[lane].extraBars
    this.setData({
      overlayVisible: true,
      overlayLabel:   label,
      overlayBars:    extraBars,
    })
  },

  hideOverlay() {
    this.setData({ overlayVisible: false })
  },

  onBarTap(e) {
    const { boxKey, boxTitle } = e.currentTarget.dataset
    if (!boxKey && !boxTitle) return
    wx.navigateTo({
      url: `/pages/box-detail/box-detail?title=${encodeURIComponent(boxTitle || '')}`
    })
  },
})
