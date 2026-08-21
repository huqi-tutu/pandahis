const { describe, it } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { composerSheetViewModel, formatSheetCoordinate, estimateQuoteLines } = require('../native-utils/composer-sheet-layout.js')

function source(relative) {
  return fs.readFileSync(path.join(__dirname, '..', relative), 'utf8')
}

function layout(overrides = {}) {
  return composerSheetViewModel({
    windowHeight: 667,
    windowWidth: 375,
    keyboardHeight: 0,
    safeAreaBottom: 34,
    restWindowHeight: 667,
    mode: 'edit',
    selectedText: '短引',
    quoteExpanded: false,
    ...overrides,
  })
}

function assertSheetFitsWindow(input, vm) {
  assert.ok(vm.keyboardLiftPx >= 0)
  assert.ok(vm.cardMaxHeightPx >= 0)
  assert.ok(
    vm.keyboardLiftPx + vm.cardMaxHeightPx <= input.windowHeight,
    `sheet ${vm.keyboardLiftPx}+${vm.cardMaxHeightPx} exceeds window ${input.windowHeight}`,
  )
  assert.ok(vm.bodyMaxHeightPx >= 0)
  assert.ok(vm.bodyMaxHeightPx + vm.chromeHeightPx <= vm.cardMaxHeightPx + 0.5)
}

describe('composerSheetViewModel', () => {
  it('键盘收起时卡片不超过 85% 屏高，底 padding 含安全区', () => {
    const input = {
      windowHeight: 667,
      windowWidth: 375,
      keyboardHeight: 0,
      safeAreaBottom: 34,
      restWindowHeight: 667,
      mode: 'edit',
      selectedText: '短引',
      quoteExpanded: false,
    }
    const vm = composerSheetViewModel(input)
    assert.equal(vm.keyboardOpen, false)
    assert.equal(vm.keyboardLiftPx, 0)
    assert.equal(vm.cardMaxHeightPx, Math.floor(667 * 0.85))
    assert.match(vm.cardStyle, /height:auto/)
    assert.ok(vm.cardPaddingBottomPx > 34)
    assert.equal(vm.quoteMaxLines, 0)
    assert.equal(vm.showQuoteToggle, false)
    assertSheetFitsWindow(input, vm)
  })

  it('iOS 键盘升起时卡片贴在键盘上方，且不再保底 280px 把提交顶出屏幕', () => {
    const input = {
      windowHeight: 667,
      windowWidth: 375,
      keyboardHeight: 420,
      safeAreaBottom: 34,
      restWindowHeight: 667,
      mode: 'edit',
      selectedText: 'x'.repeat(80),
      quoteExpanded: true,
      quoteClassPrefix: 'correction-quote',
    }
    const vm = composerSheetViewModel(input)
    assert.equal(vm.keyboardOpen, true)
    assert.equal(vm.keyboardLiftPx, 420)
    assert.equal(vm.cardMaxHeightPx, 247)
    assert.equal(vm.keyboardLiftPx + vm.cardMaxHeightPx, 667)
    assert.match(vm.cardStyle, /height:247px/)
    assert.ok(vm.cardPaddingBottomPx < 34, '键盘升起时去掉 home indicator 占位')
    assert.equal(vm.quoteMaxLines, 0)
    assert.equal(vm.quoteClampStyle, '')
    assert.equal(vm.showQuoteToggle, false)
    assertSheetFitsWindow(input, vm)
  })

  it('键盘升起时不截断划线原文，把预留空白交给正文滚动', () => {
    const vm = layout({
      keyboardHeight: 336,
      selectedText: '汉军在荥阳以南修筑甬道，直通黄河边上的敖仓，靠这条粮道维持补给。'.repeat(3),
    })
    assert.equal(vm.keyboardOpen, true)
    assert.equal(vm.quoteMaxLines, 0)
    assert.equal(vm.quoteClampClass, '')
    assert.ok(vm.bodyMaxHeightPx > 56)
    assert.match(vm.bodyStyle, /height:\d+px/)
  })

  it('Android 窗口已被键盘挤矮时不再叠加 margin-bottom', () => {
    const input = {
      windowHeight: 400,
      windowWidth: 375,
      keyboardHeight: 336,
      safeAreaBottom: 0,
      restWindowHeight: 667,
      mode: 'edit',
      selectedText: '短引',
      quoteExpanded: false,
    }
    const vm = composerSheetViewModel(input)
    assert.equal(vm.keyboardOpen, true)
    assert.equal(vm.keyboardLiftPx, 0)
    assert.equal(vm.cardMaxHeightPx, 400)
    assertSheetFitsWindow(input, vm)
  })

  it('浏览态不占编辑器高度，长引用不截断', () => {
    const edit = layout({ mode: 'edit' })
    const view = layout({ mode: 'view', selectedText: 'x'.repeat(200) })
    assert.ok(view.bodyMaxHeightPx > edit.bodyMaxHeightPx)
    assert.equal(view.textareaHeightPx, 0)
    assert.equal(view.quoteMaxLines, 0)
    assert.equal(view.showQuoteToggle, false)
    assert.equal(view.quoteClampClass, '')
  })

  it('15 行及以内整段展示，不出现展开收起', () => {
    const charsPerLine = estimateQuoteLines('字'.repeat(25), 375)
    assert.equal(charsPerLine, 1)
    const fifteen = layout({ selectedText: '字'.repeat(25 * 15) })
    assert.ok(estimateQuoteLines('字'.repeat(25 * 15), 375) <= 15)
    assert.equal(fifteen.showQuoteToggle, false)
    assert.equal(fifteen.quoteMaxLines, 0)
    assert.equal(fifteen.quoteClampStyle, '')
  })

  it('超过 15 行才默认收起，并可展开', () => {
    const longText = '字'.repeat(25 * 15 + 1)
    const collapsed = layout({ selectedText: longText, quoteExpanded: false })
    const expanded = layout({ selectedText: longText, quoteExpanded: true })
    assert.equal(collapsed.showQuoteToggle, true)
    assert.equal(collapsed.quoteMaxLines, 15)
    assert.equal(collapsed.quoteToggleLabel, '展开')
    assert.equal(expanded.quoteMaxLines, 0)
    assert.equal(expanded.quoteToggleLabel, '收起')
    assert.match(collapsed.quoteClampClass, /is-clamp-15/)
    assert.match(collapsed.quoteClampStyle, /-webkit-line-clamp:15/)
    assert.doesNotMatch(collapsed.quoteClampStyle, /max-height/)
  })

  it('坐标为文明 · 朝代 · 史略，空段省略、相邻同名去重', () => {
    assert.equal(formatSheetCoordinate('华夏', '西汉', '汉高祖'), '华夏 · 西汉 · 汉高祖')
    assert.equal(formatSheetCoordinate('', '西汉', '汉高祖'), '西汉 · 汉高祖')
    assert.equal(formatSheetCoordinate('华夏', '西汉', '西汉'), '华夏 · 西汉')
    assert.equal(formatSheetCoordinate('', '', ''), '')
  })
})

