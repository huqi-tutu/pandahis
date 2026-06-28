// 本地调试：后端默认 http://localhost:8080/api/v1；真机预览请 wx.setStorageSync('apiBaseUrl', 'http://局域网IP:8080/api/v1')
const DEFAULT_BASE_URL = 'http://localhost:8080/api/v1'

function getBaseUrl() {
  try {
    const v = wx.getStorageSync('apiBaseUrl')
    return v || DEFAULT_BASE_URL
  } catch {
    return DEFAULT_BASE_URL
  }
}

function request(path, opts) {
  const baseUrl = getBaseUrl()
  const url = baseUrl.replace(/\/$/, '') + (path.startsWith('/') ? path : `/${path}`)
  const method = (opts && opts.method) || 'GET'
  return new Promise((resolve, reject) => {
    wx.request({
      url,
      method,
      data: opts && opts.data,
      header: { 'content-type': 'application/json' },
      timeout: 60000,
      success(res) {
        const status = res.statusCode || 0
        const body = res.data
        if (status >= 400 || !body || typeof body !== 'object') {
          reject(new Error((body && body.message) || `HTTP_${status}`))
          return
        }
        if (body.code && body.code !== 'OK') {
          reject(new Error(body.message || body.code))
          return
        }
        resolve(body)
      },
      fail(err) {
        reject(new Error((err && err.errMsg) || 'REQUEST_FAIL'))
      },
    })
  })
}

module.exports = { request, getBaseUrl }
