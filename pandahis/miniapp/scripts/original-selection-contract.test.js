const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')

function source(relative) {
  return fs.readFileSync(path.join(__dirname, '..', relative), 'utf8')
}

test('打开原文半屏时先清掉详情选区与操作条', () => {
  const page = source('package-graph/pages/box-detail/index.ts')
  const goOriginal = page.match(/goOriginal\(\)\s*\{([\s\S]*?)\n\s*\},\n\s*closeOriginal/)
  assert.ok(goOriginal)
  assert.match(goOriginal[1], /this\.hideSelectionBar\(\)/)
})

test('关闭原文半屏时清掉半屏选区与操作条', () => {
  const page = source('package-graph/pages/box-detail/index.ts')
  const closeOriginal = page.match(/closeOriginal\(\)\s*\{([\s\S]*?)\n\s*\},/)
  assert.ok(closeOriginal)
  assert.match(closeOriginal[1], /this\.hideSelectionBar\(\)/)
})

test('原文半屏正文可长按选中，操作条不含笔记', () => {
  const wxml = source('package-graph/pages/box-detail/index.wxml')
  assert.match(wxml, /id="originalBodySelection"/)
  assert.match(wxml, /bindselectionchange="onOriginalSelectionChange"/)
  assert.match(wxml, /showNote="\{\{!showOriginal\}\}"/)
  assert.match(wxml, /id="originalBodySelection"[\s\S]*user-select/)
})

test('原文选中纠错使用独立来源 box_original_selection', () => {
  const page = source('package-graph/pages/box-detail/index.ts')
  assert.match(page, /onOriginalSelectionChange/)
  assert.match(page, /correctionSourceType:\s*'box_original_selection'/)
  assert.match(page, /onOriginalSelectionChange[\s\S]*buttonCount:\s*4/)
})

test('史略详情页不跳转独立原文页', () => {
  const page = source('package-graph/pages/box-detail/index.ts')
  assert.doesNotMatch(page, /ROUTES\.originalText/)
})

test('从母本原文纠错跳回时自动打开半屏', () => {
  const page = source('package-graph/pages/box-detail/index.ts')
  assert.match(page, /query\.openOriginal === '1'/)
  assert.match(page, /_openOriginalOnReady/)
})