describe('composer sheet markup', () => {
  it('纠错弹层把 textarea 和提交钉在 scroll-view 外', () => {
    const wxml = source('components/correction-modal/correction-modal.wxml')
    const body = wxml.match(/<scroll-view[\s\S]*?<\/scroll-view>/)
    assert.ok(body)
    assert.doesNotMatch(body[0], /<textarea/)
    assert.doesNotMatch(body[0], /correction-submit/)
    assert.match(wxml, /correction-modal-composer[\s\S]*<textarea[\s\S]*correction-submit/)
    assert.match(wxml, /catchtap="onSheetTap"/)
    assert.match(wxml, /<textarea[\s\S]*catchtap="noop"/)
    assert.match(wxml, /correction-submit[\s\S]*catchtap="onSubmit"/)
    assert.match(wxml, /correction-label">坐标/)
    assert.doesNotMatch(wxml, /correction-label">文明/)
    assert.doesNotMatch(wxml, /correction-label">朝代/)
    assert.doesNotMatch(wxml, /correction-label">史略/)
    assert.match(source('components/correction-modal/correction-modal.ts'), /hideKeyboard/)
    assert.doesNotMatch(source('components/correction-modal/correction-modal.ts'), /Math\.max\(280/)
  })

  it('笔记弹层同样钉底，避免同样被键盘挡住', () => {
    const wxml = source('components/note-modal/note-modal.wxml')
    const body = wxml.match(/<scroll-view[\s\S]*?<\/scroll-view>/)
    assert.ok(body)
    assert.doesNotMatch(body[0], /<textarea/)
    assert.doesNotMatch(body[0], /note-submit/)
    assert.match(wxml, /note-modal-composer[\s\S]*<textarea[\s\S]*note-submit/)
    assert.match(wxml, /catchtap="onSheetTap"/)
    assert.match(wxml, /<textarea[\s\S]*catchtap="noop"/)
    assert.match(wxml, /note-submit[\s\S]*catchtap="onSubmit"/)
    assert.match(wxml, /note-label">坐标/)
    assert.doesNotMatch(wxml, /note-label">史略/)
    assert.match(source('components/note-modal/note-modal.ts'), /hideKeyboard/)
  })
})
