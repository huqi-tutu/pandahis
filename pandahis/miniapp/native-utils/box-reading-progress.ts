/** 史略详情阅读进度：登录用户持久化。
 * 锚点优先 scrollTopPx（有栏坐标系下的 scroll-view 偏移），progressPct 作跨端兜底。
 */

import { getToken, hasToken, request } from './api'
import { encodePathSegment } from './encode-path-segment'

export const MIN_RESTORABLE_PROGRESS_PCT = 5
export const MAX_RESTORABLE_PROGRESS_PCT = 95
export const BOX_READING_PROGRESS_STORAGE_KEY = 'boxReadingProgressByUser'

export type BoxReadingProgressRecord = {
  progressPct: number
  scrollTopPx: number | null
  updatedAt: string
}

export type BoxReadingProgressMap = Record<string, BoxReadingProgressRecord>

export type BoxReadingProgressInput = {
  progressPct: number
  scrollTopPx?: number | null
}

/** 按登录令牌分桶，避免换账号串本地进度 */
export function readingProgressScopeKey(token = getToken()): string | null {
  const raw = String(token || '').trim()
  if (!raw) return null
  let hash = 0
  for (let i = 0; i < raw.length; i += 1) {
    hash = ((hash << 5) - hash + raw.charCodeAt(i)) | 0
  }
  return `s${hash}`
}

export function isRestorableProgressPct(pct: unknown): pct is number {
  return typeof pct === 'number'
    && Number.isFinite(pct)
    && pct >= MIN_RESTORABLE_PROGRESS_PCT
    && pct <= MAX_RESTORABLE_PROGRESS_PCT
}

export function clampProgressPct(pct: unknown): number {
  if (typeof pct !== 'number' || !Number.isFinite(pct)) return 0
  return Math.min(100, Math.max(0, Math.round(pct)))
}

export function progressPctFromScroll(scrollTop: number, maxScroll: number): number {
  if (!(maxScroll > 0) || !(scrollTop >= 0)) return 0
  return clampProgressPct((scrollTop / maxScroll) * 100)
}

export function scrollTopFromProgressPct(pct: number, maxScroll: number): number {
  if (!isRestorableProgressPct(pct) || !(maxScroll > 0)) return 0
  return Math.max(0, Math.round((pct / 100) * maxScroll))
}

export function maxScrollFromMetrics(scrollHeight: number, viewportH: number): number {
  return Math.max((Number(scrollHeight) || 0) - (Number(viewportH) || 0), 0)
}

/** 详情 Tab 栏为绝对定位 overlay，视口回退用 tabTop（勿用 bodyTop，会多扣 Tab 高） */
export function detailViewportFallbackPx(windowHeight: number, tabTop: number): number {
  return Math.max((Number(windowHeight) || 0) - (Number(tabTop) || 0), 0)
}

export const ORIGINAL_READING_PROGRESS_SUFFIX = '__original'

/** 原文半屏进度与详情隔离：同一 box 使用独立存储键 */
export function originalReadingProgressId(boxId: string): string {
  const id = String(boxId || '').trim()
  if (!id) return ''
  if (id.endsWith(ORIGINAL_READING_PROGRESS_SUFFIX)) return id
  return `${id}${ORIGINAL_READING_PROGRESS_SUFFIX}`
}

/** 原文半屏 body 约 62vh；测不到 DOM 时作百分比换算回退 */
export function originalViewportFallbackPx(windowHeight: number): number {
  return Math.max(Math.round((Number(windowHeight) || 0) * 0.62), 0)
}

export function normalizeScrollTopPx(raw: unknown): number | null {
  if (typeof raw !== 'number' || !Number.isFinite(raw)) return null
  const n = Math.round(raw)
  if (n < 0 || n > 2_000_000) return null
  return n
}

/** 恢复目标：有 scrollTop 用 scrollTop（夹到 maxScroll）；否则用百分比 */
export function resolveRestoreScrollTop(
  record: Pick<BoxReadingProgressRecord, 'progressPct' | 'scrollTopPx'> | null | undefined,
  maxScroll: number,
): number {
  if (!record || !isRestorableProgressPct(record.progressPct)) return 0
  const safeMax = Math.max(0, maxScroll)
  const scrollTop = normalizeScrollTopPx(record.scrollTopPx)
  if (scrollTop != null && scrollTop > 0) {
    return Math.min(scrollTop, safeMax)
  }
  return scrollTopFromProgressPct(record.progressPct, safeMax)
}

export function normalizeProgressRecord(
  raw: unknown,
): BoxReadingProgressRecord | null {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null
  const obj = raw as Record<string, unknown>
  const progressPct = clampProgressPct(obj.progressPct)
  if (!isRestorableProgressPct(progressPct)) return null
  const updatedAt = typeof obj.updatedAt === 'string' && obj.updatedAt.trim()
    ? obj.updatedAt.trim()
    : ''
  if (!updatedAt || !Number.isFinite(Date.parse(updatedAt))) return null
  return {
    progressPct,
    scrollTopPx: normalizeScrollTopPx(obj.scrollTopPx),
    updatedAt,
  }
}

export function readProgressMap(raw: unknown): BoxReadingProgressMap {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return {}
  const out: BoxReadingProgressMap = {}
  for (const [boxId, value] of Object.entries(raw as Record<string, unknown>)) {
    const id = String(boxId || '').trim()
    if (!id) continue
    const record = normalizeProgressRecord(value)
    if (record) out[id] = record
  }
  return out
}

