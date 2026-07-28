import { hasToken, request } from './api'
import { encodePathSegment } from './encode-path-segment'
import { ROUTES, navigateTo } from './router'

export function promptLoginForUnitFavorite() {
  wx.showModal({
    title: '需要登录',
    content: '登录后可收藏朝代，并在「我的收藏」中查看。',
    confirmText: '去登录',
    success: (r) => {
      if (r.confirm) navigateTo(ROUTES.login)
    },
  })
}

export async function fetchFavoritedUnitIdSet(): Promise<Set<string>> {
  if (!hasToken()) return new Set()
  const set = new Set<string>()
  try {
    let page = 1
    const pageSize = 50
    while (true) {
      const res = await request<{ items: { unitId: string }[]; total?: number }>(
        `/favorites/units?page=${page}&pageSize=${pageSize}`,
        { auth: true }
      )
      const items = res.data.items || []
      for (const x of items) {
        if (x.unitId) set.add(x.unitId)
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

export async function favoriteUnit(unitId: string): Promise<void> {
  await request(`/favorites/units/${encodePathSegment(unitId)}`, { method: 'POST', auth: true })
}

export async function unfavoriteUnit(unitId: string): Promise<void> {
  await request(`/favorites/units/${encodePathSegment(unitId)}`, { method: 'DELETE', auth: true })
}

export async function isUnitFavorited(unitId: string): Promise<boolean> {
  const set = await fetchFavoritedUnitIdSet()
  return set.has(unitId)
}
