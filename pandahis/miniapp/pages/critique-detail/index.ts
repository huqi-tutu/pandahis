import { request } from '../../native-utils/api'
import {
  requireLoginForCorrection,
  submitCorrection,
  type CorrectionSourceType,
} from '../../native-utils/correction'
import {
  fetchNoteHighlights,
  requireLoginForNote,
  submitNote,
  type NoteHighlight,
} from '../../native-utils/note'
import { applyHighlightsToPlain, highlightAnchorId } from '../../native-utils/note-highlight'
import { encodePathSegment } from '../../native-utils/encode-path-segment'
import { computePageTopPadPx } from '../../native-utils/nav-metrics'
import { resolveSelectionBarAnchor } from '../../native-utils/selection-bar-position'

const SOURCE_TYPE: CorrectionSourceType = 'critique_detail_selection'

/** 从「史略名称·评述角度」取 · 后的评述角度 */
function critiqueAngleTitle(fullTitle: string): string {
  const t = String(fullTitle || '').trim()
  if (!t) return ''
  const dotIdx = t.indexOf('·')
  if (dotIdx >= 0) {
    const rest = t.slice(dotIdx + 1).trim()
    return rest || t
  }
  return t
}

type CritiqueApiDetail = {
  id?: number
  boxId?: string
  boxTitle?: string
  civilizationName?: string
  dynastyName?: string
  title?: string
  author?: string
  eraText?: string
  content?: string
  source?: string
  blurb?: string
}

Page({
  data: {
    critiqueId: 0,
    navTitle: '',
    title: '',
    author: '',
    book: '',
    era: '',
    body: '',
    bodySegs: [] as Array<{ text: string; highlight?: boolean; noteId?: number; anchorId?: string; focus?: boolean }>,
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
    noteVisible: false,
    noteSubmitting: false,
    noteSelectedText: '',
    focusNoteId: 0,
  },
  _selectionContext: null as WechatMiniprogram.IAnyObject | null,
  async onLoad(query: Record<string, string | undefined>) {
    try {
      this.setData({ pageTopPadPx: computePageTopPadPx() })
    } catch {
      this.setData({ pageTopPadPx: 88 })
    }
    const critiqueId = Number(query.critiqueId || 0)
    const focusNoteId = Number(query.noteId || 0)
    this.setData({ focusNoteId: Number.isFinite(focusNoteId) ? focusNoteId : 0 })
    if (critiqueId > 0) {
      this.setData({ critiqueId })
      await this.loadById(critiqueId)
      return
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
    await this.loadHighlights()
  },
  async loadById(critiqueId: number) {
    try {
      wx.showLoading({ title: '加载中', mask: true })
      const res = await request<CritiqueApiDetail>(`/critiques/${encodePathSegment(String(critiqueId))}`)
      wx.hideLoading()
      const d = res.data || {}
      const boxTitle = String(d.boxTitle || '').trim()
      const fullTitle = String(d.title || '').trim()
      const angleTitle = critiqueAngleTitle(fullTitle)
      this.setData({
        critiqueId,
        boxId: String(d.boxId || '').trim(),
        boxTitle,
        civilizationName: String(d.civilizationName || '').trim(),
        dynastyName: String(d.dynastyName || '').trim(),
        navTitle: boxTitle ? `${boxTitle}・评述` : '评述详情',
        title: angleTitle || fullTitle || '暂无主题',
        author: String(d.author || '').trim(),
        book: String(d.source || '').trim(),
        era: String(d.eraText || '').trim(),
        body: String(d.content || d.blurb || '').trim(),
      })
      await this.loadHighlights()
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
      { buttonCount: 4 },
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
  onSelectionNote() {
    const text = this.data.selectionBarText
    this.hideSelectionBar()
    if (!text) return
    requireLoginForNote(() => {
      this.setData({
        noteVisible: true,
        noteSubmitting: false,
        noteSelectedText: text,
      })
    })
  },
  closeNote() {
    this.setData({ noteVisible: false, noteSubmitting: false })
    this.clearBodySelection()
  },
  applyHighlights(highlights: NoteHighlight[]) {
    const body = String(this.data.body || '')
    this.setData({
      bodySegs: applyHighlightsToPlain(body, highlights, this.data.focusNoteId),
    })
    if (this.data.focusNoteId) {
      const id = highlightAnchorId(this.data.focusNoteId)
      setTimeout(() => {
        wx.pageScrollTo({ selector: `#${id}`, duration: 240 })
      }, 80)
    }
  },
  async loadHighlights() {
    const boxId = this.data.boxId
    const critiqueId = Number(this.data.critiqueId || 0)
    if (!boxId || !(critiqueId > 0)) {
      this.applyHighlights([])
      return
    }
    try {
      const highlights = await fetchNoteHighlights(boxId, SOURCE_TYPE, critiqueId)
      this.applyHighlights(highlights)
    } catch {
      this.applyHighlights([])
    }
  },
  async onNoteSubmit(e: WechatMiniprogram.CustomEvent) {
    const noteText = String((e.detail as { noteText?: string })?.noteText || '')
    const boxId = this.data.boxId
    const critiqueId = Number(this.data.critiqueId || 0)
    if (!boxId || this.data.noteSubmitting) {
      if (!boxId) wx.showToast({ title: '缺少史略信息，无法保存', icon: 'none' })
      return
    }
    if (!(critiqueId > 0)) {
      wx.showToast({ title: '缺少评述信息，无法保存', icon: 'none' })
      return
    }
    this.setData({ noteSubmitting: true })
    try {
      await submitNote({
        boxId,
        sourceType: SOURCE_TYPE,
        selectedText: this.data.noteSelectedText,
        noteText,
        sourceRefId: critiqueId,
      })
      wx.showToast({ title: '笔记已保存', icon: 'success' })
      this.setData({ noteVisible: false, noteSubmitting: false })
      await this.loadHighlights()
    } catch (err: unknown) {
      this.setData({ noteSubmitting: false })
      const msg = err instanceof Error ? err.message : '保存失败，请稍后重试'
      wx.showToast({ title: msg, icon: 'none' })
    }
  },
  closeCorrection() {
    this.setData({ correctionVisible: false, correctionSubmitting: false })
    this.clearBodySelection()
  },
  async onCorrectionSubmit(e: WechatMiniprogram.CustomEvent) {
    const reason = String((e.detail as { reason?: string })?.reason || '')
    const boxId = this.data.boxId
    const critiqueId = Number(this.data.critiqueId || 0)
    if (!boxId || this.data.correctionSubmitting) {
      if (!boxId) wx.showToast({ title: '缺少史略信息，无法提交', icon: 'none' })
      return
    }
    if (!(critiqueId > 0)) {
      wx.showToast({ title: '缺少评述信息，无法提交', icon: 'none' })
      return
    }
    this.setData({ correctionSubmitting: true })
    try {
      await submitCorrection({
        boxId,
        sourceType: SOURCE_TYPE,
        reason,
        selectedText: this.data.correctionSelectedText,
        sourceRefId: critiqueId,
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
