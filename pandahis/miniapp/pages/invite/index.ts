import { hasToken, request } from '../../native-utils/api'
import { ROUTES, buildUrl, navigateTo } from '../../native-utils/router'
import { bindInviteCode } from '../../native-utils/invite-bind'
import { copyText, promptInviteByCode } from '../../native-utils/share-invite'

type InviteMe = {
  inviteCode: string
  readBalance: number
  invitedCount: number
  inviteRewardReads: number
}

Page({
  data: {
    hasToken: false,
    loading: false,
    inviteCode: '',
    readBalance: 0,
    invitedCount: 0,
    inviteRewardReads: 10,
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
    const tab = typeof this.getTabBar === 'function' ? this.getTabBar() : null
    if (tab && typeof (tab as any).setSelected === 'function') (tab as any).setSelected(2)
    const loggedIn = hasToken()
    this.setData({ hasToken: loggedIn })
    if (loggedIn) {
      void this.loadInviteMe()
    } else {
      this.setData({
        loading: false,
        inviteCode: '',
        readBalance: 0,
        invitedCount: 0,
      })
    }
  },
  onInviteFriends() {
    if (this.data.loading || !this.data.inviteCode) return
    promptInviteByCode(this.data.inviteCode)
  },
  goLogin() {
    navigateTo(ROUTES.login)
  },
  goHome() {
    wx.switchTab({ url: ROUTES.home })
  },
  async loadInviteMe() {
    this.setData({ loading: true })
    try {
      const res = await request<InviteMe>('/invite/me', { auth: true })
      const d = res.data
      this.setData({
        inviteCode: d.inviteCode || '',
        readBalance: d.readBalance ?? 0,
        invitedCount: d.invitedCount ?? 0,
        inviteRewardReads: d.inviteRewardReads ?? 10,
      })
    } catch (e: any) {
      wx.showToast({ title: e?.message || '加载失败', icon: 'none' })
    } finally {
      this.setData({ loading: false })
    }
  },
  onBindInput(e: WechatMiniprogram.Input) {
    this.setData({ bindCode: (e.detail.value || '').toUpperCase() })
  },
  async submitBindCode() {
    if (this.data.bindSubmitting) return
    const code = (this.data.bindCode || '').trim()
    if (!code) {
      wx.showToast({ title: '请输入好友邀请码', icon: 'none' })
      return
    }
    this.setData({ bindSubmitting: true })
    try {
      const res = await bindInviteCode(code)
      wx.showToast({
        title: res.message || (res.bound ? '绑定成功' : '绑定失败'),
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
  copyCode() {
    if (this.data.loading) return
    const c = this.data.inviteCode
    if (!c) return
    void copyText(c).then(() => wx.showToast({ title: '已复制', icon: 'none' }))
  },
  onShareAppMessage() {
    const code = (this.data.inviteCode || '').trim()
    const path = code
      ? buildUrl(ROUTES.inviteAccept, { inviteCode: code })
      : ROUTES.inviteAccept
    return {
      title: '邀请你一起读历史图谱',
      path: path.startsWith('/') ? path : `/${path}`,
    }
  },
  onShareTimeline() {
    const code = (this.data.inviteCode || '').trim()
    return {
      title: '历史图谱 · 邀请你一起读',
      ...(code ? { query: `inviteCode=${encodeURIComponent(code)}` } : {}),
    }
  },
})
