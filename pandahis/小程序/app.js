App({
  globalData: {
    userInfo: null,
    isVip: false,
    pendingCiv: null,   // home-overview 切换文明时传递
    matrixDataSource: 'local', // local | cloud
  },

  onLaunch() {
    this._initCloud()
    // 初始化全局状态
    try {
      const userInfo = wx.getStorageSync('user_info')
      if (userInfo) this.globalData.userInfo = userInfo
    } catch (e) {}

    this._loadFonts()
  },

  _initCloud() {
    try {
      const cloudEnv = require('./config/cloud.env.js')
      if (wx.cloud && cloudEnv.envId && cloudEnv.envId !== 'YOUR_ENV_ID') {
        wx.cloud.init({
          env: cloudEnv.envId,
          traceUser: true,
        })
      }
    } catch (e) {
      console.warn('[app] 云开发初始化跳过', e)
    }
  },

  // 加载自定义字体，解决 Android 无内置宋体问题
  _loadFonts() {
    // Noto Serif SC 700（帝王名用字重）
    wx.loadFontFace({
      family: 'Noto Serif SC',
      source: 'url("https://cdn.jsdelivr.net/npm/@fontsource/noto-serif-sc@5.1.1/files/noto-serif-sc-chinese-simplified-700-normal.woff2")',
      weight: '700',
      global: true,
      success() {},
      fail(err) {
        console.warn('[字体] Noto Serif SC 700 加载失败', err)
      }
    })

    // Noto Serif SC 400（备用：如有其他正文宋体需求）
    wx.loadFontFace({
      family: 'Noto Serif SC',
      source: 'url("https://cdn.jsdelivr.net/npm/@fontsource/noto-serif-sc@5.1.1/files/noto-serif-sc-chinese-simplified-400-normal.woff2")',
      weight: '400',
      global: true,
      success() {},
      fail(err) {
        console.warn('[字体] Noto Serif SC 400 加载失败', err)
      }
    })
  }
})
