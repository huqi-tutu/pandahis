const test = require('node:test')
const assert = require('node:assert/strict')

const {
  countOffscreenBottom,
  countOffscreenRight,
  dedupeHintItems,
} = require('../native-utils/offscreen-hints')

test('counts fully and partially hidden items to the right', () => {
  const items = [
    { id: 'visible', rightRpx: 480, bottomRpx: 100, weight: 1 },
    { id: 'partial', rightRpx: 540, bottomRpx: 100, weight: 1 },
    { id: 'bucket', rightRpx: 720, bottomRpx: 100, weight: 6 },
  ]

  assert.equal(countOffscreenRight(items, 500, 16), 7)
})

test('uses a tolerance to avoid flicker at the viewport edge', () => {
  const items = [{ id: 'edge', rightRpx: 512, bottomRpx: 100, weight: 1 }]

  assert.equal(countOffscreenRight(items, 500, 16), 0)
})

test('counts weighted items below the visible canvas area', () => {
  const items = [
    { id: 'visible', rightRpx: 100, bottomRpx: 280, weight: 1 },
    { id: 'below', rightRpx: 100, bottomRpx: 420, weight: 1 },
    { id: 'bucket', rightRpx: 100, bottomRpx: 500, weight: 4 },
  ]

  assert.equal(countOffscreenBottom(items, 300, 16), 5)
})

test('deduplicates the same history item across collections', () => {
  const items = dedupeHintItems([
    { id: 'same', rightRpx: 200, bottomRpx: 100, weight: 1 },
    { id: 'same', rightRpx: 240, bottomRpx: 120, weight: 1 },
    { id: 'other', rightRpx: 300, bottomRpx: 140, weight: 1 },
  ])

  assert.deepEqual(items.map((item) => item.id), ['same', 'other'])
  assert.equal(items[0].rightRpx, 240)
})
