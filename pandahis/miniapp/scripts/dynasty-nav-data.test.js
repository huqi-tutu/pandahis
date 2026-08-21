const assert = require('node:assert/strict')
const test = require('node:test')

const { buildRows } = require('../native-utils/matrix/mock-home-matrix.js')
const {
  buildNavFromRows,
  findActiveNavIndex,
  calcMaxScrollPx,
  resolveNavSnapTopPx,
} = require('../native-utils/matrix/dynasty-nav-data.js')

function collapsedNavCtx(matrixHeight, bottomPadRpx) {
  const ratio = 375 / 750
  const layout = buildRows('huaxia', {})
  const { navItems } = buildNavFromRows(layout.rows, ratio, 'huaxia')
  return {
    ratio,
    layout,
    navItems,
    ctx: {
      ratio,
      matrixBlocks: layout.blocks || [],
      navItems,
      matrixRows: layout.rows || [],
      matrixTotalH: layout.totalH || 0,
      matrixScrollBottomPad: bottomPadRpx,
      matrixHeight,
      scrollInsetPx: 8,
    },
  }
}

function collapsedMingQingRangePx(layout, ratio) {
  const ming = (layout.blocks || []).find(b => b.dynasty === '明' && b.kind === 'dynasty')
  const qing = (layout.blocks || []).find(b => b.dynasty === '清' && b.kind === 'dynasty')
  assert.ok(ming && qing, '折叠态应有明、清朝代卡')
  return {
    mingTop: ming.top * ratio,
    qingBottom: (qing.top + qing.h) * ratio,
  }
}

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

test('折叠态选中明或清时，明清两张卡都应完整落在视口内', () => {
  const matrixHeight = 560
  const bottomPadRpx = 144
  const { layout, ctx } = collapsedNavCtx(matrixHeight, bottomPadRpx)
  const { mingTop, qingBottom } = collapsedMingQingRangePx(layout, ctx.ratio)

  ;['明', '清'].forEach(key => {
    const snap = resolveNavSnapTopPx(key, ctx)
    assert.ok(snap <= mingTop + 1, `${key} 不应把明卡顶滚出视口，snap=${snap} mingTop=${mingTop}`)
    assert.ok(
      snap + matrixHeight >= qingBottom - 1,
      `${key} 应让清卡底露出来，snap=${snap} visibleEnd=${snap + matrixHeight} qingBottom=${qingBottom}`
    )
  })
})

test('折叠态在最大滚动处仍能单独选中明和清', () => {
  const matrixHeight = 560
  const bottomPadRpx = 144
  const { navItems, ctx } = collapsedNavCtx(matrixHeight, bottomPadRpx)
  const maxScroll = calcMaxScrollPx(ctx.matrixTotalH, ctx.matrixScrollBottomPad, ctx.ratio, matrixHeight)

  const qingSnap = resolveNavSnapTopPx('清', ctx)
  const qingIdx = findActiveNavIndex(qingSnap, navItems, 32, { pinnedKey: '清', maxScroll })
  assert.equal(navItems[qingIdx].label, '清')

  const mingSnap = resolveNavSnapTopPx('明', ctx)
  const mingIdx = findActiveNavIndex(mingSnap, navItems, 32, { pinnedKey: '明', maxScroll })
  assert.equal(navItems[mingIdx].label, '明')
})

test('最大滚动距离应计入底部垫高，避免末代卡片被底栏挡住', () => {
  const ratio = 0.5
  const totalH = 4744
  const pad = 144
  const viewport = 560
  const withoutPad = Math.max(0, totalH * ratio - viewport)
  const withPad = calcMaxScrollPx(totalH, pad, ratio, viewport)
  assert.ok(withPad > withoutPad, `含垫高的 maxScroll 应更大，实际 ${withPad} vs ${withoutPad}`)
  assert.equal(withPad, (totalH + pad) * ratio - viewport)
})
