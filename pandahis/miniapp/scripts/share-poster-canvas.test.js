const assert = require('node:assert/strict')
const test = require('node:test')

function makeContext(events, id) {
  const ctx = {
    measureText(text) { events.push(['measureText', id, text]); return { width: [...String(text)].length * 34 } },
    scale(x, y) { events.push(['scale', id, x, y]) },
    fillRect() {}, save() {}, restore() {}, beginPath() {}, arc() {}, clip() {}, drawImage() {}, fill() {},
    moveTo(x, y) { events.push(['moveTo', id, x, y]) }, lineTo() {}, stroke() {}, arcTo() {}, closePath() {},
    fillText(text, x, y) { events.push(['fillText', id, text, x, y]) },
  }
  return ctx
}

test('真实海报绘制在最终尺寸后重取 context 并安全容纳二十行与来源', async () => {
  const events = []
  let width = 0
  let height = 0
  let contextCount = 0
  const canvas = {
    get width() { return width },
    set width(value) { width = value; events.push(['width', value]) },
    get height() { return height },
    set height(value) { height = value; events.push(['height', value]) },
    getContext() { contextCount += 1; events.push(['getContext', contextCount]); return makeContext(events, contextCount) },
    createImage() {
      const image = {}
      Object.defineProperty(image, 'src', { set() { queueMicrotask(() => image.onerror && image.onerror(new Error('mock'))) } })
      return image
    },
  }
  global.wx = {
    canvasToTempFilePath({ success }) { success({ tempFilePath: '/tmp/poster.png' }) },
  }
  const { renderSharePosterToCanvas } = require('../native-utils/share-poster-canvas.js')
  const result = await renderSharePosterToCanvas(canvas, {
    quoteText: '史'.repeat(500),
    sourceLine1: '《史记·五帝本纪》'.repeat(8),
    userName: '读者',
    excerptDate: '2026/7/24',
  })
  assert.equal(result, '/tmp/poster.png')
  assert.equal(width, 1500)
  assert.ok(height > 2300)
  assert.ok(contextCount >= 2)
  const finalHeightIndex = events.map(e => e[0]).lastIndexOf('height')
  const finalScaleIndex = events.findIndex((e, i) => i > finalHeightIndex && e[0] === 'scale')
  assert.ok(finalScaleIndex > finalHeightIndex)
  const finalContextId = events[finalScaleIndex][1]
  const footerY = events.find(e => e[0] === 'moveTo' && e[1] === finalContextId)[3]
  const contentY = events
    .filter(e => e[0] === 'fillText' && e[1] === finalContextId && e[4] < footerY)
    .map(e => e[4])
  assert.ok(contentY.length >= 23)
  assert.ok(Math.max(...contentY) < footerY)
})
