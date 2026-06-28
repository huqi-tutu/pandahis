import { clearToken, getBaseUrl, hasToken } from '../../native-utils/api'
import { bindInviteCode } from '../../native-utils/invite-bind'
import { ROUTES, navigateTo } from '../../native-utils/router'

Page({
  data: {
    loggedIn: false,
    apiBase: '',
    bindCode: '',
    bindSubmitting: false,
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
  onShow() {
    this.setData({
      loggedIn: hasToken(),
      apiBase: getBaseUrl(),
    })
  },
  onBindInput(e: WechatMiniprogram.Input) {
    this.setData({ bindCode: (e.detail.value || '').toUpperCase() })
  },
  async submitBindCode() {
    if (!hasToken()) {
      navigateTo(ROUTES.login)
      return
    }
    if (this.data.bindSubmitting) return
    const code = (this.data.bindCode || '').trim()
    if (!code) {
      wx.showToast({ title: '请输入邀请码', icon: 'none' })
      return
    }
    this.setData({ bindSubmitting: true })
    try {
      const res = await bindInviteCode(code)
      wx.showToast({
        title: res.message || (res.bound ? '已绑定' : '绑定失败'),
        icon: res.bound ? 'success' : 'none',
      })
      if (res.bound) this.setData({ bindCode: '' })
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '提交失败'
      wx.showToast({ title: msg.length > 18 ? `${msg.slice(0, 16)}…` : msg, icon: 'none' })
    } finally {
      this.setData({ bindSubmitting: false })
    }
  },
  copySupportEmail() {
    const email = 'support@pandahis.com'
    wx.setClipboardData({
      data: email,
      success: () => wx.showToast({ title: '已复制邮箱', icon: 'success' }),
    })
  },
  goProfileEdit() {
    if (!hasToken()) {
      navigateTo(ROUTES.login)
      return
    }
    navigateTo(ROUTES.profileEdit)
  },
  goInviteReads() {
    navigateTo(ROUTES.invite)
  },
  clearCache() {
    wx.showModal({
      title: '清除缓存',
      content: '将清除本地图片缓存等数据，不会删除登录状态与邀请码。',
      success: (r) => {
        if (!r.confirm) return
        try {
          const info = wx.getStorageInfoSync()
          const keep = new Set(['accessToken', 'apiBaseUrl', 'pendingInviteCode', 'userLoggedOut'])
          for (const key of info.keys) {
            if (!keep.has(key)) wx.removeStorageSync(key)
          }
        } catch {
          // ignore
        }
        wx.showToast({ title: '已清除', icon: 'success' })
      },
    })
  },
  logout() {
    wx.showModal({
      title: '退出登录',
      content: '确定退出当前账号？',
      confirmText: '退出',
      success: (r) => {
        if (!r.confirm) return
        clearToken()
        this.setData({ loggedIn: false })
        wx.showToast({ title: '已退出', icon: 'success' })
        setTimeout(() => navigateTo(ROUTES.login), 400)
      },
    })
  },
})
