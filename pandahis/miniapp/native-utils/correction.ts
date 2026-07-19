import { hasToken, request } from './api'
import { encodePathSegment } from './encode-path-segment'
import { ROUTES, navigateTo } from './router'

export type CorrectionSourceType = 'dynasty_canvas' | 'box_detail_selection'

export type CorrectionStatus = 'pending' | 'reviewed' | 'resolved'

export type CorrectionDetail = {
  id: number
  boxId: string
  boxTitle: string
  unitId?: string | null
  civilizationName: string
  dynastyName: string
  sourceType: CorrectionSourceType
  selectedText?: string | null
  reason?: string | null
  status: CorrectionStatus
  createdAt: string
}

export type CorrectionListItem = {
  id: number
  boxId: string
  boxTitle: string
  status: CorrectionStatus
  createdAt: string
}

export const CORRECTION_STATUS_LABEL: Record<string, string> = {
  pending: '待处理',
  reviewed: '已审阅',
  resolved: '已解决',
}

export const CORRECTION_SOURCE_LABEL: Record<string, string> = {
  dynasty_canvas: '朝代详情页',
  box_detail_selection: '史略详情页',
}

export function correctionStatusLabel(status: string): string {
  return CORRECTION_STATUS_LABEL[status] || status || '待处理'
}

export function correctionSourceLabel(sourceType: string): string {
  return CORRECTION_SOURCE_LABEL[sourceType] || sourceType || ''
}

export function formatCorrectionTime(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso.replace('T', ' ').slice(0, 19)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

function normalizeDetail(raw: Record<string, unknown>): CorrectionDetail {
  return {
    id: Number(raw.id ?? raw['id'] ?? 0),
    boxId: String(raw.boxId ?? raw['box_id'] ?? ''),
    boxTitle: String(raw.boxTitle ?? raw['box_title'] ?? ''),
    unitId: (raw.unitId ?? raw['unit_id'] ?? null) as string | null,
    civilizationName: String(raw.civilizationName ?? raw['civilization_name'] ?? ''),
    dynastyName: String(raw.dynastyName ?? raw['dynasty_name'] ?? ''),
    sourceType: String(raw.sourceType ?? raw['source_type'] ?? '') as CorrectionSourceType,
    selectedText: (raw.selectedText ?? raw['selected_text'] ?? null) as string | null,
    reason: (raw.reason ?? null) as string | null,
    status: String(raw.status ?? 'pending') as CorrectionStatus,
    createdAt: String(raw.createdAt ?? raw['created_at'] ?? ''),
  }
}

function normalizeListItem(raw: Record<string, unknown>): CorrectionListItem {
  return {
    id: Number(raw.id ?? raw['id'] ?? 0),
    boxId: String(raw.boxId ?? raw['box_id'] ?? ''),
    boxTitle: String(raw.boxTitle ?? raw['box_title'] ?? ''),
    status: String(raw.status ?? 'pending') as CorrectionStatus,
    createdAt: String(raw.createdAt ?? raw['created_at'] ?? ''),
  }
}

export function promptLoginForCorrection() {
  wx.showModal({
    title: '需要登录',
    content: '登录后可提交纠错，并在「我的纠错」中查看记录。',
    confirmText: '去登录',
    success: (r) => {
      if (r.confirm) navigateTo(ROUTES.login)
    },
  })
}

export type SubmitCorrectionPayload = {
  boxId: string
  sourceType: CorrectionSourceType
  reason?: string
  selectedText?: string
}

export async function submitCorrection(payload: SubmitCorrectionPayload): Promise<CorrectionDetail> {
  const res = await request<Record<string, unknown>>('/corrections', {
    method: 'POST',
    auth: true,
    data: {
      boxId: payload.boxId,
      sourceType: payload.sourceType,
      reason: payload.reason || undefined,
      selectedText: payload.selectedText || undefined,
    },
  })
  return normalizeDetail((res.data || {}) as Record<string, unknown>)
}

export async function fetchCorrections(page = 1, pageSize = 20): Promise<{ items: CorrectionListItem[]; total: number }> {
  const res = await request<{ items: Record<string, unknown>[]; total: number }>(
    `/corrections?page=${page}&pageSize=${pageSize}`,
    { auth: true }
  )
  const items = (res.data.items || []).map((x) => normalizeListItem(x))
  return { items, total: res.data.total ?? items.length }
}

export async function fetchCorrectionDetail(id: number): Promise<CorrectionDetail> {
  const res = await request<Record<string, unknown>>(`/corrections/${encodePathSegment(String(id))}`, {
    auth: true,
  })
  return normalizeDetail((res.data || {}) as Record<string, unknown>)
}

export function requireLoginForCorrection(action: () => void) {
  if (!hasToken()) {
    promptLoginForCorrection()
    return
  }
  action()
}

export function parseCivilizationFromCrumb(crumbText: string): string {
  const text = (crumbText || '').trim()
  if (!text) return ''
  const idx = text.indexOf(' · ')
  return idx >= 0 ? text.slice(0, idx).trim() : text
}
