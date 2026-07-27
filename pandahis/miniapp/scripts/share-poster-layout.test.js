const assert = require('node:assert/strict')
const test = require('node:test')

const { calculateSharePosterLayout, MAX_QUOTE_LINES } = require('../native-utils/share-poster-layout.js')

test('正文最多允许二十行', () => {
  assert.equal(MAX_QUOTE_LINES, 20)
})

test('长正文按实际行数增高且来源与分割线保持安全间距', () => {
  const short = calculateSharePosterLayout(3, 1)
  const long = calculateSharePosterLayout(20, 2)
  assert.equal(short.posterHeight, 1150)
  assert.ok(long.posterHeight > short.posterHeight)
  assert.ok(long.footerTop - long.sourceBottom >= 64)
})

test('布局边界会夹紧到合法行数', () => {
  const layout = calculateSharePosterLayout(200, -2)
  assert.equal(layout.quoteLineCount, 20)
  assert.equal(layout.pathLineCount, 0)
  assert.ok(Number.isFinite(layout.posterHeight))
})
