import { hasToken } from '../../native-utils/api'
import {
  FEEDBACK_CONTENT_MAX,
  FEEDBACK_DAILY_LIMIT,
  FEEDBACK_IMAGE_MAX,
  FEEDBACK_TYPES,
  FeedbackType,
  submitFeedback,
  uploadFeedbackImage,
} from '../../native-utils/feedback'
import { computePageTopPadPx } from '../../native-utils/nav-metrics'
import { ROUTES, navigateTo, redirectTo } from '../../native-utils/router'

type LocalImage = {
  localPath: string
  remoteUrl?: string
}

Page({
  data: {
    pageTopPadPx: 88,
    keyboardPadPx: 0,
    typeOptions: FEEDBACK_TYPES.map((x) => ({ ...x })),
    feedbackType: 'feature' as FeedbackType,
    content: '',
    contentLength: 0,
    contentMax: FEEDBACK_CONTENT_MAX,
    images: [] as LocalImage[],
    imageMax: FEEDBACK_IMAGE_MAX,
    dailyLimit: FEEDBACK_DAILY_LIMIT,
    canSubmit: false,
    submitting: false,
  },
  onLoad() {
    try {
      this.setData({ pageTopPadPx: computePageTopPadPx() })
    } catch {
      this.setData({ pageTopPadPx: 88 })
    }
    this.ensureLogin({ replace: true })
  },
  onShow() {
    this.ensureLogin({ replace: false })
  },
  ensureLogin(opts: { replace: boolean }) {
    if (hasToken()) return true
    wx.showModal({
      title: '需要登录',
      content: '登录后可提交帮助与反馈。',
      showCancel: false,
      success: () => {
        if (opts.replace) redirectTo(ROUTES.login)
        else navigateTo(ROUTES.login)
      },
    })
    return false
  },
  onTypeTap(e: WechatMiniprogram.BaseEvent) {
    const value = String((e.currentTarget as WechatMiniprogram.IAnyObject).dataset.value || '') as FeedbackType
    if (!value || value === this.data.feedbackType) return
    this.setData({ feedbackType: value })
  },
  onContentInput(e: WechatMiniprogram.Input) {
    const content = String(e.detail.value || '')
    this.setData({
      content,
      contentLength: content.length,
      canSubmit: content.trim().length > 0 && !this.data.submitting,
    })
  },
  onPickImages() {
    if (!this.ensureLogin({ replace: false })) return
    const remain = FEEDBACK_IMAGE_MAX - this.data.images.length
    if (remain <= 0) return
    wx.chooseMedia({
      count: remain,
      mediaType: ['image'],
      sourceType: ['album'],
      sizeType: ['compressed'],
      success: (res) => {
        const picked = (res.tempFiles || [])
          .map((f) => f.tempFilePath)
          .filter(Boolean)
          .map((localPath) => ({ localPath }))
        if (!picked.length) return
        this.setData({ images: [...this.data.images, ...picked].slice(0, FEEDBACK_IMAGE_MAX) })
      },
    })
  },
  onRemoveImage(e: WechatMiniprogram.BaseEvent) {
    const index = Number((e.currentTarget as WechatMiniprogram.IAnyObject).dataset.index)
    if (!Number.isFinite(index)) return
    const images = this.data.images.filter((_, i) => i !== index)
    this.setData({ images })
  },
  onPreview(e: WechatMiniprogram.BaseEvent) {
    const index = Number((e.currentTarget as WechatMiniprogram.IAnyObject).dataset.index)
    const urls = this.data.images.map((x) => x.localPath)
    if (!urls.length) return
    wx.previewImage({
      current: urls[index] || urls[0],
      urls,
    })
  },
  async onSubmit() {
    if (this.data.submitting) return
    if (!this.ensureLogin({ replace: false })) return
    const content = (this.data.content || '').trim()
    if (!content) {
      wx.showToast({ title: '请填写问题描述', icon: 'none' })
      return
    }
    if (content.length > FEEDBACK_CONTENT_MAX) {
      wx.showToast({ title: `最多 ${FEEDBACK_CONTENT_MAX} 字`, icon: 'none' })
      return
    }

    this.setData({ submitting: true, canSubmit: false })
    wx.showLoading({ title: '提交中', mask: true })
    try {
      const images = [...this.data.images]
      const imageUrls: string[] = []
      for (let i = 0; i < images.length; i += 1) {
        const img = images[i]
        if (img.remoteUrl) {
          imageUrls.push(img.remoteUrl)
          continue
        }
        const url = await uploadFeedbackImage(img.localPath)
        images[i] = { ...img, remoteUrl: url }
        this.setData({ images: [...images] })
        imageUrls.push(url)
      }
      await submitFeedback({
        feedbackType: this.data.feedbackType,
        content,
        imageUrls,
      })
      wx.hideLoading()
      wx.showToast({ title: '已提交', icon: 'success' })
      setTimeout(() => wx.navigateBack({ fail: () => navigateTo(ROUTES.settings) }), 500)
    } catch (err: unknown) {
      wx.hideLoading()
      const msg = err instanceof Error ? err.message : '提交失败'
      wx.showToast({
        title: msg.length > 20 ? `${msg.slice(0, 18)}…` : msg,
        icon: 'none',
      })
    } finally {
      this.setData({
        submitting: false,
        canSubmit: (this.data.content || '').trim().length > 0,
      })
    }
  },
})
