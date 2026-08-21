const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')

function source(relative) {
  return fs.readFileSync(path.join(__dirname, '..', relative), 'utf8')
}

test('详情页原文请求按本地令牌状态软认证访问', () => {
  const compatibleAccess = /original-ref`,\s*\{\s*auth:\s*hasToken\(\),\s*softAuth:\s*true,?\s*\}/
  assert.match(source('package-graph/pages/box-detail/index.ts'), compatibleAccess)
})

test('独立原文页已下线', () => {
  assert.doesNotMatch(source('app.json'), /pages\/original-text/)
  assert.doesNotMatch(source('native-utils/router.ts'), /originalText/)
  assert.equal(fs.existsSync(path.join(__dirname, '..', 'pages/original-text')), false)
})

test('跳转原文不再读取 header 的 original locked 状态', () => {
  const body = source('package-graph/pages/box-detail/index.ts').match(/goOriginal\(\)\s*\{([\s\S]*?)\n\s*\},\n/)
  assert.ok(body)
  assert.doesNotMatch(body[1], /access\?\.tabs\?\.original|promptLockedTab/)
})


test('详情页原文失败统一为友好加载失败', () => {
  const page = source('package-graph/pages/box-detail/index.ts')
  const goOriginal = page.match(/goOriginal\(\)\s*\{([\s\S]*?)\n\s*\},\n\s*closeOriginal/)
  assert.ok(goOriginal)
  assert.match(goOriginal[1], /原文暂时无法加载，请稍后重试/)
  assert.doesNotMatch(goOriginal[1], /需要会员|ROUTES\.membership|switchTab/)
})

test('原文半屏滚动区与朝代简介同结构，并给出固定高度', () => {
  const wxml = source('package-graph/pages/box-detail/index.wxml')
  assert.doesNotMatch(wxml, /ud-modal-body-wrap/)
  assert.match(wxml, /<scroll-view[\s\S]*class="ud-modal-body"/)
  assert.match(wxml, /id="originalBodyScroll"/)
  assert.match(wxml, /bindscroll="onOriginalScroll"/)
  assert.match(wxml, /scroll-top="\{\{originalScrollAssign\}\}"/)
  const scss = source('package-graph/pages/box-detail/index.scss')
  const body = scss.match(/\.ud-modal-body \{([\s\S]*?)\n\}/)
  assert.ok(body)
  assert.match(body[1], /height:\s*62vh/)
  assert.match(body[1], /max-height:\s*62vh/)
})

test('原文半屏用户滚动时静默同步 scroll-top，进度条才 setData', () => {
  const page = source('package-graph/pages/box-detail/index.ts')
  const onOriginalScroll = page.match(/onOriginalScroll\([^)]*\)\s*\{([\s\S]*?)\n\s*\},/)
  assert.ok(onOriginalScroll)
  assert.match(onOriginalScroll[1], /this\.data\.originalScrollAssign\s*=\s*scrollTop/)
  assert.match(onOriginalScroll[1], /originalReadingProgress:\s*pct/)
  assert.doesNotMatch(onOriginalScroll[1], /originalScrollAssign:\s*scrollTop/)
})

test('原文半屏程序定位后保留 scroll-top，不释放成空以免正文回到顶部', () => {
  const page = source('package-graph/pages/box-detail/index.ts')
  const apply = page.match(/applyOriginalScrollTop\([\s\S]*?\n\s*\},\n\s*restoreOriginalScrollTop/)
  assert.ok(apply)
  assert.match(apply[0], /originalScrollAssign:\s*safeTarget/)
  assert.doesNotMatch(apply[0], /releaseOriginalScrollAssign/)
})

test('原文半屏打开恢复、关闭落盘，存储键与详情隔离', () => {
  const page = source('package-graph/pages/box-detail/index.ts')
  const goOriginal = page.match(/goOriginal\(\)\s*\{([\s\S]*?)\n\s*\},\n\s*closeOriginal/)
  const closeOriginal = page.match(/closeOriginal\(\)\s*\{([\s\S]*?)\n\s*\},/)
  assert.ok(goOriginal)
  assert.ok(closeOriginal)
  assert.match(goOriginal[1], /tryRestoreOriginalReadingProgress/)
  assert.match(goOriginal[1], /cancelOriginalProgressRestore/)
  assert.match(closeOriginal[1], /cancelOriginalProgressRestore/)
  assert.match(closeOriginal[1], /schedulePersistOriginalReadingProgress\(true\)/)
  assert.match(page, /originalReadingProgressId\(this\.data\.boxId\)/)
  assert.match(page, /persistBoxReadingProgress\(\s*originalReadingProgressId/)
})

test('原文半屏恢复失败或关闭时不把滚动位置写成 0', () => {
  const page = source('package-graph/pages/box-detail/index.ts')
  const onOriginalScroll = page.match(/onOriginalScroll\([^)]*\)\s*\{([\s\S]*?)\n\s*\},/)
  const fromRecord = page.match(/restoreOriginalScrollFromRecord\([\s\S]*?\n\s*\},\n\s*applyOriginalScrollTop/)
  assert.ok(onOriginalScroll)
  assert.ok(fromRecord)
  assert.match(onOriginalScroll[1], /!this\.data\.showOriginal/)
  assert.match(onOriginalScroll[1], /_restoringOriginalProgress/)
  assert.match(fromRecord[0], /!this\.data\.showOriginal/)
  assert.match(fromRecord[0], /maxScroll > 0/)
})
