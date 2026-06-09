const KEY = 'searchHistoryLocal'
const MAX = 20

export function readLocalSearchHistory(): string[] {
  try {
    const raw = wx.getStorageSync(KEY)
    if (!Array.isArray(raw)) return []
    return raw.filter((x) => typeof x === 'string' && x.trim()).map((x) => x.trim())
  } catch {
    return []
  }
}

export function addLocalSearchHistory(keyword: string): void {
  const k = keyword.trim()
  if (!k) return
  const list = readLocalSearchHistory().filter((x) => x !== k)
  list.unshift(k)
  try {
    wx.setStorageSync(KEY, list.slice(0, MAX))
  } catch {
    // ignore
  }
}

export function removeLocalSearchHistory(keyword: string): void {
  const k = keyword.trim()
  if (!k) return
  try {
    wx.setStorageSync(
      KEY,
      readLocalSearchHistory().filter((x) => x !== k)
    )
  } catch {
    // ignore
  }
}
