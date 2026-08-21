import { hasToken } from '../../native-utils/api'
import {
  deleteNote,
  fetchNoteDetail,
  formatNoteTime,
  navigateToNoteSource,
  noteRemarkLabel,
  noteSourceLabel,
  resolveNoteSourceNav,
  updateNote,
  type NoteDetail,
} from '../../native-utils/note'
import { computePageTopPadPx } from '../../native-utils/nav-metrics'
import { ROUTES, navigateTo } from '../../native-utils/router'

const EMPTY_DETAIL: NoteDetail = {
  id: 0,
  boxId: '',
  boxTitle: '',
  boxCategoryKey: '',
  boxCategoryName: '',
  civilizationName: '',
  dynastyName: '',
  regimeName: '',
  emperorName: '',
  coordinateText: '',
  sourceType: 'box_detail_selection',
  selectedText: '',
  noteText: '',
  createdAt: '',
}

Page({
  data: {
    hasToken: false,
    loaded: false,
    noteId: 0,
    detail: EMPTY_DETAIL,
    sourceLabel: '',
    createdAtLabel: '',
    remarkLabel: noteRemarkLabel(''),
    emptyRemark: true,
    canViewSource: false,
    editVisible: false,
    submitting: false,
    pageTopPadPx: 88,
  },
  onLoad(query: Record<string, string | undefined>) {
    try {
      this.setData({ pageTopPadPx: computePageTopPadPx() })
    } catch {
      this.setData({ pageTopPadPx: 88 })
    }
    this.setData({ noteId: Number(query.id || 0) })
  },
  onShow() {
    const ok = hasToken()
    this.setData({ hasToken: ok })
    if (ok) void this.load()
    else this.setData({ loaded: true, detail: EMPTY_DETAIL })
  },
  goLogin() {
    navigateTo(ROUTES.login)
  },
  applyDetail(detail: NoteDetail) {
    const remark = String(detail.noteText || '').trim()
    this.setData({
      detail,
      loaded: true,
      sourceLabel: noteSourceLabel(detail.sourceType),
      createdAtLabel: formatNoteTime(detail.createdAt),
      remarkLabel: noteRemarkLabel(remark),
      emptyRemark: !remark,
      canViewSource: !('error' in resolveNoteSourceNav(detail)),
    })
  },
  async load() {
    const id = this.data.noteId
    if (!id) {
      this.setData({ loaded: true, detail: EMPTY_DETAIL })
      return
    }
    try {
      const detail = await fetchNoteDetail(id)
      this.applyDetail(detail)
    } catch {
      this.setData({ loaded: true, detail: EMPTY_DETAIL })
    }
  },
  onViewSource() {
    const detail = this.data.detail as NoteDetail
    if (!detail.id || !this.data.canViewSource) return
    navigateToNoteSource(detail)
  },
  onEdit() {
    this.setData({ editVisible: true, submitting: false })
  },
  closeEdit() {
    this.setData({ editVisible: false, submitting: false })
  },
  async onEditSubmit(e: WechatMiniprogram.CustomEvent) {
    const noteText = String((e.detail as { noteText?: string })?.noteText || '')
    const id = this.data.noteId
    if (!id || this.data.submitting) return
    this.setData({ submitting: true })
    try {
      const detail = await updateNote(id, noteText)
      this.setData({ editVisible: false, submitting: false })
      this.applyDetail(detail)
      wx.showToast({ title: '已保存', icon: 'success' })
    } catch (err: unknown) {
      this.setData({ submitting: false })
      const msg = err instanceof Error ? err.message : '保存失败'
      wx.showToast({ title: msg, icon: 'none' })
    }
  },
  onDelete() {
    const id = this.data.noteId
    if (!id) return
    wx.showModal({
      title: '删除笔记',
      content: '删除后划线也会一起去掉，确定删除？',
      confirmText: '删除',
      success: (r) => {
        if (r.confirm) void this.doDelete(id)
      },
    })
  },
  async doDelete(id: number) {
    try {
      await deleteNote(id)
      wx.showToast({ title: '已删除', icon: 'success' })
      setTimeout(() => wx.navigateBack(), 400)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '删除失败'
      wx.showToast({ title: msg, icon: 'none' })
    }
  },
})
