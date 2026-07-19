const assert = require('node:assert/strict')
const test = require('node:test')

const {
  formatDynastyLoadError,
  formatEmptySwimError,
  formatUserFacingError,
} = require('../native-utils/load-error-message.js')

test('正式环境不向用户暴露后端和数据库诊断信息', () => {
  const message = formatDynastyLoadError(new Error('ECONNREFUSED 49.235.165.220'), false)

  assert.equal(message, '朝代数据暂时无法加载，请稍后重试。')
  assert.doesNotMatch(message, /ECONNREFUSED|后端|historical_/)
})

test('开发环境保留可操作的诊断信息', () => {
  const message = formatDynastyLoadError(new Error('INVALID_RESPONSE'), true)

  assert.match(message, /INVALID_RESPONSE/)
  assert.match(message, /historical_dynasty/)
})

test('正式环境空泳道提示保持用户友好', () => {
  const message = formatEmptySwimError(false)

  assert.equal(message, '该朝代画布暂时无法展示，请稍后重试。')
  assert.doesNotMatch(message, /swim-matrix|historical_/)
})

test('正式环境 toast 不暴露 API 诊断信息', () => {
  const message = formatUserFacingError(new Error('INTERNAL_ERROR 49.235.165.220'), false)

  assert.equal(message, '操作失败，请稍后重试')
})
