import { hasToken, request } from './api'
import { encodePathSegment } from './encode-path-segment'
import { ROUTES, navigateTo } from './router'

export function promptLoginForFavorite() {
  wx.showModal({
    title: '需要登录',
    content: '登录后可收藏史略，并在「我的收藏」中查看。',
    confirmText: '去登录',
    success: (r) => {
      if (r.confirm) navigateTo(ROUTES.login)
    },
  })
}

export async function fetchFavoritedBoxIdSet(): Promise<Set<string>> {
  if (!hasToken()) return new Set()
  const set = new Set<string>()
  try {
    let page = 1
    const pageSize = 50
    while (true) {
      const res = await request<{ items: { boxId: string }[]; total?: number }>(
        `/favorites/boxes?page=${page}&pageSize=${pageSize}`,
        { auth: true }
      )
      const items = res.data.items || []
      for (const x of items) {
        if (x.boxId) set.add(x.boxId)
      }
      const total = res.data.total ?? items.length
      if (items.length < pageSize || set.size >= total) break
      page += 1
    }
  } catch {
    return new Set()
  }
  return set
}

export async function favoriteBox(boxId: string): Promise<void> {
  await request(`/favorites/boxes/${encodePathSegment(boxId)}`, { method: 'POST', auth: true })
}

export async function unfavoriteBox(boxId: string): Promise<void> {
  await request(`/favorites/boxes/${encodePathSegment(boxId)}`, { method: 'DELETE', auth: true })
}

export async function isBoxFavorited(boxId: string): Promise<boolean> {
  const set = await fetchFavoritedBoxIdSet()
  return set.has(boxId)
}

/** 批量收藏 / 取消（用于朝代矩阵：与收藏列表页同一 boxId 维度） */
export async function setBoxesFavorited(boxIds: string[], favorited: boolean): Promise<void> {
  const ids = [...new Set(boxIds.filter(Boolean))]
  if (!ids.length) return
  if (favorited) {
    await Promise.all(ids.map((id) => favoriteBox(id)))
  } else {
    await Promise.all(ids.map((id) => unfavoriteBox(id)))
  }
}

export function computeUnitFavoriteState(
  boxIds: string[],
  favorited: Set<string>
): { allFavorited: boolean; anyFavorited: boolean; favoritedCount: number } {
  const ids = boxIds.filter(Boolean)
  if (!ids.length) {
    return { allFavorited: false, anyFavorited: false, favoritedCount: 0 }
  }
  let favoritedCount = 0
  for (const id of ids) {
    if (favorited.has(id)) favoritedCount += 1
  }
  return {
    allFavorited: favoritedCount === ids.length,
    anyFavorited: favoritedCount > 0,
    favoritedCount,
  }
}
