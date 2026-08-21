import { hasToken, request } from './api'
import { encodePathSegment } from './encode-path-segment'
import { ROUTES, navigateTo } from './router'

export type NoteSourceType =
  | 'box_detail_selection'
  | 'critique_detail_selection'
  | 'relic_detail_selection'
  | 'relation_graph_selection'

export type NoteDetail = {
  id: number
  boxId: string
  boxTitle: string
  boxCategoryKey: string
  boxCategoryName: string
  unitId?: string | null
  civilizationName: string
  dynastyName: string
  regimeName: string
  emperorName: string
  coordinateText: string
  sourceType: NoteSourceType
  sourceRefId?: number | null
  selectedText: string
  noteText?: string | null
  createdAt: string
  updatedAt?: string | null
}

export type NoteDynastyItem = {
  dynastyId: string
  dynastyName: string
  civilizationName: string
  noteCount: number
  startYear?: number | null
}

export type NoteListItem = {
  id: number
  boxId: string
  boxTitle: string
  selectedText: string
  noteText?: string | null
  createdAt: string
}

export type NoteHighlight = {
  id: number
  selectedText: string
}

export const EMPTY_NOTE_LABEL = '仅划线'
export const NOTE_TEXT_MAX = 2000

export const NOTE_SOURCE_LABEL: Record<string, string> = {
  box_detail_selection: '史略详情',
  critique_detail_selection: '评述',
  relic_detail_selection: '见证',
  relation_graph_selection: '关系图谱',
}

export function noteSourceLabel(sourceType: string): string {
  return NOTE_SOURCE_LABEL[sourceType] || sourceType || ''
}

