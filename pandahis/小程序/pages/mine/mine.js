const protoPage = require('../../behaviors/proto-page.js')

Page({
  behaviors: [protoPage],

  data: {
    name: '雄哥',
    phone: '138****8888',
    avatarLetter: '雄',
    isVip: false,
    footprintCount: 127,
    favoriteCount: 23,
    learnDays: 18,
    dynastyFav: 8,
    boxFav: 15,
  },

  onShow() {
    // 实际项目：从用户中心读取数据
  },

  goVip() {
    wx.switchTab({ url: '/pages/vip/vip' })
  },

  goFootprint() {
    wx.navigateTo({ url: '/pages/mine-footprint/mine-footprint' })
  },

  goFavorite() {
    wx.navigateTo({ url: '/pages/mine-favorite/mine-favorite' })
  },

  goLogin() {
    wx.showModal({
      title: '退出登录',
      content: '确认退出登录？',
      confirmText: '退出',
      confirmColor: '#9B3E38',
      success: (res) => {
        if (res.confirm) {
          wx.navigateTo({ url: '/pages/login/login' })
        }
      }
    })
  },

  noop() {}
})
