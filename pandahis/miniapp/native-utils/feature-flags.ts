import { request } from './api'

/** 请求失败时的兜底：默认关闭文明切换 */
const DEFAULT_FLAGS: FeatureFlags = { civSwitchEnabled: false }

export const TOAST_CIV_LOCKED = '即将上线，敬请期待'

export type FeatureFlags = {
  civSwitchEnabled: boolean
}

export function getFeatureFlags(): FeatureFlags {
  try {
    const app = getApp<IAppOption>()
    return (app?.globalData?.featureFlags as FeatureFlags | undefined) || DEFAULT_FLAGS
  } catch {
    return DEFAULT_FLAGS
  }
}

export function isCivSwitchEnabled(): boolean {
  return getFeatureFlags().civSwitchEnabled !== false
}

export async function loadFeatureFlags(): Promise<FeatureFlags> {
  try {
    const res = await request<FeatureFlags>('/config/features')
    const raw = res.data || ({} as FeatureFlags)
    const normalized: FeatureFlags = {
      civSwitchEnabled: raw.civSwitchEnabled !== false,
    }
    try {
      const app = getApp<IAppOption>()
      if (app) {
        app.globalData = app.globalData || {}
        app.globalData.featureFlags = normalized
      }
    } catch {
      // ignore
    }
    return normalized
  } catch {
    return DEFAULT_FLAGS
  }
}

export function toastCivLocked(): void {
  wx.showToast({ title: TOAST_CIV_LOCKED, icon: 'none' })
}

export function isHuaxiaCivSlug(slug: string | null | undefined): boolean {
  return String(slug || '').trim() === 'huaxia'
}

export function isHuaxiaUnitId(unitId: string | null | undefined): boolean {
  const id = String(unitId || '').trim().toUpperCase()
  if (!id) return true
  return id.startsWith('CD_HX_') || id === 'CD_HX'
}

interface IAppOption {
  globalData?: {
    featureFlags?: FeatureFlags
  }
}
