import {
  correctionSourceLabel,
  correctionStatusLabel,
  formatCorrectionTime,
} from '../../native-utils/correction'

function windowHeightPx(): number {
  try {
    const sys = wx.getSystemInfoSync()
    return sys.windowHeight || 667
  } catch {
    return 667
  }
}

Component({
  properties: {
    visible: {
      type: Boolean,
      value: false,
    },
    mode: {
      type: String,
      value: 'edit' as 'edit' | 'view',
    },
    civilizationName: {
      type: String,
      value: '',
    },
    dynastyName: {
      type: String,
      value: '',
    },
    boxTitle: {
      type: String,
      value: '',
    },
    selectedText: {
      type: String,
      value: '',
    },
    reason: {
      type: String,
      value: '',
    },
    status: {
      type: String,
      value: 'pending',
    },
    sourceType: {
      type: String,
      value: '',
    },
    submittedAt: {
      type: String,
      value: '',
    },
    submitting: {
      type: Boolean,
      value: false,
    },
    showViewSource: {
      type: Boolean,
      value: false,
    },
  },
  data: {
    draftReason: '',
    sourceLabel: '',
    statusLabel: '',
    reasonDisplay: '（未填写）',
    submittedAtDisplay: '',
    keyboardHeight: 0,
    cardMaxHeightPx: Math.floor(windowHeightPx() * 0.85),
    scrollIntoView: '',
  },
  observers: {
    'visible, mode, reason, status, sourceType, submittedAt': function syncFields(
      visible: boolean,
      mode: string,
      reason: string,
      status: string,
      sourceType: string,
      submittedAt: string
    ) {
      if (!visible) {
        this.setData({
          keyboardHeight: 0,
          cardMaxHeightPx: Math.floor(windowHeightPx() * 0.85),
          scrollIntoView: '',
        })
        return
      }
      const patch: Record<string, string> = {
        sourceLabel: correctionSourceLabel(sourceType),
        statusLabel: correctionStatusLabel(status),
        reasonDisplay: (reason || '').trim() || '（未填写）',
        submittedAtDisplay: formatCorrectionTime(submittedAt),
      }
      if (mode === 'edit') {
        patch.draftReason = (reason || '').slice(0, 500)
      }
      this.setData(patch)
    },
  },
  methods: {
    noop() {},
    onBackdropTap() {
      this.triggerEvent('close')
    },
    onClose() {
      this.triggerEvent('close')
    },
    onViewSource() {
      this.triggerEvent('viewsource')
    },
    onReasonInput(e: WechatMiniprogram.Input) {
      const value = String(e.detail.value || '').slice(0, 500)
      this.setData({ draftReason: value })
    },
    onReasonFocus() {
      this.setData({ scrollIntoView: 'correction-reason-field' })
    },
    onKeyboardHeightChange(e: WechatMiniprogram.TextareaKeyboardHeightChange) {
      const height = Math.max(0, Math.floor(Number(e.detail?.height) || 0))
      const winH = windowHeightPx()
      const maxH = height > 0 ? Math.max(280, winH - height - 12) : Math.floor(winH * 0.85)
      this.setData({
        keyboardHeight: height,
        cardMaxHeightPx: maxH,
        scrollIntoView: height > 0 ? 'correction-reason-field' : '',
      })
    },
    onSubmit() {
      if (this.properties.submitting) return
      this.triggerEvent('submit', { reason: this.data.draftReason.trim() })
    },
  },
})
