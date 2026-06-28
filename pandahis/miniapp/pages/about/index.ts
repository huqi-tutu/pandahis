Page({
  data: {
    version: '0.1.0',
    headerPadPx: 88,
  },
  onLoad() {
    try {
      const sys = wx.getSystemInfoSync()
      const navPx = 88 * (sys.windowWidth / 750)
      this.setData({ headerPadPx: (sys.statusBarHeight || 20) + navPx })
    } catch {
      this.setData({ headerPadPx: 88 })
    }
  },
})
