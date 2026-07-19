const assert = require('node:assert/strict')
const test = require('node:test')

const { extractUnitDynastyHint } = require('../native-utils/format.js')

test('从搜索路径提取朝代名', () => {
  assert.equal(extractUnitDynastyHint('华夏 › 春秋'), '春秋')
  assert.equal(extractUnitDynastyHint('华夏/战国'), '战国')
})
