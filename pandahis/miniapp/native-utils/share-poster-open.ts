import { hasToken, request } from './api'

export type ShareUserProfile = {
  nickname: string
  avatarUrl: string
}

export function formatShareExcerptDate(): string {
  const now = new Date()
  return `${now.getFullYear()}/${now.getMonth() + 1}/${now.getDate()}`
}

export async function fetchShareUserProfile(): Promise<ShareUserProfile> {
  if (!hasToken()) {
    return { nickname: '历史读者', avatarUrl: '' }
  }
  try {
    const meRes = await request<Record<string, unknown>>('/me', { auth: true })
    const raw = (meRes.data || {}) as Record<string, unknown>
    return {
      nickname: String(raw.nickname ?? raw['nickname'] ?? '历史读者'),
      avatarUrl: String(raw.avatarUrl ?? raw['avatar_url'] ?? ''),
    }
  } catch {
    return { nickname: '历史读者', avatarUrl: '' }
  }
}

export type SharePosterSheetState = {
  sharePosterVisible: boolean
  sharePosterQuote: string
  sharePosterSourceLine1: string
  sharePosterSourceLine2: string
  sharePosterUserName: string
  sharePosterUserAvatar: string
  sharePosterExcerptDate: string
}

export async function buildSharePosterSheetState(
  quoteText: string,
  sourceLine1: string,
  sourceLine2: string,
): Promise<SharePosterSheetState> {
  const profile = await fetchShareUserProfile()
  return {
    sharePosterVisible: true,
    sharePosterQuote: quoteText,
    sharePosterSourceLine1: sourceLine1,
    sharePosterSourceLine2: sourceLine2,
    sharePosterUserName: profile.nickname,
    sharePosterUserAvatar: profile.avatarUrl,
    sharePosterExcerptDate: formatShareExcerptDate(),
  }
}
