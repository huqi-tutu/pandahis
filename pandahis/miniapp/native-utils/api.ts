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

/** 本机联调地址（需在设置或登录页开发区显式启用） */
export const LOCAL_DEV_BASE_URL = `http://localhost:${DEV_API_PORT}/api/v1`

function normalizeDevelopBaseUrl(value: unknown): string {
  const url = String(value || '').trim().replace(/\/$/, '')
  if (!url) return ''
  if (/^https:\/\/[a-z0-9.-]+(?::\d+)?(?:\/.*)?$/i.test(url)) return url
  const privateHttp =
    /^http:\/\/(?:localhost|127(?:\.\d{1,3}){3}|10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})(?::\d+)?(?:\/.*)?$/i
  return privateHttp.test(url) ? url : ''
}

function isPrivateHttpBaseUrl(url: string): boolean {
  return /^http:\/\//i.test(url)
}

/** 真机预览无法稳定访问本机/局域网 HTTP，统一走生产 */
function shouldIgnoreStoredBaseOnClient(stored: string): boolean {
  if (isDevtoolsClient()) return false
  if (/localhost|127\.0\.0\.1/i.test(stored)) return true
  return isPrivateHttpBaseUrl(stored)
}

export function getBaseUrl(): string {
  const envVersion = getEnvVersion()
  if (envVersion === 'develop') {
    const stored = normalizeDevelopBaseUrl(wx.getStorageSync('apiBaseUrl'))
    if (stored) {
      if (shouldIgnoreStoredBaseOnClient(stored)) {
        return PROD_BASE_URL
      }
      return stored
    }
    return PROD_BASE_URL
  }
  return PROD_BASE_URL
}

/** 设置页连通性检测（基础） */
export function probeApiHealth(): Promise<ApiResponse<{ status: string }>> {
  return request<{ status: string }>('/health')
}

export type ApiProbeStage = 'health' | 'auth' | 'unit' | 'swim-matrix'

export type ApiProbeResult = {
  ok: boolean
  stage: ApiProbeStage
  error?: unknown
}

/** 分阶段检测：health → 登录接口 → 朝代概要 → 朝代画布 */
export async function probeApiConnectivity(): Promise<ApiProbeResult> {
  try {
    await probeApiHealth()
  } catch (error) {
    return { ok: false, stage: 'health', error }
  }
  try {
    await request('/auth/wx-login', {
      method: 'POST',
      data: { code: 'connectivity-probe-invalid' },
    })
  } catch (error) {
    const msg = error instanceof ApiError ? error.message : String(error)
    // 服务端可达且校验 code：说明登录链路通（与 wx.login 后 POST 同域名同路径）
    if (/invalid|expired|wx\.login/i.test(msg)) {
      // continue
    } else {
      return { ok: false, stage: 'auth', error }
    }
  }
  try {
    await request('/units/CD_HX_XIA')
  } catch (error) {
    return { ok: false, stage: 'unit', error }
  }
  try {
    await request('/units/CD_HX_XIA/swim-matrix')
  } catch (error) {
    return { ok: false, stage: 'swim-matrix', error }
  }
  return { ok: true, stage: 'swim-matrix' }
}

function parseResponseBody(raw: unknown): any {
  if (raw == null) return null
  if (typeof raw === 'object') return raw
  if (typeof raw === 'string') {
    const text = raw.trim()
    if (!text) return null
    try {
      return JSON.parse(text)
    } catch {
      return null
    }
  }
  return null
}

/** 公开内容 GET 不附带 token，避免登录态触发服务端未迁移的用户表查询导致 500 */
function isPublicContentPath(path: string): boolean {
  const p = path.split('?')[0]
  // /search、/search/suggest 为可选登录接口：有 token 时必须带上，才能读写搜索历史
  return (
    /^\/units\//.test(p)
    || /^\/boxes\//.test(p)
    || p.startsWith('/home/')
    || p === '/health'
    || p.startsWith('/membership/plans')
    || p.startsWith('/config/')
    || p.startsWith('/dictionary/')
    || p.startsWith('/wikipedia/')
  )
}

function shouldAttachBearerToken(path: string, method: string, auth?: boolean): boolean {
  if (!getToken()) return false
  if (auth) return true
  if (method === 'GET' && isPublicContentPath(path)) return false
  return true
}

function buildRequestHeaders(
  path: string,
  method: string,
  auth?: boolean,
  contentType = 'application/json'
): Record<string, string> {
  const header: Record<string, string> = { 'content-type': contentType }
  const envVersion = getEnvVersion()
  if (envVersion) header['X-Miniapp-Env'] = envVersion
  if (shouldAttachBearerToken(path, method, auth)) {
    header.Authorization = `Bearer ${getToken()}`
  }
  return header
}

