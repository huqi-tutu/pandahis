const { hasToken, request } = require('../../native-utils/api')
const { ROUTES, navigateTo } = require('../../native-utils/router')

Page({
  data: {
    nickname: '',
    saving: false,
    headerPadPx: 88,
  },
  onLoad() {
    try {
      var sys = wx.getSystemInfoSync()
      var navPx = 88 * (sys.windowWidth / 750)
      this.setData({ headerPadPx: (sys.statusBarHeight || 20) + navPx })
    } catch (e) {
      this.setData({ headerPadPx: 88 })
    }
  },
  onShow() {
    if (!hasToken()) {
      navigateTo(ROUTES.login)
      return
    }
    this.load()
  },
  async load() {
    try {
      const res = await request('/me', { auth: true })
      this.setData({ nickname: res.data.nickname || '' })
    } catch {
      wx.showToast({ title: '加载失败', icon: 'none' })
    }
  },
  onInput(e) {
    this.setData({ nickname: e.detail.value })
  },
  async onSave() {
    if (this.data.saving) return
    const nickname = (this.data.nickname || '').trim()
    if (!nickname) {
      wx.showToast({ title: '请输入昵称', icon: 'none' })
      return
    }
    this.setData({ saving: true })
    try {
      await request('/me/profile', {
        method: 'PATCH',
        auth: true,
        data: { nickname },
      })
      wx.showToast({ title: '已保存', icon: 'success' })
      setTimeout(() => wx.navigateBack(), 400)
    } catch (e) {
      const msg = e instanceof Error ? e.message : '保存失败'
      wx.showToast({ title: msg.length > 18 ? `${msg.slice(0, 16)}…` : msg, icon: 'none' })
    } finally {
      this.setData({ saving: false })
    }
  },
})
