import { DEV_API_PORT, DEV_LAN_HOST } from './dev-config'

export type ApiResponse<T> = { code: string; message: string; requestId: string; data: T }

const PROD_BASE_URL = 'https://www.pandahis.com/api/v1'

function isDevtoolsClient(): boolean {
  try {
    const info = wx.getSystemInfoSync() as WechatMiniprogram.SystemInfo & {
      host?: { env?: string }
    }
    if (info.platform === 'devtools') return true
    if (info.host?.env === 'WeChatDevTools') return true
  } catch {
    // ignore
  }
  return false
}

/** 开发者工具用 localhost；真机用局域网 IP（见 dev-config.ts） */
function getLocalBaseUrl(): string {
  if (isDevtoolsClient()) {
    return `http://localhost:${DEV_API_PORT}/api/v1`
  }
  return `http://${DEV_LAN_HOST}:${DEV_API_PORT}/api/v1`
}

function isDevelopEnv(): boolean {
  try {
    return wx.getAccountInfoSync()?.miniProgram?.envVersion === 'develop'
  } catch {
    return true
  }
}

/** 开发版误把生产地址写入 storage 时，自动回退本地后端 */
function resolveStoredBaseUrl(stored: string): string {
  if (
    isDevelopEnv() &&
    (stored === PROD_BASE_URL || stored.includes('www.pandahis.com'))
  ) {
    return getLocalBaseUrl()
  }
  return stored
}

export function getBaseUrl(): string {
  if (isDevelopEnv()) {
    return getLocalBaseUrl()
  }
  const stored = String(wx.getStorageSync('apiBaseUrl') || '').trim()
  if (stored) return resolveStoredBaseUrl(stored)
  return PROD_BASE_URL
}

export function getToken(): string {
  return wx.getStorageSync('accessToken') || ''
}

/** 用户主动退出后为 true，阻止启动时静默自动登录 */
export const USER_LOGGED_OUT_KEY = 'userLoggedOut'

export function setToken(token: string) {
  wx.setStorageSync('accessToken', token)
  try {
    wx.removeStorageSync(USER_LOGGED_OUT_KEY)
  } catch {
    // ignore
  }
}

export function clearToken() {
  wx.removeStorageSync('accessToken')
  try {
    wx.setStorageSync(USER_LOGGED_OUT_KEY, '1')
  } catch {
    // ignore
  }
}

export function hasUserLoggedOut(): boolean {
  try {
    return wx.getStorageSync(USER_LOGGED_OUT_KEY) === '1'
  } catch {
    return false
  }
}

export function hasToken(): boolean {
  return Boolean(getToken())
}

export function request<T>(
  path: string,
  opts?: { method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'; data?: any; auth?: boolean }
): Promise<ApiResponse<T>> {
  if (opts?.auth && !getToken()) {
    return Promise.reject(new Error('UNAUTHORIZED'))
  }

  const baseUrl = getBaseUrl()
  const url = baseUrl.replace(/\/$/, '') + (path.startsWith('/') ? path : `/${path}`)
  const method = opts?.method || 'GET'
  const header: Record<string, string> = { 'content-type': 'application/json' }
  const token = getToken()
  if (token) header.Authorization = `Bearer ${token}`

  return new Promise<ApiResponse<T>>((resolve, reject) => {
    wx.request({
      url,
      method,
      data: opts?.data,
      header,
      // 首请求含连接池建连 + 远端 MySQL 时可能 >10s；与后端日志对齐，避免误报 timeout
      timeout: 60000,
      success(res) {
        const status = res.statusCode || 0
        const body = res.data as any
        if (status === 401 || body?.code === 'UNAUTHORIZED') {
          clearToken()
          reject(new Error('UNAUTHORIZED'))
          return
        }
        if (status >= 400) {
          const detail = {
            url,
            method,
            status,
            body,
          }
          console.error('[api] HTTP_ERROR', detail)
          const msg =
            (typeof body === 'object' && body && (body.message || body.code)) ||
            (typeof body === 'string' && body.slice(0, 200)) ||
            `HTTP_${status}`
          const err = new Error(msg)
          ;(err as any).detail = detail
          reject(err)
          return
        }
        if (!body || typeof body !== 'object') {
          const detail = { url, method, status, body }
          console.error('[api] INVALID_RESPONSE', detail)
          const err = new Error('INVALID_RESPONSE')
          ;(err as any).detail = detail
          reject(err)
          return
        }
        if (body.code && body.code !== 'OK') {
          const detail = { url, method, status, body }
          console.error('[api] API_ERROR', detail)
          const err = new Error(body.message || body.code)
          ;(err as any).detail = detail
          reject(err)
          return
        }
        resolve(body as ApiResponse<T>)
      },
      fail(err) {
        console.error('[api] REQUEST_FAIL', { url, method, err })
        const msg = (err as any)?.errMsg || (err as any)?.message || 'REQUEST_FAIL'
        const e = new Error(msg)
        ;(e as any).detail = { url, method, err }
        reject(e)
      },
    })
  })
}
