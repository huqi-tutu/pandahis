import { hasToken, request, uploadFile } from '../../native-utils/api'
import { formatApiRequestError } from '../../native-utils/load-error-message'
import { computePageTopPadPx } from '../../native-utils/nav-metrics'
import { ROUTES, navigateTo } from '../../native-utils/router'

type MeProfile = {
  nickname?: string
  avatarUrl?: string | null
  avatar_url?: string | null
}

Page({
  data: {
    nickname: '',
    avatarUrl: '',
    avatarInitial: '我',
    saving: false,
    avatarUploading: false,
    pageTopPadPx: 88,
    keyboardPadPx: 0,
  },
  onLoad() {
    try {
      this.setData({ pageTopPadPx: computePageTopPadPx() })
    } catch {
      this.setData({ pageTopPadPx: 88 })
    }
  },
  onShow() {
    if (!hasToken()) {
      navigateTo(ROUTES.login)
      return
    }
    void this.load()
  },
  async load() {
    try {
      const res = await request<MeProfile>('/me', { auth: true })
      const raw = res.data || {}
      const nickname = raw.nickname || ''
      const avatarUrl = raw.avatarUrl || raw.avatar_url || ''
      const initial = nickname ? String(nickname).charAt(0) : '我'
      this.setData({ nickname, avatarUrl, avatarInitial: initial })
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : ''
      console.error('[profile-edit] load failed', e)
      if (msg === 'UNAUTHORIZED') {
        navigateTo(ROUTES.login)
        return
      }
      wx.showModal({
        title: '加载资料失败',
        content: formatApiRequestError(e),
        showCancel: false,
      })
    }
  },
  onInput(e: WechatMiniprogram.Input) {
    const nickname = e.detail.value || ''
    this.setData({
      nickname,
      avatarInitial: nickname.trim() ? nickname.trim().charAt(0) : '我',
    })
  },
  onInputFocus() {
    // 自定义导航页上，额外留白确保输入框不被键盘挡住
  },
  onInputBlur() {
    this.setData({ keyboardPadPx: 0 })
  },
  onKeyboardHeightChange(e: WechatMiniprogram.InputKeyboardHeightChange) {
    const height = Math.max(0, Math.floor(Number(e.detail?.height) || 0))
    this.setData({ keyboardPadPx: height })
  },
  async onChooseAvatar(e: WechatMiniprogram.CustomEvent<{ avatarUrl: string }>) {
    if (this.data.avatarUploading) return
    const localPath = e.detail?.avatarUrl || ''
    if (!localPath) {
      wx.showToast({ title: '未获取到头像', icon: 'none' })
      return
    }
    const prevAvatarUrl = this.data.avatarUrl
    this.setData({ avatarUrl: localPath, avatarUploading: true })
    try {
      const res = await uploadFile<MeProfile>('/me/avatar', localPath, { name: 'file' })
      const nextUrl = res.data?.avatarUrl || res.data?.avatar_url || localPath
      this.setData({ avatarUrl: nextUrl })
      wx.showToast({ title: '头像已更新', icon: 'success' })
    } catch (err) {
      this.setData({ avatarUrl: prevAvatarUrl })
      const msg = err instanceof Error ? err.message : '上传失败'
      wx.showToast({
        title: msg.length > 18 ? `${msg.slice(0, 16)}…` : msg,
        icon: 'none',
      })
    } finally {
      this.setData({ avatarUploading: false })
    }
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
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '保存失败'
      wx.showToast({ title: msg.length > 18 ? `${msg.slice(0, 16)}…` : msg, icon: 'none' })
    } finally {
      this.setData({ saving: false })
    }
  },
})
