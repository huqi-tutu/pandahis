export type FavoriteItemRaw = {
  boxId: string
  title: string
  subText?: string
  categoryKey?: string
  favoritedAt?: string
  startYear?: number
  endYear?: number
  pathLabel?: string
}

export type FavoriteCardView = FavoriteItemRaw & {
  dateLabel: string
  yearRange: string
  pathLabel: string
}

export function formatHistoryYear(y: number): string {
  if (y < 0) return `前${Math.abs(y)}`
  return String(y)
}

export function formatYearRange(start?: number, end?: number): string {
  const s = start ?? 0
  const e = end ?? s
  return `${formatHistoryYear(s)} — ${formatHistoryYear(e)}`
}

export function formatFavoriteDate(iso?: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const that = new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
  const diffDays = Math.round((today - that) / 86400000)
  if (diffDays === 0) return '今天'
  if (diffDays === 1) return '昨天'
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${mm}-${dd}`
}

export function toFavoriteCardView(item: FavoriteItemRaw): FavoriteCardView {
  const pathLabel =
    item.pathLabel ||
    (item.subText?.includes('·') ? item.subText.split('·').slice(1).join('·').trim() : item.subText || '')
  return {
    ...item,
    dateLabel: formatFavoriteDate(item.favoritedAt),
    yearRange: formatYearRange(item.startYear, item.endYear),
    pathLabel,
  }
}

export function isDynastyFavorite(categoryKey?: string): boolean {
  return categoryKey === 'junji'
}

export function splitFavorites(items: FavoriteItemRaw[]): {
  dynasty: FavoriteCardView[]
  shilue: FavoriteCardView[]
} {
  const dynasty: FavoriteCardView[] = []
  const shilue: FavoriteCardView[] = []
  for (const raw of items) {
    const card = toFavoriteCardView(raw)
    if (isDynastyFavorite(raw.categoryKey)) {
      dynasty.push(card)
    } else {
      shilue.push(card)
    }
  }
  return { dynasty, shilue }
}

export type FootprintItemRaw = {
  boxId: string
  title: string
  subText?: string
  categoryKey?: string
  lastViewedAt?: string
  viewCount?: number
  startYear?: number
  endYear?: number
  pathLabel?: string
}

export type FootprintCardView = FootprintItemRaw & {
  timeLabel: string
  yearRange: string
  pathLabel: string
}

/** 足迹访问时间：刚刚 / N 分钟前 / 昨天 / MM-DD */
export function formatVisitTime(iso?: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const diffMs = Date.now() - d.getTime()
  if (diffMs < 60_000) return '刚刚'
  if (diffMs < 3_600_000) {
    const mins = Math.max(1, Math.floor(diffMs / 60_000))
    return `${mins} 分钟前`
  }
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const that = new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
  const diffDays = Math.round((today - that) / 86400000)
  if (diffDays === 0) return '今天'
  if (diffDays === 1) return '昨天'
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${mm}-${dd}`
}

export function toFootprintCardView(item: FootprintItemRaw): FootprintCardView {
  const pathLabel = item.pathLabel || item.subText || ''
  return {
    ...item,
    timeLabel: formatVisitTime(item.lastViewedAt),
    yearRange: formatYearRange(item.startYear, item.endYear),
    pathLabel,
  }
}
