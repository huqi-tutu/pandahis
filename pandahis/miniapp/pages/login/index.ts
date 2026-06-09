import { clearToken, hasToken, setToken } from '../../native-utils/api'
import { peekPendingInviteCode, stashInviteCode } from '../../native-utils/invite-storage'
import { leaveAfterLogin, loginSuccessToast, loginWithWxCode } from '../../native-utils/wx-auth'
import { ROUTES } from '../../native-utils/router'

Page({
  data: {
    loggingIn: false,
    pendingInvite: '',
    inviteCodeInput: '',
    hasToken: false,
    reauth: false,
    phone: '',
    code: '',
    countdown: 0,
  },
  _countdownTimer: null as ReturnType<typeof setInterval> | null,
  onLoad(query: Record<string, string | undefined>) {
    const reauth = query.reauth === '1' || query.reauth === 'true'
    if (reauth) {
      clearToken()
    }
    this.setData({ reauth })
  },
  onUnload() {
    if (this._countdownTimer) clearInterval(this._countdownTimer)
  },
  onInviteCodeInput(e: WechatMiniprogram.Input) {
    const v = (e.detail.value || '').trim().toUpperCase()
    this.setData({ inviteCodeInput: v })
    if (v) stashInviteCode(v)
  },
  onPhoneInput(e: WechatMiniprogram.Input) {
    this.setData({ phone: (e.detail.value || '').trim() })
  },
  onCodeInput(e: WechatMiniprogram.Input) {
    this.setData({ code: (e.detail.value || '').trim() })
  },
  onShow() {
    const pendingInvite = peekPendingInviteCode()
    this.setData({
      pendingInvite,
      inviteCodeInput: pendingInvite || '',
      hasToken: hasToken(),
    })
    if (hasToken()) {
      leaveAfterLogin(0)
    }
  },
  sendCode() {
    if (this.data.countdown > 0) return
    const phone = (this.data.phone || '').trim()
    if (!/^1\d{10}$/.test(phone)) {
      wx.showToast({ title: '请输入有效手机号', icon: 'none' })
      return
    }
    wx.showToast({ title: '短信登录暂未开放', icon: 'none' })
  },
  loginByPhone() {
    wx.showToast({ title: '手机号登录暂未开放', icon: 'none' })
  },
  guestBrowse() {
    wx.switchTab({ url: ROUTES.home })
  },
  openAgreement() {
    wx.showModal({
      title: '用户服务协议',
      content: '完整协议页面即将上线，登录即表示您同意平台服务条款。',
      showCancel: false,
    })
  },
  openPrivacy() {
    wx.showModal({
      title: '隐私政策',
      content: '完整隐私政策页面即将上线，我们重视您的个人信息保护。',
      showCancel: false,
    })
  },
  loginDev() {
    setToken('dev-local-token')
    wx.showToast({ title: '已写入 Token', icon: 'success' })
    leaveAfterLogin()
  },
  async loginWx() {
    if (this.data.loggingIn) return
    this.setData({ loggingIn: true })
    try {
      const manual = (this.data.inviteCodeInput || peekPendingInviteCode() || '').trim()
      if (manual) stashInviteCode(manual)
      const data = await loginWithWxCode({ inviteCode: manual || undefined })
      this.setData({ reauth: false, hasToken: true })
      loginSuccessToast(data)
      leaveAfterLogin()
    } catch (e: any) {
      const msg = typeof e?.message === 'string' ? e.message : '登录失败'
      wx.showToast({ title: msg.length > 20 ? msg.slice(0, 20) + '…' : msg, icon: 'none' })
    } finally {
      this.setData({ loggingIn: false })
    }
  },
})
