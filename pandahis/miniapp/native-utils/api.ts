import { DEV_API_PORT } from './dev-config'
import { getEnvVersion, isDevtoolsClient } from './runtime-env'

export type ApiResponse<T> = { code: string; message: string; requestId: string; data: T }

export type ApiErrorDetail = {
  url: string
  method: string
  status?: number
  body?: unknown
  err?: unknown
}

export class ApiError extends Error {
  readonly detail: ApiErrorDetail

  constructor(message: string, detail: ApiErrorDetail) {
    super(message)
    this.name = 'ApiError'
    this.detail = detail
  }
}

const PROD_BASE_URL = 'https://www.pandahis.com/api/v1'

function normalizeDevelopBaseUrl(value: unknown): string {
  const url = String(value || '').trim().replace(/\/$/, '')
  if (!url) return ''
  if (/^https:\/\/[a-z0-9.-]+(?::\d+)?(?:\/.*)?$/i.test(url)) return url
  const privateHttp =
    /^http:\/\/(?:localhost|127(?:\.\d{1,3}){3}|10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})(?::\d+)?(?:\/.*)?$/i
  return privateHttp.test(url) ? url : ''
}

export function getBaseUrl(): string {
  if (getEnvVersion() === 'develop') {
    const stored = normalizeDevelopBaseUrl(wx.getStorageSync('apiBaseUrl'))
    if (stored) return stored
    // 开发者工具可直接访问本机；真机预览默认走生产 HTTPS，
    // 避免 DHCP 改变开发机局域网 IP 后整页数据加载失败。
    if (isDevtoolsClient()) {
      return `http://localhost:${DEV_API_PORT}/api/v1`
    }
  }
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
  opts?: { method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'; data?: any; auth?: boolean }
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
      method: method as WechatMiniprogram.RequestOption['method'],
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
          reject(new ApiError(String(msg), detail))
          return
        }
        if (!body || typeof body !== 'object') {
          const detail = { url, method, status, body }
          console.error('[api] INVALID_RESPONSE', detail)
          reject(new ApiError('INVALID_RESPONSE', detail))
          return
        }
        if (body.code && body.code !== 'OK') {
          const detail = { url, method, status, body }
          console.error('[api] API_ERROR', detail)
          reject(new ApiError(String(body.message || body.code), detail))
          return
        }
        resolve(body as ApiResponse<T>)
      },
      fail(err) {
        console.error('[api] REQUEST_FAIL', { url, method, err })
        const msg = err?.errMsg || 'REQUEST_FAIL'
        reject(new ApiError(msg, { url, method, err }))
      },
    })
  })
}
