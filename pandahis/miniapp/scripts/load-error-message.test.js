const assert = require('node:assert/strict')
const test = require('node:test')

const { ApiError } = require('../native-utils/api.js')
const { formatApiRequestError } = require('../native-utils/load-error-message.js')

test.afterEach(() => {
  delete global.wx
})

test('识别微信合法域名拦截', () => {
  global.wx = {
    getDeviceInfo: () => ({ platform: 'ios' }),
    getAppBaseInfo: () => ({}),
  }
  const err = new ApiError('request:fail url not in domain list', {
    url: 'https://www.pandahis.com/api/v1/health',
    method: 'GET',
    err: { errMsg: 'request:fail url not in domain list' },
  })
  const msg = formatApiRequestError(err)
  assert.match(msg, /合法域名/)
  assert.match(msg, /pandahis/)
})

test('真机连接失败给出设置指引', () => {
  global.wx = {
    getDeviceInfo: () => ({ platform: 'android' }),
    getAppBaseInfo: () => ({}),
  }
  const err = new ApiError('request:fail', {
    url: 'http://192.168.0.1:8080/api/v1/health',
    method: 'GET',
    err: { errMsg: 'request:fail -2:net::ERR_CONNECTION_REFUSED' },
  })
  const msg = formatApiRequestError(err)
  assert.match(msg, /设置/)
})

test('开发版预览显示具体错误摘要', () => {
  global.wx = {
    getDeviceInfo: () => ({ platform: 'ios' }),
    getAppBaseInfo: () => ({}),
    getAccountInfoSync: () => ({ miniProgram: { envVersion: 'develop' } }),
  }
  const err = new ApiError('unit not found', {
    url: 'https://www.pandahis.com/api/v1/units/HX-X',
    method: 'GET',
    status: 200,
    body: { code: 'NOT_FOUND' },
  })
  const msg = formatApiRequestError(err)
  assert.match(msg, /未找到该朝代/)
})

test('resolveDetailUnitIds 优先 CD 标准 ID', () => {
  const { resolveDetailUnitIds } = require('../pages/home/matrix-adapter.js')
  const ids = resolveDetailUnitIds('HX-X', '夏')
  assert.deepEqual(ids, ['HX-X', 'CD_HX_XIA'])
})
