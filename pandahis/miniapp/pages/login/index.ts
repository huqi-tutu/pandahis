import {
  clearAccessToken,
  clearToken,
  getBaseUrl,
  hasToken,
  request,
  setToken,
  useLocalDevApi,
  useProductionApi,
} from '../../native-utils/api'
import { peekPendingInviteCode, stashInviteCode } from '../../native-utils/invite-storage'
import { formatApiRequestError } from '../../native-utils/load-error-message'
import { leaveAfterLogin, loginSuccessToast, loginWithWxCode } from '../../native-utils/wx-auth'
import { ROUTES } from '../../native-utils/router'
import { isDevtoolsClient } from '../../native-utils/runtime-env'

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
    agreed: false,
    devVisible: false,
    apiBase: '',
    guestTop: 0,
    guestHeight: 32,
  },
  _countdownTimer: null as ReturnType<typeof setInterval> | null,
  onLoad(query: Record<string, string | undefined>) {
    const reauth = query.reauth === '1' || query.reauth === 'true'
    if (reauth) {
      clearToken()
    }
    // 「立即体验」与右上角胶囊按钮上下居中对齐
    const rect = wx.getMenuButtonBoundingClientRect()
    this.setData({
      reauth,
      devVisible: isDevtoolsClient(),
      guestTop: rect.top,
      guestHeight: rect.height,
    })
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
      apiBase: getBaseUrl(),
    })
    if (hasToken() && !this.data.reauth) {
      void request('/me', { auth: true, softAuth: true })
        .then(() => leaveAfterLogin(0))
        .catch(() => {
          clearAccessToken()
          this.setData({ hasToken: false })
        })
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
  toggleAgree() {
    this.setData({ agreed: !this.data.agreed })
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
    useLocalDevApi()
    setToken('dev-local-token')
    this.setData({ apiBase: getBaseUrl() })
    wx.showToast({ title: '本机 API + dev Token', icon: 'success' })
    leaveAfterLogin()
  },
  useProdApi() {
    useProductionApi()
    this.setData({ apiBase: getBaseUrl() })
    wx.showToast({ title: '已切换生产 API', icon: 'success' })
  },
  useLocalApi() {
    useLocalDevApi()
    this.setData({ apiBase: getBaseUrl() })
    wx.showToast({ title: '已切换本机 API', icon: 'success' })
  },
  async loginWx() {
    if (this.data.loggingIn) return
    if (!this.data.agreed) {
      wx.showToast({ title: '请先勾选同意用户协议与隐私政策', icon: 'none' })
      return
    }
    this.setData({ loggingIn: true })
    try {
      const manual = (this.data.inviteCodeInput || peekPendingInviteCode() || '').trim()
      if (manual) stashInviteCode(manual)
      const data = await loginWithWxCode({ inviteCode: manual || undefined })
      this.setData({ reauth: false, hasToken: true })
      loginSuccessToast(data)
      leaveAfterLogin()
    } catch (e: unknown) {
      const msg = formatApiRequestError(e)
      wx.showModal({
        title: '登录失败',
        content: `${msg}\n\n当前接口：${getBaseUrl()}`,
        showCancel: false,
      })
    } finally {
      this.setData({ loggingIn: false })
    }
  },
})
