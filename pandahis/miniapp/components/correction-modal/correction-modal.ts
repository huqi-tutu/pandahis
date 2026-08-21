import {
  correctionSourceLabel,
  correctionStatusLabel,
  formatCorrectionTime,
} from '../../native-utils/correction'
import {
  composerSheetViewModel,
  formatSheetCoordinate,
  readComposerSheetMetrics,
} from '../../native-utils/composer-sheet-layout'

type SheetOverride = {
  keyboardHeight?: number
  quoteExpanded?: boolean
  restWindowHeight?: number
  mode?: string
  selectedText?: string
}

function sheetPatch(
  component: { properties: Record<string, any>; data: Record<string, any> },
  override: SheetOverride = {},
) {
  const metrics = readComposerSheetMetrics()
  const quoteExpanded = override.quoteExpanded ?? Boolean(component.data.quoteExpanded)
  const restWindowHeight =
    override.restWindowHeight ||
    Number(component.data.restWindowHeight) ||
    metrics.windowHeight
  const vm = composerSheetViewModel({
    ...metrics,
    keyboardHeight:
      override.keyboardHeight ?? (Math.max(0, Number(component.data.keyboardHeight) || 0)),
    restWindowHeight,
    mode: String(override.mode ?? (component.properties.mode || 'edit')),
    selectedText: String(override.selectedText ?? (component.properties.selectedText || '')),
    quoteExpanded,
  })
  return {
    ...vm,
    quoteExpanded,
    restWindowHeight,
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
    keyboardOpen: false,
    keyboardLiftPx: 0,
    restWindowHeight: 0,
    cardStyle: '',
    bodyStyle: '',
    textareaHeightPx: 110,
    quoteExpanded: false,
    quoteMaxLines: 0,
    quoteClampClass: '',
    quoteClampStyle: '',
    showQuoteToggle: false,
    quoteToggleLabel: '展开',
    sheetOpen: false,
    coordinateText: '',
  },
  lifetimes: {
    attached() {
      this._onKeyboardHeight = (res: { height?: number }) => {
        if (!this.properties.visible) return
        const height = Math.max(0, Math.floor(Number(res?.height) || 0))
        this.setData(sheetPatch(this, { keyboardHeight: height }))
      }
      if (typeof wx.onKeyboardHeightChange === 'function') {
        wx.onKeyboardHeightChange(this._onKeyboardHeight)
      }
    },
    detached() {
      if (this._onKeyboardHeight && typeof wx.offKeyboardHeightChange === 'function') {
        wx.offKeyboardHeightChange(this._onKeyboardHeight)
      }
    },
  },
  observers: {
    'visible, mode, reason, status, sourceType, submittedAt, selectedText, civilizationName, dynastyName, boxTitle': function syncFields(
      visible: boolean,
      mode: string,
      reason: string,
      status: string,
      sourceType: string,
      submittedAt: string,
      selectedText: string,
      civilizationName: string,
      dynastyName: string,
      boxTitle: string
    ) {
      const metrics = readComposerSheetMetrics()
      const coordinateText = formatSheetCoordinate(civilizationName, dynastyName, boxTitle)
      if (!visible) {
        this.setData({
          sourceLabel: correctionSourceLabel(sourceType),
          statusLabel: correctionStatusLabel(status),
          reasonDisplay: (reason || '').trim() || '（未填写）',
          submittedAtDisplay: formatCorrectionTime(submittedAt),
          coordinateText,
          sheetOpen: false,
          ...sheetPatch(this, {
            keyboardHeight: 0,
            quoteExpanded: false,
            restWindowHeight: metrics.windowHeight,
            mode,
            selectedText,
          }),
        })
        return
      }
      const opening = !this.data.sheetOpen
      const patch: Record<string, unknown> = {
        sourceLabel: correctionSourceLabel(sourceType),
        statusLabel: correctionStatusLabel(status),
        reasonDisplay: (reason || '').trim() || '（未填写）',
        submittedAtDisplay: formatCorrectionTime(submittedAt),
        coordinateText,
        sheetOpen: true,
        ...sheetPatch(this, {
          keyboardHeight: opening ? 0 : this.data.keyboardHeight,
          quoteExpanded: opening ? false : this.data.quoteExpanded,
          restWindowHeight: opening ? metrics.windowHeight : this.data.restWindowHeight,
          mode,
          selectedText,
        }),
      }
      if (mode === 'edit') {
        patch.draftReason = (reason || '').slice(0, 500)
      }
      this.setData(patch)
    },
  },
  methods: {
    noop() {},
    hideKeyboard() {
      if (!this.data.keyboardOpen) return
      if (typeof wx.hideKeyboard === 'function') wx.hideKeyboard()
    },
    onSheetTap() {
      this.hideKeyboard()
    },
    onBackdropTap() {
      if (this.data.keyboardOpen) {
        this.hideKeyboard()
        return
      }
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
    onToggleQuote() {
      if (this.data.keyboardOpen) return
      this.setData(sheetPatch(this, { quoteExpanded: !this.data.quoteExpanded }))
    },
    onKeyboardHeightChange(e: WechatMiniprogram.TextareaKeyboardHeightChange) {
      const height = Math.max(0, Math.floor(Number(e.detail?.height) || 0))
      this.setData(sheetPatch(this, { keyboardHeight: height }))
    },
    onSubmit() {
      if (this.properties.submitting) return
      this.triggerEvent('submit', { reason: this.data.draftReason.trim() })
    },
  },
})
