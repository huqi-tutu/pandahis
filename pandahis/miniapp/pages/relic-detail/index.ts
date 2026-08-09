import { request } from '../../native-utils/api'
import {
  requireLoginForCorrection,
  submitCorrection,
  type CorrectionSourceType,
} from '../../native-utils/correction'
import { encodePathSegment } from '../../native-utils/encode-path-segment'
import { computePageTopPadPx } from '../../native-utils/nav-metrics'
import { resolveSelectionBarAnchor } from '../../native-utils/selection-bar-position'

const SOURCE_TYPE: CorrectionSourceType = 'relic_detail_selection'

type RelicApiDetail = {
  id?: number
  boxId?: string
  boxTitle?: string
  civilizationName?: string
  dynastyName?: string
  name?: string
  museum?: string
  description?: string
  summary?: string
  imageUrl?: string
}

Page({
  data: {
    relicId: 0,
    navTitle: '',
    name: '',
    museum: '',
    detail: '',
    imageUrl: '',
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
  async onLoad(query: Record<string, string | undefined>) {
    try {
      this.setData({ pageTopPadPx: computePageTopPadPx() })
    } catch {
      this.setData({ pageTopPadPx: 88 })
    }
    const relicId = Number(query.relicId || 0)
    if (relicId > 0) {
      this.setData({ relicId })
      await this.loadById(relicId)
      return
    }
    const name = decodeURIComponent(query.name || '')
    const navTitle = decodeURIComponent(query.navTitle || '') || name || '见证'
    const boxTitle = decodeURIComponent(query.boxTitle || '') || navTitle.replace(/・见证$/, '') || name
    this.setData({
      navTitle,
      name,
      museum: decodeURIComponent(query.museum || ''),
      detail: decodeURIComponent(query.detail || ''),
      imageUrl: decodeURIComponent(query.imageUrl || ''),
      boxId: decodeURIComponent(query.boxId || ''),
      boxTitle,
      civilizationName: decodeURIComponent(query.civilizationName || ''),
      dynastyName: decodeURIComponent(query.dynastyName || ''),
    })
  },
  async loadById(relicId: number) {
    try {
      wx.showLoading({ title: '加载中', mask: true })
      const res = await request<RelicApiDetail>(`/relics/${encodePathSegment(String(relicId))}`)
      wx.hideLoading()
      const d = res.data || {}
      const boxTitle = String(d.boxTitle || '').trim()
      const name = String(d.name || '').trim()
      this.setData({
        relicId,
        boxId: String(d.boxId || '').trim(),
        boxTitle,
        civilizationName: String(d.civilizationName || '').trim(),
        dynastyName: String(d.dynastyName || '').trim(),
        navTitle: boxTitle ? `${boxTitle}・见证` : '见证',
        name,
        museum: String(d.museum || '').trim(),
        detail: String(d.description || d.summary || '').trim(),
        imageUrl: String(d.imageUrl || '').trim(),
      })
    } catch (err: unknown) {
      wx.hideLoading()
      const msg = err instanceof Error ? err.message : '加载失败'
      wx.showToast({ title: msg, icon: 'none' })
    }
  },
  onReady() {
    this.bindBodySelectionContext()
  },
  bindBodySelectionContext() {
    wx.createSelectorQuery()
      .in(this)
      .select('#relicBodySelection')
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
    const relicId = Number(this.data.relicId || 0)
    if (!boxId || this.data.correctionSubmitting) {
      if (!boxId) wx.showToast({ title: '缺少史略信息，无法提交', icon: 'none' })
      return
    }
    if (!(relicId > 0)) {
      wx.showToast({ title: '缺少见证信息，无法提交', icon: 'none' })
      return
    }
    this.setData({ correctionSubmitting: true })
    try {
      await submitCorrection({
        boxId,
        sourceType: SOURCE_TYPE,
        reason,
        selectedText: this.data.correctionSelectedText,
        sourceRefId: relicId,
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