export function setDevelopApiBaseUrl(url: string) {
  const normalized = normalizeDevelopBaseUrl(url)
  if (!normalized) {
    throw new Error('API 地址无效')
  }
  wx.setStorageSync('apiBaseUrl', normalized)
}

export function clearDevelopApiBaseUrl() {
  try {
    wx.removeStorageSync('apiBaseUrl')
  } catch {
    // ignore
  }
}

export function useProductionApi() {
  clearDevelopApiBaseUrl()
}

export function useLocalDevApi() {
  setDevelopApiBaseUrl(LOCAL_DEV_BASE_URL)
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

/** 仅清除令牌（401 / 过期时用这个，不阻断后续静默登录） */
export function clearAccessToken() {
  try {
    wx.removeStorageSync('accessToken')
  } catch {
    // ignore
  }
}

/** 用户主动退出：清令牌并标记不再静默登录 */
export function clearToken() {
  clearAccessToken()
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
  opts?: {
    method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
    data?: any
    auth?: boolean
    /** 为 true 时 401 仅拒绝 Promise，不清除本地 token（用于会员/热力图等并行次要请求） */
    softAuth?: boolean
  }
): Promise<ApiResponse<T>> {
  if (opts?.auth && !getToken()) {
    return Promise.reject(new Error('UNAUTHORIZED'))
  }

  const baseUrl = getBaseUrl()
  const url = baseUrl.replace(/\/$/, '') + (path.startsWith('/') ? path : `/${path}`)
  const method = opts?.method || 'GET'
  const header = buildRequestHeaders(path, method, opts?.auth)

  return new Promise<ApiResponse<T>>((resolve, reject) => {
    wx.request({
      url,
      method: method as WechatMiniprogram.RequestOption['method'],
      data: opts?.data,
      header,
      enableHttp2: false,
      enableQuic: false,
      // 首请求含连接池建连 + 远端 MySQL 时可能 >10s；与后端日志对齐，避免误报 timeout
      timeout: 60000,
      success(res) {
        const status = res.statusCode || 0
        const body = parseResponseBody(res.data)
        if (status === 401 || body?.code === 'UNAUTHORIZED') {
          if (!opts?.softAuth) {
            clearAccessToken()
          }
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

/** 上传本地文件（如头像），字段名默认 `file` */
export function uploadFile<T>(
  path: string,
  filePath: string,
  opts?: { name?: string; formData?: Record<string, string> }
): Promise<ApiResponse<T>> {
  if (!getToken()) {
    return Promise.reject(new Error('UNAUTHORIZED'))
  }

  const baseUrl = getBaseUrl()
  const url = baseUrl.replace(/\/$/, '') + (path.startsWith('/') ? path : `/${path}`)
  const name = opts?.name || 'file'
  const header = buildRequestHeaders(path, 'POST', true, '')
  delete header['content-type']

  return new Promise<ApiResponse<T>>((resolve, reject) => {
    wx.uploadFile({
      url,
      filePath,
      name,
      formData: opts?.formData,
      header,
      timeout: 60000,
      success(res) {
        const status = res.statusCode || 0
        let body: any = null
        try {
          body = typeof res.data === 'string' ? JSON.parse(res.data) : res.data
        } catch {
          body = res.data
        }
        if (status === 401 || body?.code === 'UNAUTHORIZED') {
          clearAccessToken()
          reject(new Error('UNAUTHORIZED'))
          return
        }
        if (status >= 400) {
          const detail = { url, method: 'POST', status, body }
          console.error('[api] UPLOAD_HTTP_ERROR', detail)
          const msg =
            (typeof body === 'object' && body && (body.message || body.code)) ||
            `HTTP_${status}`
          reject(new ApiError(String(msg), detail))
          return
        }
        if (!body || typeof body !== 'object') {
          reject(new ApiError('INVALID_RESPONSE', { url, method: 'POST', status, body }))
          return
        }
        if (body.code && body.code !== 'OK') {
          reject(new ApiError(String(body.message || body.code), { url, method: 'POST', status, body }))
          return
        }
        resolve(body as ApiResponse<T>)
      },
      fail(err) {
        console.error('[api] UPLOAD_FAIL', { url, err })
        reject(new ApiError(err?.errMsg || 'UPLOAD_FAIL', { url, method: 'POST', err }))
      },
    })
  })
}
