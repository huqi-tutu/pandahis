const { hasToken, request, uploadFile } = require('../../native-utils/api')
const { ROUTES, navigateTo } = require('../../native-utils/router')

Page({
  data: {
    nickname: '',
    avatarUrl: '',
    avatarInitial: '我',
    saving: false,
    avatarUploading: false,
    headerPadPx: 88,
    keyboardPadPx: 0,
  },
  onLoad() {
    try {
      var sys = wx.getSystemInfoSync()
      var navPx = 88 * (sys.windowWidth / 750)
      this.setData({ headerPadPx: (sys.statusBarHeight || 20) + navPx })
    } catch (e) {
      this.setData({ headerPadPx: 88 })
    }
  },
  onShow() {
    if (!hasToken()) {
      navigateTo(ROUTES.login)
      return
    }
    this.load()
  },
  async load() {
    try {
      const res = await request('/me', { auth: true })
      const nickname = (res.data && res.data.nickname) || ''
      const avatarUrl = (res.data && (res.data.avatarUrl || res.data.avatar_url)) || ''
      const initial = nickname ? String(nickname).charAt(0) : '我'
      this.setData({ nickname, avatarUrl, avatarInitial: initial })
    } catch {
      wx.showToast({ title: '加载失败', icon: 'none' })
    }
  },
  onInput(e) {
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
  onKeyboardHeightChange(e) {
    const height = Math.max(0, Math.floor(Number(e.detail && e.detail.height) || 0))
    this.setData({ keyboardPadPx: height })
  },
  async onChooseAvatar(e) {
    if (this.data.avatarUploading) return
    const localPath = (e.detail && e.detail.avatarUrl) || ''
    if (!localPath) {
      wx.showToast({ title: '未获取到头像', icon: 'none' })
      return
    }
    const prevAvatarUrl = this.data.avatarUrl
    this.setData({ avatarUrl: localPath, avatarUploading: true })
    try {
      const res = await uploadFile('/me/avatar', localPath, { name: 'file' })
      const nextUrl =
        (res.data && (res.data.avatarUrl || res.data.avatar_url)) || localPath
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
    } catch (e) {
      const msg = e instanceof Error ? e.message : '保存失败'
      wx.showToast({ title: msg.length > 18 ? `${msg.slice(0, 16)}…` : msg, icon: 'none' })
    } finally {
      this.setData({ saving: false })
    }
  },
})
