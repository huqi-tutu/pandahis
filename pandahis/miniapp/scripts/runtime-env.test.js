const assert = require('node:assert/strict')
const test = require('node:test')

const {
  getEnvVersion,
  isDevelopEnv,
  isDevtoolsClient,
} = require('../native-utils/runtime-env.js')

test.afterEach(() => {
  delete global.wx
})

test('正确识别开发环境', () => {
  global.wx = {
    getAccountInfoSync: () => ({ miniProgram: { envVersion: 'develop' } }),
  }

  assert.equal(getEnvVersion(), 'develop')
  assert.equal(isDevelopEnv(), true)
})

test('环境 API 异常时按非开发环境处理', () => {
  global.wx = {
    getAccountInfoSync: () => {
      throw new Error('account info unavailable')
    },
  }

  assert.equal(getEnvVersion(), '')
  assert.equal(isDevelopEnv(), false)
})

test('识别开发者工具客户端', () => {
  global.wx = {
    getAccountInfoSync: () => ({ miniProgram: { envVersion: 'develop' } }),
    getDeviceInfo: () => ({ platform: 'devtools' }),
    getAppBaseInfo: () => ({}),
  }

  assert.equal(isDevtoolsClient(), true)
})

test('识别 host.env 形式的开发者工具', () => {
  global.wx = {
    getAccountInfoSync: () => ({ miniProgram: { envVersion: 'develop' } }),
    getDeviceInfo: () => ({ platform: 'ios' }),
    getAppBaseInfo: () => ({ host: { env: 'WeChatDevTools' } }),
  }

  assert.equal(isDevtoolsClient(), true)
})
