import { clearToken, hasToken, request } from '../../native-utils/api'
import { ROUTES, navigateTo } from '../../native-utils/router'
import { promptContentShareUnavailable } from '../../native-utils/share-invite'

const APP_VERSION = '1.0.0'

type MeDTO = {
  nickname: string
  avatarUrl?: string | null
  phoneMasked: string
  favoriteCount: number
  footprintCount: number
  learnDaysCount: number
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
    vipTitle: '开通年度会员',
    vipDesc: '解锁全地域图谱 · 跨时空评述 · 见证 Tab',
    appVersion: APP_VERSION,
    headerPadPx: 88,
  },
  onLoad() {
    // 与 proto-nav 一致：状态栏 + 88rpx 导航行（随屏宽换算 px）
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
    if (tab && typeof (tab as any).setSelected === 'function') (tab as any).setSelected(3)
    void this.refresh()
  },
  setGuestState() {
    this.setData({
      loggedIn: false,
      isVip: false,
      nickname: '',
      avatarUrl: '',
      avatarInitial: '我',
      phoneLine: '未绑定手机号',
      footprintCount: 0,
      favoriteCount: 0,
      learnDays: 0,
      vipTitle: '开通年度会员',
      vipDesc: '解锁全地域图谱 · 跨时空评述 · 见证 Tab',
    })
  },
  async refresh() {
    if (!hasToken()) {
      this.setGuestState()
      return
    }
    try {
      const [meRes, membership] = await Promise.all([
        request<MeDTO>('/me', { auth: true }),
        request<MembershipDTO>('/membership', { auth: true }).catch(() => null),
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
        vipTitle: vip.title,
        vipDesc: vip.desc,
      })
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : ''
      console.error('[my] refresh failed', e)
      if (msg === 'UNAUTHORIZED') {
        clearToken()
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
        vipTitle: vip.title,
        vipDesc: vip.desc,
      })
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
    wx.switchTab({ url: ROUTES.membership })
  },
  goFootprints() {
    this.requireLogin(() => navigateTo(ROUTES.footprints))
  },
  goFavorites() {
    this.requireLogin(() => navigateTo(ROUTES.favorites))
  },
  goSettings() {
    navigateTo(ROUTES.settings)
  },
  onShareFriend() {
    promptContentShareUnavailable()
  },
  goHelp() {
    const email = 'support@pandahis.com'
    wx.showModal({
      title: '帮助与反馈',
      content: `如有问题或建议，请发送邮件至：\n${email}`,
      confirmText: '复制邮箱',
      cancelText: '关闭',
      success: (r) => {
        if (!r.confirm) return
        wx.setClipboardData({
          data: email,
          success: () => wx.showToast({ title: '已复制邮箱', icon: 'success' }),
        })
      },
    })
  },
  goAbout() {
    navigateTo(ROUTES.about)
  },
  logout() {
    wx.showModal({
      title: '退出登录',
      content: '退出后需重新登录才能使用收藏、足迹与邀请功能。',
      confirmText: '退出',
      success: (r) => {
        if (!r.confirm) return
        clearToken()
        void this.refresh()
        wx.showToast({ title: '已退出', icon: 'success' })
      },
    })
  },
})
