/** 历史年份展示：公元前用 -XX */
export function formatHistoryYear(y: number): string {
  if (!Number.isFinite(y)) return ''
  if (y === 0) return '公元0'
  if (y < 0) return `-${Math.abs(y)}`
  return String(y)
}

export function formatYearRange(start?: number, end?: number, sep = ' — '): string {
  const s = start ?? 0
  const e = end ?? s
  return `${formatHistoryYear(s)}${sep}${formatHistoryYear(e)}`
}
