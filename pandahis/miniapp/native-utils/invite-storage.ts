/** 登录 POST /auth/wx-login 时附带，用于邀请归因 */
export const PENDING_INVITE_CODE_KEY = 'pendingInviteCode'

const INVITE_CODE_RE = /^[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{6,16}$/

function normalizeInviteCode(raw: unknown): string {
  if (raw == null) return ''
  const c = String(raw).trim()
  return c
}

export function stashInviteCode(code: string) {
  const c = normalizeInviteCode(code)
  if (!c) return
  try {
    wx.setStorageSync(PENDING_INVITE_CODE_KEY, c)
  } catch {
    // ignore
  }
}

/** 小程序码 scene：inviteCode=XXX 或纯邀请码 */
export function parseInviteCodeFromScene(scene?: string | number): string {
  if (scene == null || scene === '') return ''
  const raw =
    typeof scene === 'number'
      ? String(scene)
      : decodeURIComponent(String(scene).trim())
  if (!raw) return ''
  if (raw.includes('=')) {
    const q = raw.startsWith('?') ? raw.slice(1) : raw
    const params: Record<string, string> = {}
    for (const part of q.split('&')) {
      const i = part.indexOf('=')
      if (i < 0) continue
      const k = decodeURIComponent(part.slice(0, i))
      const v = decodeURIComponent(part.slice(i + 1))
      params[k] = v
    }
    return normalizeInviteCode(params.inviteCode || params.invite_code)
  }
  const bare = normalizeInviteCode(raw)
  return INVITE_CODE_RE.test(bare) ? bare : ''
}

export function stashInviteCodeFromQuery(query?: Record<string, string | undefined>) {
  if (!query) return
  const raw = query.inviteCode || query.invite_code
  const c = normalizeInviteCode(raw)
  if (c) stashInviteCode(c)
}

export function stashInviteFromLaunchOptions(
  options?: WechatMiniprogram.App.LaunchShowOption | null
) {
  if (!options) return
  stashInviteCodeFromQuery(options.query as Record<string, string | undefined>)
  const fromScene = parseInviteCodeFromScene(
    options.scene as string | number | undefined
  )
  if (fromScene) stashInviteCode(fromScene)
}

export function peekPendingInviteCode(): string {
  try {
    const v = wx.getStorageSync(PENDING_INVITE_CODE_KEY)
    return typeof v === 'string' ? v.trim() : ''
  } catch {
    return ''
  }
}

export function clearPendingInviteCode() {
  try {
    wx.removeStorageSync(PENDING_INVITE_CODE_KEY)
  } catch {
    // ignore
  }
}
