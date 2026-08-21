const assert = require('node:assert/strict')
const test = require('node:test')

const {
  computeHeaderPadPx,
  computePageTopPadPx,
  computeNavTotalHeightPx,
} = require('../native-utils/nav-metrics.js')

test('computeNavTotalHeightPx 优先使用胶囊几何', () => {
  const originalMenu = global.wx?.getMenuButtonBoundingClientRect
  const originalSys = global.wx?.getSystemInfoSync
  global.wx = {
    getSystemInfoSync: () => ({ windowWidth: 375, statusBarHeight: 44 }),
    getMenuButtonBoundingClientRect: () => ({ top: 48, height: 32, width: 87, left: 278, right: 365, bottom: 80 }),
  }
  // gap = 48-44 = 4; content = 8+32 = 40; total = 44+40 = 84
  assert.equal(computeNavTotalHeightPx(), 84)
  assert.equal(computeHeaderPadPx(), 84)
  assert.equal(computePageTopPadPx(), 84)
  global.wx.getMenuButtonBoundingClientRect = originalMenu
  global.wx.getSystemInfoSync = originalSys
})

test('无胶囊时回退 statusBar + 88rpx', () => {
  global.wx = {
    getSystemInfoSync: () => ({ windowWidth: 375, statusBarHeight: 20 }),
    getMenuButtonBoundingClientRect: () => ({ top: 0, height: 0, width: 0, left: 0, right: 0, bottom: 0 }),
  }
  const expected = 20 + (88 * 375) / 750
  assert.equal(computeNavTotalHeightPx(), expected)
})
