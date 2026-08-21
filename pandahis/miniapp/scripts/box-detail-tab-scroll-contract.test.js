const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')

function source(relative) {
  return fs.readFileSync(path.join(__dirname, '..', relative), 'utf8')
}

function setTabBody() {
  const page = source('package-graph/pages/box-detail/index.ts')
  const match = page.match(/setTab\([^)]*\)\s*\{([\s\S]*?)\n\s*\},\n\s*onCritiqueTap/)
  assert.ok(match, 'setTab 方法应存在')
  return match[1]
}

function applyBodyScrollTopBody() {
  const page = source('package-graph/pages/box-detail/index.ts')
  const match = page.match(/applyBodyScrollTop\([\s\S]*?\n\s*\},\n\s*\/\*\* 详情 DOM 重建后恢复阅读进度/)
  assert.ok(match, 'applyBodyScrollTop 方法应存在')
  return match[0]
}

function onDetailScrollBody() {
  const page = source('package-graph/pages/box-detail/index.ts')
  const match = page.match(/onDetailScroll\([^)]*\)\s*\{([\s\S]*?)\n\s*\},\n\s*\/\*\* 切换 tab 栏显隐/)
  assert.ok(match, 'onDetailScroll 方法应存在')
  return match[1]
}

test('切回详情 Tab 不得先滚到顶部，否则正文停在开头只剩进度条', () => {
  const body = setTabBody()
  const callback = body.match(/setData\(\{[\s\S]*?\}, \(\) => \{([\s\S]*?)\n\s*\}\)/)
  assert.ok(callback, 'setTab 应在 setData 回调里恢复滚动')
  const restoreBranch = callback[1].match(/if \(restoreContent\) \{([\s\S]*?)\n\s*\} else \{/)
  assert.ok(restoreBranch, 'setTab 回调应有 restoreContent 分支')
  assert.doesNotMatch(restoreBranch[1], /applyBodyScrollTop\(0\)/)
  assert.match(restoreBranch[1], /restoreContentScrollTop\(restoreTop\)/)
  assert.match(body, /_restoringReadingProgress\s*=\s*restoreTop\s*>\s*0/)
})

test('切到关系/评述/见证仍把共享 scroll-view 归零', () => {
  const body = setTabBody()
  const callback = body.match(/setData\(\{[\s\S]*?\}, \(\) => \{([\s\S]*?)\n\s*\}\)/)
  assert.ok(callback, 'setTab 应在 setData 回调里处理非详情滚动')
  const leaveBranch = callback[1].match(/if \(restoreContent\) \{[\s\S]*?\n\s*\} else \{([\s\S]*?)\n\s*\}/)
  assert.ok(leaveBranch, 'setTab 离开详情时应归零滚动')
  assert.match(leaveBranch[1], /applyBodyScrollTop\(0\)/)
})

test('详情滚动静默同步 bodyScrollTop，进度条才 setData', () => {
  const body = onDetailScrollBody()
  const silent = body.match(/this\.data\.bodyScrollTop\s*=\s*scrollTop/)
  assert.ok(silent)
  assert.match(body.slice(0, silent.index), /_restoringReadingProgress/)
  assert.match(body, /readingProgress:\s*pct/)
  assert.doesNotMatch(body, /bodyScrollTop:\s*scrollTop/)
})

test('详情恢复滚动期间不把进度条/持久化写成 0', () => {
  const body = onDetailScrollBody()
  const persist = body.match(/schedulePersistReadingProgress/)
  assert.ok(persist)
  assert.match(body.slice(0, persist.index), /_restoringReadingProgress/)
  const setProgress = body.match(/setData\(\{\s*readingProgress:\s*pct/)
  assert.ok(setProgress, '进度条应通过 setData({ readingProgress: pct }) 更新')
  assert.match(body.slice(0, setProgress.index), /_restoringReadingProgress/)
})

test('程序定位 scroll-top 用序号作废过期回调，避免先归零后覆盖恢复位置', () => {
  const apply = applyBodyScrollTopBody()
  assert.match(apply, /_bodyScrollAssignSeq/)
  assert.match(apply, /seq !== this\._bodyScrollAssignSeq/)
})

test('wx:if 重建后程序滚动必须先 bump 再设目标，并核对真实 scrollTop', () => {
  const page = source('package-graph/pages/box-detail/index.ts')
  const wxml = source('package-graph/pages/box-detail/index.wxml')
  const apply = applyBodyScrollTopBody()
  assert.match(apply, /0\.01/)
  assert.match(wxml, /id="boxTab1Body"/)
  const restore = page.match(/restoreContentScrollTop\([\s\S]*?\n\s*\},\n\s*onShareAppMessage/)
  assert.ok(restore, 'restoreContentScrollTop 方法应存在')
  assert.match(restore[0], /#boxTab1Body/)
  assert.match(restore[0], /Math\.abs\(actual - safeTarget\)/)
})
