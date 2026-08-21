/** 史略详情页内搜索历史（按 boxId 隔离） */

const PREFIX = 'boxDetailSearchHistory:'
const MAX = 15

function storageKey(boxId: string): string {
  return `${PREFIX}${String(boxId || '').trim()}`
}

export function readBoxDetailSearchHistory(boxId: string): string[] {
  const id = String(boxId || '').trim()
  if (!id) return []
  try {
    const raw = wx.getStorageSync(storageKey(id))
    if (!Array.isArray(raw)) return []
    return raw.filter((x) => typeof x === 'string' && x.trim()).map((x) => x.trim())
  } catch {
    return []
  }
}

export function addBoxDetailSearchHistory(boxId: string, keyword: string): void {
  const id = String(boxId || '').trim()
  const k = String(keyword || '').trim().slice(0, 50)
  if (!id || !k) return
  const list = readBoxDetailSearchHistory(id).filter((x) => x !== k)
  list.unshift(k)
  try {
    wx.setStorageSync(storageKey(id), list.slice(0, MAX))
  } catch {
    // ignore
  }
}

export function removeBoxDetailSearchHistory(boxId: string, keyword: string): void {
  const id = String(boxId || '').trim()
  const k = String(keyword || '').trim()
  if (!id || !k) return
  try {
    wx.setStorageSync(
      storageKey(id),
      readBoxDetailSearchHistory(id).filter((x) => x !== k)
    )
  } catch {
    // ignore
  }
}

/** 清空本篇全部搜索历史 */
export function clearBoxDetailSearchHistory(boxId: string): void {
  const id = String(boxId || '').trim()
  if (!id) return
  try {
    wx.removeStorageSync(storageKey(id))
  } catch {
    try {
      wx.setStorageSync(storageKey(id), [])
    } catch {
      // ignore
    }
  }
}
