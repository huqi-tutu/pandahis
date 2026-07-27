const assert = require('node:assert/strict')
const test = require('node:test')

const { buildRows } = require('../native-utils/matrix/mock-home-matrix.js')
const { buildNavFromRows, findActiveNavIndex } = require('../native-utils/matrix/dynasty-nav-data.js')

test('晋朝索引应映射到矩阵中西晋行的 y 坐标，不能为 0', () => {
  const ratio = 375 / 750
  const layout = buildRows('huaxia', {})
  const { navItems } = buildNavFromRows(layout.rows, ratio, 'huaxia')
  const jin = navItems.find(item => item.label === '晋')
  assert.ok(jin)
  assert.ok(jin.yPx > 0, `晋 yPx 应大于 0，实际为 ${jin.yPx}`)
})

test('滚到五帝顶时索引不应误高亮晋', () => {
  const ratio = 375 / 750
  const layout = buildRows('huaxia', {})
  const { navItems } = buildNavFromRows(layout.rows, ratio, 'huaxia')
  assert.equal(findActiveNavIndex(0, navItems), -1)
  assert.equal(findActiveNavIndex(10, navItems), -1)
})

test('索引高亮应对应视口顶部已越过的最后一个朝代', () => {
  const ratio = 375 / 750
  const layout = buildRows('huaxia', {})
  const { navItems } = buildNavFromRows(layout.rows, ratio, 'huaxia')
  const labelAt = scrollTop => {
    const idx = findActiveNavIndex(scrollTop, navItems)
    return idx >= 0 ? navItems[idx].label : null
  }
  assert.equal(labelAt(108), '夏')
  assert.equal(labelAt(216), '商')
  assert.equal(labelAt(324), '周')
  assert.equal(labelAt(888), '汉')
})