export function formatNoteTime(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso.replace('T', ' ').slice(0, 19)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export function noteRemarkLabel(noteText?: string | null): string {
  const text = String(noteText || '').trim()
  return text || EMPTY_NOTE_LABEL
}

export function excerptText(text: string, max = 80): string {
  const t = String(text || '').replace(/\s+/g, ' ').trim()
  if (t.length <= max) return t
  return `${t.slice(0, max)}…`
}

function toNullableNumber(raw: unknown): number | null {
  if (raw === undefined || raw === null || raw === '') return null
  const n = Number(raw)
  return Number.isFinite(n) && n > 0 ? n : null
}

function normalizeDetail(raw: Record<string, unknown>): NoteDetail {
  return {
    id: Number(raw.id ?? 0),
    boxId: String(raw.boxId ?? raw['box_id'] ?? ''),
    boxTitle: String(raw.boxTitle ?? raw['box_title'] ?? ''),
    boxCategoryKey: String(raw.boxCategoryKey ?? raw['box_category_key'] ?? ''),
    boxCategoryName: String(raw.boxCategoryName ?? raw['box_category_name'] ?? ''),
    unitId: (raw.unitId ?? raw['unit_id'] ?? null) as string | null,
    civilizationName: String(raw.civilizationName ?? raw['civilization_name'] ?? ''),
    dynastyName: String(raw.dynastyName ?? raw['dynasty_name'] ?? ''),
    regimeName: String(raw.regimeName ?? raw['regime_name'] ?? ''),
    emperorName: String(raw.emperorName ?? raw['emperor_name'] ?? ''),
    coordinateText: String(raw.coordinateText ?? raw['coordinate_text'] ?? ''),
    sourceType: String(raw.sourceType ?? raw['source_type'] ?? '') as NoteSourceType,
    sourceRefId: toNullableNumber(raw.sourceRefId ?? raw['source_ref_id']),
    selectedText: String(raw.selectedText ?? raw['selected_text'] ?? ''),
    noteText: (raw.noteText ?? raw['note_text'] ?? null) as string | null,
    createdAt: String(raw.createdAt ?? raw['created_at'] ?? ''),
    updatedAt: (raw.updatedAt ?? raw['updated_at'] ?? null) as string | null,
  }
}

function normalizeDynasty(raw: Record<string, unknown>): NoteDynastyItem {
  return {
    dynastyId: String(raw.dynastyId ?? raw['dynasty_id'] ?? ''),
    dynastyName: String(raw.dynastyName ?? raw['dynasty_name'] ?? ''),
    civilizationName: String(raw.civilizationName ?? raw['civilization_name'] ?? ''),
    noteCount: Number(raw.noteCount ?? raw['note_count'] ?? 0),
    startYear: (raw.startYear ?? raw['start_year'] ?? null) as number | null,
  }
}

function normalizeListItem(raw: Record<string, unknown>): NoteListItem {
  return {
    id: Number(raw.id ?? 0),
    boxId: String(raw.boxId ?? raw['box_id'] ?? ''),
    boxTitle: String(raw.boxTitle ?? raw['box_title'] ?? ''),
    selectedText: String(raw.selectedText ?? raw['selected_text'] ?? ''),
    noteText: (raw.noteText ?? raw['note_text'] ?? null) as string | null,
    createdAt: String(raw.createdAt ?? raw['created_at'] ?? ''),
  }
}

function normalizeHighlight(raw: Record<string, unknown>): NoteHighlight {
  return {
    id: Number(raw.id ?? 0),
    selectedText: String(raw.selectedText ?? raw['selected_text'] ?? ''),
  }
}

export function promptLoginForNote() {
  wx.showModal({
    title: '需要登录',
    content: '登录后可将划线与笔记保存到你的账号，并在「我的笔记」中查看。',
    confirmText: '去登录',
    success: (r) => {
      if (r.confirm) navigateTo(ROUTES.login)
    },
  })
}

export function requireLoginForNote(action: () => void) {
  if (!hasToken()) {
    promptLoginForNote()
    return
  }
  action()
}

export type SubmitNotePayload = {
  boxId: string
  sourceType: NoteSourceType
  selectedText: string
  noteText?: string
  sourceRefId?: number | null
}

export async function submitNote(payload: SubmitNotePayload): Promise<NoteDetail> {
  const res = await request<Record<string, unknown>>('/notes', {
    method: 'POST',
    auth: true,
    data: {
      boxId: payload.boxId,
      sourceType: payload.sourceType,
      selectedText: payload.selectedText,
      noteText: payload.noteText || undefined,
      sourceRefId: payload.sourceRefId || undefined,
    },
  })
  return normalizeDetail((res.data || {}) as Record<string, unknown>)
}

export async function updateNote(id: number, noteText: string): Promise<NoteDetail> {
  const res = await request<Record<string, unknown>>(`/notes/${encodePathSegment(String(id))}`, {
    method: 'PATCH',
    auth: true,
    data: { noteText: noteText || '' },
  })
  return normalizeDetail((res.data || {}) as Record<string, unknown>)
}

export async function deleteNote(id: number): Promise<void> {
  await request(`/notes/${encodePathSegment(String(id))}`, {
    method: 'DELETE',
    auth: true,
  })
}

export async function fetchNoteDetail(id: number): Promise<NoteDetail> {
  const res = await request<Record<string, unknown>>(`/notes/${encodePathSegment(String(id))}`, {
    auth: true,
  })
  return normalizeDetail((res.data || {}) as Record<string, unknown>)
}

export async function fetchNoteDynasties(): Promise<NoteDynastyItem[]> {
  const res = await request<{ items: Record<string, unknown>[] }>('/notes/dynasties', { auth: true })
  return (res.data.items || []).map((x) => normalizeDynasty(x))
}

export async function fetchNotesByDynasty(
  dynastyId: string,
  page = 1,
  pageSize = 20
): Promise<{ items: NoteListItem[]; total: number }> {
  const res = await request<{ items: Record<string, unknown>[]; total: number }>(
    `/notes?dynastyId=${encodeURIComponent(dynastyId)}&page=${page}&pageSize=${pageSize}`,
    { auth: true }
  )
  const items = (res.data.items || []).map((x) => normalizeListItem(x))
  return { items, total: res.data.total ?? items.length }
}

export async function fetchNoteHighlights(
  boxId: string,
  sourceType: NoteSourceType,
  sourceRefId?: number | null
): Promise<NoteHighlight[]> {
  if (!hasToken() || !boxId) return []
  const ref = sourceRefId && sourceRefId > 0 ? `&sourceRefId=${sourceRefId}` : ''
  const res = await request<Record<string, unknown>[]>(
    `/notes/highlights?boxId=${encodeURIComponent(boxId)}&sourceType=${encodeURIComponent(sourceType)}${ref}`,
    { auth: true, softAuth: true }
  )
  return (res.data || []).map((x) => normalizeHighlight(x))
}

export function resolveNoteSourceNav(
  detail: Pick<NoteDetail, 'sourceType' | 'boxId' | 'sourceRefId' | 'boxTitle' | 'selectedText' | 'id'>
): { path: string; query: Record<string, string | number> } | { error: string } {
  const sourceType = detail.sourceType
  const noteId = detail.id
  if (sourceType === 'box_detail_selection') {
    const boxId = String(detail.boxId || '').trim()
    if (!boxId) return { error: '缺少史略信息，无法跳转' }
    return {
      path: ROUTES.boxDetail,
      query: {
        boxId,
        title: String(detail.boxTitle || '').trim(),
        noteId,
        tab: 'content',
      },
    }
  }
  if (sourceType === 'critique_detail_selection') {
    const critiqueId = toNullableNumber(detail.sourceRefId)
    if (!critiqueId) return { error: '缺少评述信息，无法跳转' }
    return {
      path: ROUTES.critiqueDetail,
      query: { critiqueId, noteId },
    }
  }
  if (sourceType === 'relic_detail_selection') {
    const relicId = toNullableNumber(detail.sourceRefId)
    if (!relicId) return { error: '缺少见证信息，无法跳转' }
    return {
      path: ROUTES.relicDetail,
      query: { relicId, noteId },
    }
  }
  if (sourceType === 'relation_graph_selection') {
    const boxId = String(detail.boxId || '').trim()
    if (!boxId) return { error: '缺少史略信息，无法跳转' }
    return {
      path: ROUTES.boxDetail,
      query: {
        boxId,
        title: String(detail.boxTitle || '').trim(),
        noteId,
        tab: 'relations',
        highlightName: String(detail.selectedText || '').trim(),
      },
    }
  }
  return { error: '未知来源，无法跳转' }
}

export function navigateToNoteSource(
  detail: Pick<NoteDetail, 'sourceType' | 'boxId' | 'sourceRefId' | 'boxTitle' | 'selectedText' | 'id'>
): boolean {
  const nav = resolveNoteSourceNav(detail)
  if ('error' in nav) {
    wx.showToast({ title: nav.error, icon: 'none' })
    return false
  }
  navigateTo(nav.path, nav.query)
  return true
}