/** 取本地/远端中较新的一条；均无效则 null */
export function pickNewerProgress(
  local: BoxReadingProgressRecord | null | undefined,
  remote: BoxReadingProgressRecord | null | undefined,
): BoxReadingProgressRecord | null {
  const a = normalizeProgressRecord(local)
  const b = normalizeProgressRecord(remote)
  if (!a) return b
  if (!b) return a
  return Date.parse(b.updatedAt) > Date.parse(a.updatedAt) ? b : a
}

export function upsertProgressMap(
  map: BoxReadingProgressMap | null | undefined,
  boxId: string,
  input: BoxReadingProgressInput,
  updatedAt = new Date().toISOString(),
): BoxReadingProgressMap {
  const id = String(boxId || '').trim()
  const prev = readProgressMap(map)
  if (!id) return prev
  const next = { ...prev }
  const progressPct = clampProgressPct(input.progressPct)
  if (!isRestorableProgressPct(progressPct)) {
    if (Object.prototype.hasOwnProperty.call(next, id)) {
      delete next[id]
    }
    return next
  }
  next[id] = {
    progressPct,
    scrollTopPx: normalizeScrollTopPx(input.scrollTopPx),
    updatedAt: String(updatedAt || new Date().toISOString()),
  }
  return next
}

function readScopedStore(): Record<string, BoxReadingProgressMap> {
  try {
    const raw = wx.getStorageSync(BOX_READING_PROGRESS_STORAGE_KEY)
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return {}
    const out: Record<string, BoxReadingProgressMap> = {}
    for (const [scope, value] of Object.entries(raw as Record<string, unknown>)) {
      const key = String(scope || '').trim()
      if (!key) continue
      out[key] = readProgressMap(value)
    }
    return out
  } catch {
    return {}
  }
}

function writeScopedStore(store: Record<string, BoxReadingProgressMap>): void {
  try {
    wx.setStorageSync(BOX_READING_PROGRESS_STORAGE_KEY, store)
  } catch {
    // ignore
  }
}

export function readLocalBoxReadingProgressMap(): BoxReadingProgressMap {
  const scope = readingProgressScopeKey()
  if (!scope) return {}
  return readProgressMap(readScopedStore()[scope])
}

export function writeLocalBoxReadingProgressMap(map: BoxReadingProgressMap): void {
  const scope = readingProgressScopeKey()
  if (!scope) return
  const store = { ...readScopedStore(), [scope]: readProgressMap(map) }
  writeScopedStore(store)
}

export function readLocalBoxReadingProgress(boxId: string): BoxReadingProgressRecord | null {
  const id = String(boxId || '').trim()
  if (!id) return null
  return normalizeProgressRecord(readLocalBoxReadingProgressMap()[id])
}

export function writeLocalBoxReadingProgress(
  boxId: string,
  input: BoxReadingProgressInput,
  updatedAt = new Date().toISOString(),
): BoxReadingProgressRecord | null {
  const scope = readingProgressScopeKey()
  if (!scope) return null
  const next = upsertProgressMap(readLocalBoxReadingProgressMap(), boxId, input, updatedAt)
  writeLocalBoxReadingProgressMap(next)
  const id = String(boxId || '').trim()
  return id ? normalizeProgressRecord(next[id]) : null
}

export type RemoteBoxReadingProgress = {
  boxId?: string
  progressPct?: number | null
  scrollTopPx?: number | null
  updatedAt?: string | null
}

export async function fetchRemoteBoxReadingProgress(
  boxId: string,
): Promise<BoxReadingProgressRecord | null> {
  if (!hasToken()) return null
  const id = String(boxId || '').trim()
  if (!id) return null
  try {
    const res = await request<RemoteBoxReadingProgress>(
      `/me/boxes/${encodePathSegment(id)}/reading-progress`,
      { method: 'GET', auth: true },
    )
    return normalizeProgressRecord({
      progressPct: res.data?.progressPct,
      scrollTopPx: res.data?.scrollTopPx,
      updatedAt: res.data?.updatedAt,
    })
  } catch {
    return null
  }
}

export async function saveRemoteBoxReadingProgress(
  boxId: string,
  input: BoxReadingProgressInput,
): Promise<BoxReadingProgressRecord | null> {
  if (!hasToken()) return null
  const id = String(boxId || '').trim()
  if (!id) return null
  try {
    const res = await request<RemoteBoxReadingProgress>(
      `/me/boxes/${encodePathSegment(id)}/reading-progress`,
      {
        method: 'PUT',
        auth: true,
        data: {
          progressPct: clampProgressPct(input.progressPct),
          scrollTopPx: normalizeScrollTopPx(input.scrollTopPx),
        },
      },
    )
    return normalizeProgressRecord({
      progressPct: res.data?.progressPct,
      scrollTopPx: res.data?.scrollTopPx,
      updatedAt: res.data?.updatedAt,
    })
  } catch {
    return null
  }
}

/** 登录用户：合并本地与远端进度；未登录恒为 null */
export async function resolveBoxReadingProgress(
  boxId: string,
): Promise<BoxReadingProgressRecord | null> {
  if (!hasToken()) return null
  const local = readLocalBoxReadingProgress(boxId)
  const remote = await fetchRemoteBoxReadingProgress(boxId)
  const picked = pickNewerProgress(local, remote)
  if (picked) {
    writeLocalBoxReadingProgress(
      boxId,
      { progressPct: picked.progressPct, scrollTopPx: picked.scrollTopPx },
      picked.updatedAt,
    )
  }
  return picked
}

/** 登录用户：写本地并尽力同步远端；未登录 no-op */
export async function persistBoxReadingProgress(
  boxId: string,
  input: BoxReadingProgressInput,
): Promise<void> {
  if (!hasToken()) return
  writeLocalBoxReadingProgress(boxId, input)
  await saveRemoteBoxReadingProgress(boxId, input)
}
