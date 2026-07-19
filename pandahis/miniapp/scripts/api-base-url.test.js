const assert = require('node:assert/strict')
const test = require('node:test')

const { ApiError, getBaseUrl, request } = require('../native-utils/api.js')
const { DEV_API_PORT } = require('../native-utils/dev-config.js')

const PROD_BASE_URL = 'https://www.pandahis.com/api/v1'

function mockWx({
  platform,
  envVersion = 'develop',
  storedBaseUrl = '',
  accountInfoThrows = false,
}) {
  global.wx = {
    getSystemInfoSync: () => ({ platform }),
    getAccountInfoSync: () => {
      if (accountInfoThrows) throw new Error('account info unavailable')
      return { miniProgram: { envVersion } }
    },
    getStorageSync: (key) => (key === 'apiBaseUrl' ? storedBaseUrl : ''),
  }
}

test.afterEach(() => {
  delete global.wx
})

test('开发者工具默认连接本机后端', () => {
  mockWx({ platform: 'devtools' })

  assert.equal(getBaseUrl(), `http://localhost:${DEV_API_PORT}/api/v1`)
})

test('真机开发版默认连接生产后端，避免局域网 IP 变化导致空白', () => {
  mockWx({ platform: 'ios' })

  assert.equal(getBaseUrl(), PROD_BASE_URL)
})

test('真机开发版允许通过 storage 显式连接局域网后端', () => {
  mockWx({
    platform: 'ios',
    storedBaseUrl: 'http://192.168.0.107:8080/api/v1',
  })

  assert.equal(getBaseUrl(), 'http://192.168.0.107:8080/api/v1')
})

test('正式版默认连接生产后端', () => {
  mockWx({ platform: 'ios', envVersion: 'release' })

  assert.equal(getBaseUrl(), PROD_BASE_URL)
})

test('体验版忽略遗留的局域网地址', () => {
  mockWx({
    platform: 'ios',
    envVersion: 'trial',
    storedBaseUrl: 'http://192.168.0.107:8080/api/v1',
  })

  assert.equal(getBaseUrl(), PROD_BASE_URL)
})

test('无法识别运行环境时安全回退生产后端', () => {
  mockWx({ platform: 'ios', accountInfoThrows: true })

  assert.equal(getBaseUrl(), PROD_BASE_URL)
})

test('开发版拒绝不安全的 storage 地址', () => {
  mockWx({
    platform: 'ios',
    storedBaseUrl: 'javascript:alert(1)',
  })

  assert.equal(getBaseUrl(), PROD_BASE_URL)
})

test('HTTP 失败返回带结构化详情的 ApiError', async () => {
  global.wx = {
    getAccountInfoSync: () => ({ miniProgram: { envVersion: 'release' } }),
    getStorageSync: () => '',
    request: ({ success }) => {
      success({
        statusCode: 500,
        data: { code: 'INTERNAL_ERROR', message: '服务暂时不可用' },
      })
    },
  }

  await assert.rejects(request('/units/test'), (error) => {
    assert.ok(error instanceof ApiError)
    assert.equal(error.detail.status, 500)
    assert.equal(error.detail.method, 'GET')
    assert.match(error.detail.url, /\/units\/test$/)
    return true
  })
})
