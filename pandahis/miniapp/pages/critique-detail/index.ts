import {
  requireLoginForCorrection,
  submitCorrection,
  type CorrectionSourceType,
} from '../../native-utils/correction'
import { computePageTopPadPx } from '../../native-utils/nav-metrics'
import { resolveSelectionBarAnchor } from '../../native-utils/selection-bar-position'

const SOURCE_TYPE: CorrectionSourceType = 'critique_detail_selection'

Page({
  data: {
    navTitle: '',
    title: '',
    author: '',
    book: '',
    era: '',
    body: '',
    boxId: '',
    boxTitle: '',
    civilizationName: '',
    dynastyName: '',
    pageTopPadPx: 88,
    selectionBarVisible: false,
    selectionBarLeft: 0,
    selectionBarTop: 0,
    selectionBarPlacement: 'above' as 'above' | 'below',
    selectionBarText: '',
    selectionMountKey: 1,
    dictionaryVisible: false,
    dictionaryQuery: '',
    correctionVisible: false,
    correctionSubmitting: false,
    correctionSelectedText: '',
  },
  _selectionContext: null as WechatMiniprogram.IAnyObject | null,
  onLoad(query: Record<string, string | undefined>) {
    try {
      this.setData({ pageTopPadPx: computePageTopPadPx() })
    } catch {
      this.setData({ pageTopPadPx: 88 })
    }
    const title = decodeURIComponent(query.title || '')
    const navTitle = decodeURIComponent(query.navTitle || '') || title || '评述详情'
    const boxTitle = decodeURIComponent(query.boxTitle || '') || navTitle.replace(/・评述$/, '') || title
    this.setData({
      navTitle,
      title,
      author: decodeURIComponent(query.author || ''),
      book: decodeURIComponent(query.book || ''),
      era: decodeURIComponent(query.era || ''),
      body: decodeURIComponent(query.body || ''),
      boxId: decodeURIComponent(query.boxId || ''),
      boxTitle,
      civilizationName: decodeURIComponent(query.civilizationName || ''),
      dynastyName: decodeURIComponent(query.dynastyName || ''),
    })
  },
  onReady() {
    this.bindBodySelectionContext()
  },
  bindBodySelectionContext() {
    wx.createSelectorQuery()
      .in(this)
      .select('#critiqueBodySelection')
      .context((res) => {
        this._selectionContext = (res as WechatMiniprogram.IAnyObject)?.context ?? null
      })
      .exec()
  },
  clearBodySelection() {
    const ctx = this._selectionContext as { removeSelection?: () => void } | null
    if (ctx && typeof ctx.removeSelection === 'function') {
      try {
        ctx.removeSelection()
        return
      } catch {
        // fallback below
      }
    }
    this.setData({ selectionMountKey: this.data.selectionMountKey + 1 }, () => {
      this.bindBodySelectionContext()
    })
  },
  hideSelectionBar() {
    this.setData({
      selectionBarVisible: false,
      selectionBarText: '',
    })
    this.clearBodySelection()
  },
  onPageTap() {
    if (this.data.selectionBarVisible) this.hideSelectionBar()
  },
  onDetailSelectionChange(e: WechatMiniprogram.CustomEvent) {
    const detail = (e.detail || {}) as {
      isCollapsed?: boolean
      selectedString?: string
      firstRangeRect?: { left?: number; top?: number; width?: number; height?: number }
    }
    const selected = String(detail.selectedString || '').trim()
    if (detail.isCollapsed || !selected) {
      this.hideSelectionBar()
      return
    }
    const anchor = resolveSelectionBarAnchor(
      detail.firstRangeRect,
      {
        left: this.data.selectionBarLeft,
        top: this.data.selectionBarTop,
        placement: this.data.selectionBarPlacement,
      },
      { buttonCount: 3 },
    )
    this.setData({
      selectionBarVisible: true,
      selectionBarText: selected,
      selectionBarLeft: anchor.left,
      selectionBarTop: anchor.top,
      selectionBarPlacement: anchor.placement,
    })
  },
  onSelectionCopy() {
    const text = this.data.selectionBarText
    this.hideSelectionBar()
    if (!text) return
    wx.setClipboardData({
      data: text,
      success: () => wx.showToast({ title: '已复制', icon: 'success' }),
    })
  },
  onSelectionQuery() {
    const text = this.data.selectionBarText
    this.hideSelectionBar()
    if (!text) return
    this.clearBodySelection()
    this.setData({
      dictionaryVisible: true,
      dictionaryQuery: text,
    })
  },
  closeDictionary() {
    this.setData({ dictionaryVisible: false, dictionaryQuery: '' })
    this.clearBodySelection()
  },
  onSelectionCorrection() {
    const text = this.data.selectionBarText
    this.hideSelectionBar()
    if (!text) return
    requireLoginForCorrection(() => {
      this.setData({
        correctionVisible: true,
        correctionSubmitting: false,
        correctionSelectedText: text,
      })
    })
  },
  closeCorrection() {
    this.setData({ correctionVisible: false, correctionSubmitting: false })
    this.clearBodySelection()
  },
  async onCorrectionSubmit(e: WechatMiniprogram.CustomEvent) {
    const reason = String((e.detail as { reason?: string })?.reason || '')
    const boxId = this.data.boxId
    if (!boxId || this.data.correctionSubmitting) {
      if (!boxId) wx.showToast({ title: '缺少史略信息，无法提交', icon: 'none' })
      return
    }
    this.setData({ correctionSubmitting: true })
    try {
      await submitCorrection({
        boxId,
        sourceType: SOURCE_TYPE,
        reason,
        selectedText: this.data.correctionSelectedText,
      })
      wx.showToast({ title: '提交成功，感谢反馈', icon: 'success' })
      this.setData({ correctionVisible: false, correctionSubmitting: false })
    } catch (err: unknown) {
      this.setData({ correctionSubmitting: false })
      const msg = err instanceof Error ? err.message : '提交失败，请稍后重试'
      wx.showToast({ title: msg, icon: 'none' })
    }
  },
})
