import { hasToken, request } from '../../native-utils/api'
import { ROUTES, buildUrl, navigateTo } from '../../native-utils/router'
import { promptInviteByCode } from '../../native-utils/share-invite'

type AssistParticipant = { nickname: string; avatarUrl?: string | null }

type AssistDTO = {
  targetCount: number
  currentCount: number
  completed: boolean
  rewardClaimed: boolean
  rewardPlanName: string
  rewardDurationDays: number
  membershipEndAt?: string | null
  assistDeadlineAt?: string | null
  participants: AssistParticipant[]
}

type InviteMe = { inviteCode: string }

type Slot = {
  filled: boolean
  label: string
  avatarUrl: string
}

Page({
  data: {
    targetCount: 4,
    currentCount: 0,
    completed: false,
    rewardClaimed: false,
    durationDays: 90,
    endDateLabel: '',
    deadlineLabel: '',
    assistExpired: false,
    slots: [] as Slot[],
    inviteCode: '',
    canShare: true,
  },
  onShow() {
    if (!hasToken()) {
      navigateTo(ROUTES.login)
      return
    }
    void this.load()
  },
  onInviteFriends() {
    if (!this.data.inviteCode) {
      wx.showToast({ title: '邀请码加载中', icon: 'none' })
      return
    }
    promptInviteByCode(this.data.inviteCode, { title: '好友助力' })
  },
  async load() {
    try {
      const [assistRes, inviteRes] = await Promise.all([
        request<AssistDTO>('/membership/assist', { auth: true }),
        request<InviteMe>('/invite/me', { auth: true }).catch(() => null),
      ])
      const a = assistRes.data
      const inviteCode = inviteRes?.data?.inviteCode || ''
      const participants = a.participants || []
      const endDateLabel = this.formatEndDate(a.membershipEndAt)
      const deadlineLabel = this.formatEndDate(a.assistDeadlineAt)
      const assistExpired = this.isExpired(a.assistDeadlineAt) && !a.rewardClaimed
      const slots = this.buildSlots(a.targetCount, participants, a.rewardClaimed ? a.targetCount : a.currentCount)
      this.setData({
        targetCount: a.targetCount,
        currentCount: a.rewardClaimed ? a.targetCount : a.currentCount,
        completed: a.completed,
        rewardClaimed: a.rewardClaimed,
        durationDays: a.rewardDurationDays || 90,
        endDateLabel,
        deadlineLabel,
        assistExpired,
        slots,
        inviteCode,
        canShare: Boolean(inviteCode),
      })
      if (a.completed && !a.rewardClaimed && !assistExpired) {
        void this.tryClaim()
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '加载失败'
      wx.showToast({ title: msg, icon: 'none' })
    }
  },
  buildSlots(target: number, participants: AssistParticipant[], filledCount: number): Slot[] {
    const slots: Slot[] = []
    for (let i = 0; i < target; i++) {
      const filled = i < filledCount
      const p = participants[i]
      if (filled && p) {
        const name = (p.nickname || '').trim()
        slots.push({
          filled: true,
          label: name ? name.charAt(0) : '友',
          avatarUrl: (p.avatarUrl || '').trim(),
        })
      } else if (filled) {
        slots.push({ filled: true, label: '友', avatarUrl: '' })
      } else {
        slots.push({ filled: false, label: '', avatarUrl: '' })
      }
    }
    return slots
  },
  isExpired(iso?: string | null): boolean {
    if (!iso) return false
    const t = Date.parse(iso)
    return !Number.isNaN(t) && t < Date.now()
  },
  formatEndDate(iso?: string | null): string {
    if (!iso) return ''
    const d = iso.slice(0, 10)
    const parts = d.split('-')
    if (parts.length === 3) return `${parts[0]}-${Number(parts[1])}-${Number(parts[2])}`
    return d
  },
  async tryClaim() {
    try {
      const res = await request<AssistDTO>('/membership/assist/claim', {
        method: 'POST',
        auth: true,
      })
      const a = res.data
      const participants = a.participants || []
      this.setData({
        rewardClaimed: a.rewardClaimed,
        endDateLabel: this.formatEndDate(a.membershipEndAt),
        completed: true,
        currentCount: a.targetCount,
        slots: this.buildSlots(a.targetCount, participants, a.targetCount),
      })
      wx.showToast({ title: '季度会员已开通', icon: 'success' })
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : ''
      if (msg.includes('expired')) {
        this.setData({ assistExpired: true })
        wx.showToast({ title: '助力活动已过期', icon: 'none' })
        return
      }
      if (!msg.includes('not completed') && !msg.includes('已完成')) {
        wx.showToast({ title: msg || '领取失败', icon: 'none' })
      }
    }
  },
  onShareAppMessage() {
    const code = (this.data.inviteCode || '').trim()
    const path = code
      ? buildUrl(ROUTES.inviteAccept, { inviteCode: code })
      : ROUTES.inviteAccept
    return {
      title: '帮我助力，一起读历史图谱',
      path: path.startsWith('/') ? path : `/${path}`,
    }
  },
  onShareTimeline() {
    const code = (this.data.inviteCode || '').trim()
    return {
      title: '历史图谱 · 邀你助力领会员',
      ...(code ? { query: `inviteCode=${encodeURIComponent(code)}` } : {}),
    }
  },
})
