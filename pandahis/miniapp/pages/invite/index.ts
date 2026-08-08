import { hasToken, request } from '../../native-utils/api'
import { INVITE_SHARE_COVER_URL } from '../../native-utils/brand-assets'
import { ROUTES, buildUrl, navigateTo } from '../../native-utils/router'
import { promptInviteByCode } from '../../native-utils/share-invite'
import { computePageTopPadPx } from '../../native-utils/nav-metrics'

type InviteeDTO = {
  nickname?: string | null
  avatarUrl?: string | null
  registeredAt?: string | null
  rewardReads?: number | null
}

type InviteMe = {
  inviteCode: string
  readBalance: number
  invitedCount: number
  inviteRewardReads: number
  invitees?: InviteeDTO[]
}

type InviteeView = {
  key: string
  nickname: string
  avatarUrl: string
  initial: string
  registeredLabel: string
  rewardLabel: string
}

Page({
  data: {
    loading: false,
    loadError: false,
    inviteCode: '',
    invitedCount: 0,
    earnedReads: 0,
    inviteRewardReads: 100,
    canShare: false,
    invitees: [] as InviteeView[],
    pageTopPadPx: 88,
    showRules: false,
  },
  onLoad() {
    try {
      this.setData({ pageTopPadPx: computePageTopPadPx() })
    } catch {
      this.setData({ pageTopPadPx: 88 })
    }
  },
  onShow() {
    const tab = typeof this.getTabBar === 'function' ? this.getTabBar() : null
    if (tab && typeof (tab as WechatMiniprogram.IAnyObject).setSelected === 'function') {
      ;(tab as WechatMiniprogram.IAnyObject).setSelected(2)
    }
    try {
      wx.showShareMenu({
        withShareTicket: true,
        menus: ['shareAppMessage', 'shareTimeline'],
      })
    } catch {
      // ignore
    }
    if (!hasToken()) {
      this.setData({
        loading: false,
        loadError: false,
        inviteCode: '',
        invitedCount: 0,
        earnedReads: 0,
        canShare: false,
        invitees: [],
      })
      navigateTo(ROUTES.login, { from: 'invite' })
      return
    }
    void this.loadInviteMe()
  },
  noop() {},
  onRetryLoad() {
    void this.loadInviteMe()
  },
  onOpenRules() {
    this.setData({ showRules: true })
  },
  onCloseRules() {
    this.setData({ showRules: false })
  },
  onInviteFriends() {
    if (!this.data.inviteCode) {
      wx.showToast({ title: '邀请码加载中', icon: 'none' })
      return
    }
    promptInviteByCode(this.data.inviteCode)
  },
  formatRegisteredAt(iso?: string | null): string {
    if (!iso) return '—'
    const t = Date.parse(iso)
    if (Number.isNaN(t)) {
      const d = iso.slice(0, 10)
      return d || '—'
    }
    const date = new Date(t)
    const y = date.getFullYear()
    const m = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    return `${y}-${m}-${day}`
  },
  mapInvitees(list: InviteeDTO[] | undefined, fallbackReward: number): InviteeView[] {
    return (list || []).map((item, index) => {
      const nickname = (item.nickname || '').trim() || '好友'
      const reward =
        typeof item.rewardReads === 'number' ? item.rewardReads : fallbackReward
      return {
        key: `${item.registeredAt || ''}-${index}`,
        nickname,
        avatarUrl: (item.avatarUrl || '').trim(),
        initial: nickname.charAt(0) || '友',
        registeredLabel: this.formatRegisteredAt(item.registeredAt),
        rewardLabel: reward > 0 ? `+${reward}点` : '',
      }
    })
  },
  async loadInviteMe() {
    this.setData({ loading: true, loadError: false })
    try {
      const res = await request<InviteMe>('/invite/me', { auth: true })
      const d = res.data
      const inviteCode = d.inviteCode || ''
      const inviteRewardReads = d.inviteRewardReads ?? 100
      const invitedCount = d.invitedCount ?? 0
      // 邀请累计获得 ≈ 成功邀请数 × 单次奖励（与「余额」区分，避免消费后数字回落）
      const earnedReads = invitedCount * inviteRewardReads
      this.setData({
        inviteCode,
        invitedCount,
        earnedReads,
        inviteRewardReads,
        canShare: Boolean(inviteCode),
        invitees: this.mapInvitees(d.invitees, inviteRewardReads),
        loadError: false,
      })
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '加载失败'
      this.setData({ loadError: true, invitees: [] })
      wx.showToast({ title: msg, icon: 'none' })
    } finally {
      this.setData({ loading: false })
    }
  },
  onShareAppMessage() {
    const code = (this.data.inviteCode || '').trim()
    const path = code
      ? buildUrl(ROUTES.inviteAccept, { inviteCode: code })
      : ROUTES.inviteAccept
    return {
      title: '邀请你一起读历史图谱',
      path: path.startsWith('/') ? path : `/${path}`,
      imageUrl: INVITE_SHARE_COVER_URL,
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
