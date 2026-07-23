import { hasToken, request } from './api'
import { encodePathSegment } from './encode-path-segment'
import { ROUTES, navigateTo } from './router'

export function promptLoginForReadComplete() {
  wx.showModal({
    title: '需要登录',
    content: '登录后可标记读完，并在「我的」中查看已读完列表。',
    confirmText: '去登录',
    success: (r) => {
      if (r.confirm) navigateTo(ROUTES.login)
    },
  })
}

export async function markBoxReadComplete(boxId: string): Promise<void> {
  await request(`/boxes/${encodePathSegment(boxId)}/read-complete`, { method: 'PUT', auth: true })
}

export async function unmarkBoxReadComplete(boxId: string): Promise<void> {
  await request(`/boxes/${encodePathSegment(boxId)}/read-complete`, { method: 'DELETE', auth: true })
}
