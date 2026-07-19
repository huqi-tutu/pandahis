import {
  correctionSourceLabel,
  correctionStatusLabel,
  formatCorrectionTime,
} from '../../native-utils/correction'

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
  },
  data: {
    draftReason: '',
    sourceLabel: '',
    statusLabel: '',
    reasonDisplay: '（未填写）',
    submittedAtDisplay: '',
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
      if (!visible) return
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
    onReasonInput(e: WechatMiniprogram.Input) {
      const value = String(e.detail.value || '').slice(0, 500)
      this.setData({ draftReason: value })
    },
    onSubmit() {
      if (this.properties.submitting) return
      this.triggerEvent('submit', { reason: this.data.draftReason.trim() })
    },
  },
})
