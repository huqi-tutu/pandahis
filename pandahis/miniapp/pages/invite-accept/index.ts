import { hasToken } from '../../native-utils/api'
import { bindInviteCode } from '../../native-utils/invite-bind'
import {
  peekPendingInviteCode,
  stashInviteCode,
  stashInviteCodeFromQuery,
  stashInviteFromLaunchOptions,
} from '../../native-utils/invite-storage'
import { ROUTES, navigateTo } from '../../native-utils/router'
import { loginSuccessToast, loginWithWxCode } from '../../native-utils/wx-auth'

Page({
  data: {
    hasPendingInvite: false,
    loggingIn: false,
    inviteCodeInput: '',
  },
  onLoad(query: Record<string, string | undefined>) {
    stashInviteCodeFromQuery(query)
    try {
      const launch = wx.getLaunchOptionsSync?.()
      if (launch) stashInviteFromLaunchOptions(launch)
    } catch {
      // ignore
    }
    const pending = peekPendingInviteCode()
    this.setData({
      hasPendingInvite: Boolean(pending),
      inviteCodeInput: pending || '',
    })
  },
  onInviteCodeInput(e: WechatMiniprogram.Input) {
    const v = (e.detail.value || '').trim().toUpperCase()
    this.setData({ inviteCodeInput: v, hasPendingInvite: Boolean(v) })
    if (v) stashInviteCode(v)
  },
  async onShow() {
    const pending = peekPendingInviteCode()
    this.setData({
      hasPendingInvite: Boolean(pending),
      inviteCodeInput: pending || this.data.inviteCodeInput || '',
    })
    if (hasToken()) {
      const manual = (this.data.inviteCodeInput || '').trim()
      if (manual) {
        try {
          const res = await bindInviteCode(manual)
          if (res.bound) {
            wx.showToast({ title: '邀请已绑定', icon: 'success' })
          }
        } catch {
          // 已绑定过等情况静默，仍进入首页
        }
      }
      wx.switchTab({ url: ROUTES.home })
    }
  },
  goLogin() {
    navigateTo(ROUTES.login)
  },
  async loginHere() {
    if (this.data.loggingIn) return
    this.setData({ loggingIn: true })
    try {
      const manual = (this.data.inviteCodeInput || peekPendingInviteCode() || '').trim()
      if (manual) stashInviteCode(manual)
      const data = await loginWithWxCode({ inviteCode: manual || undefined })
      loginSuccessToast(data)
      setTimeout(() => wx.switchTab({ url: ROUTES.home }), 500)
    } catch (e: any) {
      const msg = typeof e?.message === 'string' ? e.message : '登录失败'
      wx.showToast({ title: msg.length > 20 ? msg.slice(0, 20) + '…' : msg, icon: 'none' })
    } finally {
      this.setData({ loggingIn: false })
    }
  },
  goHome() {
    wx.switchTab({ url: ROUTES.home })
  },
})
