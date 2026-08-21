const assert = require('node:assert/strict')
const test = require('node:test')

const {
  buildRows,
  buildAllExpanded,
  initialCiv,
} = require('../native-utils/matrix/mock-home-matrix.js')

function jinEmperorCardsAndOverlays() {
  const layout = buildRows('huaxia', buildAllExpanded(initialCiv))
  const cards = (layout.subCards || []).filter(s => s.containerId === '金')
  const overlays = (layout.overlays || []).filter(ov =>
    cards.some(card => ov.id === `${card.id}_chrome`)
  )
  return { cards, overlays }
}

test('金朝展开后帝王卡 chrome 贴顶且不超出卡片', () => {
  const { cards, overlays } = jinEmperorCardsAndOverlays()
  assert.equal(cards.length, 10)
  assert.equal(overlays.length, 10)

  cards.forEach(card => {
    const ov = overlays.find(item => item.id === `${card.id}_chrome`)
    assert.ok(ov, `${card.id} 缺少 chrome`)
    const topGap = ov.headerTop - card.top
    const chromeBottom = ov.headerTop + ov.headerHeight
    const cardBottom = card.top + card.h

    assert.ok(ov.isContainerEmperorCompact, `${card.id} 应为矮卡紧凑排版`)
    assert.ok(topGap >= 0 && topGap <= 2, `${card.id} 顶部间距应为 0–2rpx，实际 ${topGap}`)
    assert.ok(chromeBottom <= cardBottom, `${card.id} chrome 底 ${chromeBottom} 超出卡片底 ${cardBottom}`)
    assert.ok(ov.headerHeight >= card.h - 4, `${card.id} chrome 高度应接近卡片，避免把时间挤出`)
    assert.ok(ov.timeFontRpx <= 12, `${card.id} 矮卡时间字号应 ≤12rpx，实际 ${ov.timeFontRpx}`)
  })
})
