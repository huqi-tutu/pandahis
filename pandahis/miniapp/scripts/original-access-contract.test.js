const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')

function source(relative) {
  return fs.readFileSync(path.join(__dirname, '..', relative), 'utf8')
}

test('两个原文请求均按本地令牌状态软认证访问', () => {
  const compatibleAccess = /original-ref`,\s*\{\s*auth:\s*hasToken\(\),\s*softAuth:\s*true,?\s*\}/
  assert.match(source('package-graph/pages/box-detail/index.ts'), compatibleAccess)
  assert.match(source('pages/original-text/index.ts'), compatibleAccess)
})

test('跳转原文不再读取 header 的 original locked 状态', () => {
  const body = source('package-graph/pages/box-detail/index.ts').match(/goOriginal\(\)\s*\{([\s\S]*?)\n\s*\},\n/)
  assert.ok(body)
  assert.doesNotMatch(body[1], /access\?\.tabs\?\.original|promptLockedTab/)
})


test('独立原文页失败时不再引导登录或会员', () => {
  const page = source('pages/original-text/index.ts')
  const catchBody = page.match(/\} catch \{([\s\S]*?)\n\s*\}\n\s*\},\n\s*copyLink/)
  assert.ok(catchBody)
  assert.match(catchBody[1], /原文暂时无法加载，请稍后重试/)
  assert.doesNotMatch(catchBody[1], /需要登录|需要会员|ROUTES\.login|ROUTES\.membership/)
})

test('详情页原文失败统一为友好加载失败', () => {
  const page = source('package-graph/pages/box-detail/index.ts')
  const goOriginal = page.match(/goOriginal\(\)\s*\{([\s\S]*?)\n\s*\},\n\s*closeOriginal/)
  assert.ok(goOriginal)
  assert.match(goOriginal[1], /原文暂时无法加载，请稍后重试/)
  assert.doesNotMatch(goOriginal[1], /需要会员|ROUTES\.membership|switchTab/)
})
