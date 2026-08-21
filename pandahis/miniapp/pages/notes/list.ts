import { hasToken } from '../../native-utils/api'
import {
  excerptText,
  fetchNotesByDynasty,
  formatNoteTime,
  noteRemarkLabel,
  type NoteListItem,
} from '../../native-utils/note'
import { computePageTopPadPx } from '../../native-utils/nav-metrics'
import { decodeQueryValue } from '../../native-utils/query-value'
import { ROUTES, navigateTo } from '../../native-utils/router'

type NoteListVm = NoteListItem & {
  createdAtLabel: string
  selectedExcerpt: string
  remarkLabel: string
  emptyRemark: boolean
}

Page({
  data: {
    hasToken: false,
    loaded: false,
    dynastyId: '',
    navTitle: '笔记',
    items: [] as NoteListVm[],
    pageTopPadPx: 88,
  },
  onLoad(query: Record<string, string | undefined>) {
    try {
      this.setData({ pageTopPadPx: computePageTopPadPx() })
    } catch {
      this.setData({ pageTopPadPx: 88 })
    }
    const dynastyId = decodeQueryValue(query.dynastyId || '')
    const dynastyName = decodeQueryValue(query.dynastyName || '') || '笔记'
    this.setData({ dynastyId, navTitle: dynastyName })
  },
  onShow() {
    const ok = hasToken()
    this.setData({ hasToken: ok, loaded: false })
    if (ok) void this.load()
    else this.setData({ loaded: true, items: [] })
  },
  goLogin() {
    navigateTo(ROUTES.login)
  },
  mapItem(item: NoteListItem): NoteListVm {
    const remark = String(item.noteText || '').trim()
    return {
      ...item,
      createdAtLabel: formatNoteTime(item.createdAt),
      selectedExcerpt: excerptText(item.selectedText, 80),
      remarkLabel: noteRemarkLabel(remark),
      emptyRemark: !remark,
    }
  },
  async load() {
    const dynastyId = this.data.dynastyId
    if (!dynastyId) {
      this.setData({ items: [], loaded: true })
      return
    }
    try {
      const all: NoteListItem[] = []
      let page = 1
      const pageSize = 50
      let total = 0
      while (true) {
        const res = await fetchNotesByDynasty(dynastyId, page, pageSize)
        all.push(...res.items)
        total = res.total
        if (res.items.length < pageSize || all.length >= total) break
        page += 1
      }
      this.setData({ items: all.map((x) => this.mapItem(x)), loaded: true })
    } catch {
      this.setData({ items: [], loaded: true })
    }
  },
  onItemTap(e: WechatMiniprogram.BaseEvent) {
    const id = Number((e.currentTarget as WechatMiniprogram.IAnyObject).dataset.id)
    if (!id) return
    navigateTo(ROUTES.noteDetail, { id })
  },
})
