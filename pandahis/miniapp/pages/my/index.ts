import { clearAccessToken, hasToken, request } from '../../native-utils/api'
import { ROUTES, navigateTo } from '../../native-utils/router'
import { computePageHeightPx, computePageTopPadPx } from '../../native-utils/nav-metrics'
import { measureScrollOverflow } from '../../native-utils/overscroll-bounce'
import { trySilentWxLogin } from '../../native-utils/wx-auth'

const APP_VERSION = '1.0.0'

type MeDTO = {
  nickname: string
  avatarUrl?: string | null
  phoneMasked: string
  favoriteCount: number
  footprintCount: number
  learnDaysCount: number
  readCompleteCount: number
  membershipStatus: string
  membershipEndAt?: string | null
}

type MembershipDTO = {
  status: string
  endAt?: string | null
}

/** 兼容 camelCase / snake_case 的 /me 响应 */
function normalizeMe(raw: Record<string, unknown>): MeDTO {
  return {
    nickname: String(raw.nickname ?? raw['nickname'] ?? ''),
    avatarUrl: (raw.avatarUrl ?? raw['avatar_url'] ?? null) as string | null,
    phoneMasked: String(raw.phoneMasked ?? raw['phone_masked'] ?? ''),
    favoriteCount: Number(raw.favoriteCount ?? raw['favorite_count'] ?? 0),
    footprintCount: Number(raw.footprintCount ?? raw['footprint_count'] ?? 0),
    learnDaysCount: Number(raw.learnDaysCount ?? raw['learn_days_count'] ?? 0),
    readCompleteCount: Number(raw.readCompleteCount ?? raw['read_complete_count'] ?? 0),
    membershipStatus: String(raw.membershipStatus ?? raw['membership_status'] ?? 'NONE'),
    membershipEndAt: (raw.membershipEndAt ?? raw['membership_end_at'] ?? null) as string | null,
  }
}

