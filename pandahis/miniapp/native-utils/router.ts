export const ROUTES = {
  home: '/pages/home/index',
  mine: '/pages/my/index',
  search: '/pages/search/index',
  searchResult: '/pages/search-result/index',
  unitDetail: '/pages/unit-detail/index',
  boxDetail: '/pages/box-detail/index',
  login: '/pages/login/index',
  invite: '/pages/invite/index',
  inviteAccept: '/pages/invite-accept/index',
  favorites: '/pages/favorites/index',
  footprints: '/pages/footprints/index',
  originalText: '/pages/original-text/index',
  settings: '/pages/settings/index',
  about: '/pages/about/index',
  membership: '/pages/membership/index',
  inviteAssist: '/pages/invite-assist/index',
  profileEdit: '/pages/profile-edit/index',
  relationDetail: '/pages/relation-detail/index',
  critiqueDetail: '/pages/critique-detail/index',
  relicDetail: '/pages/relic-detail/index',
} as const

export const SUPPORT_EMAIL = 'support@pandahis.com'

export function buildUrl(path: string, query?: Record<string, any>) {
  if (!query) return path
  const pairs = Object.keys(query)
    .sort()
    .flatMap((k) => {
      const v = query[k]
      if (v === undefined || v === null || v === '') return []
      return [`${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`]
    })
  return pairs.length ? `${path}?${pairs.join('&')}` : path
}

export function navigateTo(path: string, query?: Record<string, any>) {
  wx.navigateTo({
    url: buildUrl(path, query),
    fail(err) {
      console.error('[navigateTo]', buildUrl(path, query), err)
      wx.showToast({ title: '页面打开失败', icon: 'none' })
    },
  })
}

export function redirectTo(path: string, query?: Record<string, any>) {
  wx.redirectTo({ url: buildUrl(path, query) })
}