Page({
  data: {
    loggedIn: false,
    isVip: false,
    nickname: '',
    avatarUrl: '',
    avatarInitial: '我',
    phoneLine: '未绑定手机号',
    footprintCount: 0,
    favoriteCount: 0,
    learnDays: 0,
    readCompleteCount: 0,
    vipTitle: '开通年度会员',
    vipDesc: '解锁全地域图谱 · 跨时空评述 · 见证 Tab',
    appVersion: APP_VERSION,
    pageTopPadPx: 88,
    pageHeightPx: 667,
    scrollEnabled: false,
    shortcuts: [
      // 会员入口二期再开放；一期保留页码与后端能力
      { id: 'notes', label: '笔记', icon: '/images/icons/biji.png', action: 'notes' },
      { id: 'corrections', label: '纠错', icon: '/images/icons/jiucuo.png', action: 'corrections' },
      { id: 'invite', label: '邀请', icon: '/images/icons/fenxiang.png', action: 'invite' },
      { id: 'settings', label: '设置', icon: '/images/icons/shezhi.png', action: 'settings' },
    ],
  },
  onLoad() {
    try {
      const sys = wx.getSystemInfoSync()
      this.setData({
        pageTopPadPx: computePageTopPadPx(sys),
        pageHeightPx: computePageHeightPx(sys),
      })
    } catch {
      this.setData({ pageTopPadPx: 88, pageHeightPx: 667 })
    }
  },
  onReady() {
    this.scheduleScrollMeasure()
  },
  scheduleScrollMeasure() {
    wx.nextTick(() => {
      void this.updateScrollEnabled()
      setTimeout(() => void this.updateScrollEnabled(), 120)
    })
  },
  async updateScrollEnabled() {
    const scrollEnabled = await measureScrollOverflow(this, '#pageMyScroll', '#pageMyContent')
    if (scrollEnabled !== this.data.scrollEnabled) {
      this.setData({ scrollEnabled })
    }
  },
  onShow() {
    const tab = typeof this.getTabBar === 'function' ? this.getTabBar() : null
    if (tab && typeof (tab as any).setSelected === 'function') (tab as any).setSelected(3)
    void this.refresh()
  },
  setGuestState() {
    this.setData(
      {
        loggedIn: false,
        isVip: false,
        nickname: '',
        avatarUrl: '',
        avatarInitial: '我',
        phoneLine: '未绑定手机号',
        footprintCount: 0,
        favoriteCount: 0,
        learnDays: 0,
        readCompleteCount: 0,
        vipTitle: '开通年度会员',
        vipDesc: '解锁全地域图谱 · 跨时空评述 · 见证 Tab',
      },
      () => this.scheduleScrollMeasure(),
    )
  },
  async refresh() {
    if (!hasToken()) {
      this.setGuestState()
      return
    }
    try {
      const [meRes, membership] = await Promise.all([
        request<MeDTO>('/me', { auth: true }),
        request<MembershipDTO>('/membership', { auth: true, softAuth: true }).catch(() => null),
      ])
      const me = normalizeMe((meRes.data || {}) as Record<string, unknown>)
      const phone =
        me.phoneMasked && me.phoneMasked !== 'null' ? me.phoneMasked : ''
      const initial = (me.nickname || '我').trim().charAt(0) || '我'
      const ms = membership?.data?.status || me.membershipStatus || 'NONE'
      const endAt = membership?.data?.endAt || me.membershipEndAt
      const isVip = String(ms).toUpperCase() === 'ACTIVE'
      const vip = this.vipCopy(ms, endAt)
      this.setData({
        loggedIn: true,
        isVip,
        nickname: me.nickname || '用户',
        avatarUrl: me.avatarUrl || '',
        avatarInitial: initial,
        phoneLine: phone || '未绑定手机号',
        footprintCount: me.footprintCount,
        favoriteCount: me.favoriteCount,
        learnDays: me.learnDaysCount,
        readCompleteCount: me.readCompleteCount,
        vipTitle: vip.title,
        vipDesc: vip.desc,
      }, () => this.scheduleScrollMeasure())
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : ''
      console.error('[my] refresh failed', e)
      if (msg === 'UNAUTHORIZED') {
        clearAccessToken()
        const relogged = await trySilentWxLogin()
        if (relogged) {
          return this.refresh()
        }
        this.setGuestState()
        return
      }
      const vip = this.vipCopy('NONE', null)
      this.setData({
        loggedIn: true,
        isVip: false,
        nickname: '用户',
        avatarUrl: '',
        avatarInitial: '我',
        phoneLine: '未绑定手机号',
        footprintCount: 0,
        favoriteCount: 0,
        learnDays: 0,
        readCompleteCount: 0,
        vipTitle: vip.title,
        vipDesc: vip.desc,
      }, () => this.scheduleScrollMeasure())
    }
  },
  vipCopy(status: string, endAt?: string | null) {
    const st = String(status || '').toUpperCase()
    const endStr = endAt == null ? '' : String(endAt)
    if (st === 'ACTIVE' && endStr) {
      const d = endStr.slice(0, 10)
      const daysLeft = Math.max(
        0,
        Math.ceil((Date.parse(endStr) - Date.now()) / (24 * 60 * 60 * 1000))
      )
      const tier = daysLeft > 0 && daysLeft <= 120 ? '季度' : '典藏'
      return {
        title: `${tier}会员已开通`,
        desc: `有效期至 ${d} · 评述 / 见证 / 原文免扣阅读点`,
      }
    }
    return {
      title: '开通典藏会员',
      desc: '邀友助力免费季卡 · 或付费订阅 · 深度阅读免扣点',
    }
  },
  requireLogin(action: () => void) {
    if (!hasToken()) {
      this.goLogin()
      return
    }
    action()
  },
  goLogin() {
    navigateTo(ROUTES.login, { reauth: '1' })
  },
  onEditProfile() {
    this.requireLogin(() => navigateTo(ROUTES.profileEdit))
  },
  goMembership() {
    // 二期：会员页保留，当前非 Tab，用 navigateTo
    navigateTo(ROUTES.membership)
  },
  goFootprints() {
    this.requireLogin(() => navigateTo(ROUTES.footprints))
  },
  goReadCompleted() {
    this.requireLogin(() => navigateTo(ROUTES.readCompleted))
  },
  goFavorites() {
    this.requireLogin(() => navigateTo(ROUTES.favorites))
  },
  goNotes() {
    this.requireLogin(() => navigateTo(ROUTES.notes))
  },
  goCorrections() {
    this.requireLogin(() => navigateTo(ROUTES.corrections))
  },
  goInviteFriends() {
    if (!hasToken()) {
      navigateTo(ROUTES.login, { from: 'invite' })
      return
    }
    wx.switchTab({
      url: ROUTES.invite,
      fail(err) {
        console.error('[my] goInviteFriends failed', err)
        wx.showToast({ title: '页面打开失败', icon: 'none' })
      },
    })
  },
  goSettings() {
    navigateTo(ROUTES.settings)
  },
  onShortcutTap(e: WechatMiniprogram.BaseEvent) {
    const action = (e.currentTarget as WechatMiniprogram.IAnyObject).dataset.action as string
    switch (action) {
      case 'membership':
        this.goMembership()
        break
      case 'notes':
        this.goNotes()
        break
      case 'corrections':
        this.goCorrections()
        break
      case 'invite':
        this.goInviteFriends()
        break
      case 'settings':
        this.goSettings()
        break
      default:
        break
    }
  },
})
