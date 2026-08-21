const assert = require('node:assert/strict')
const test = require('node:test')

const {
  isRestorableProgressPct,
  progressPctFromScroll,
  scrollTopFromProgressPct,
  pickNewerProgress,
  upsertProgressMap,
  readProgressMap,
  resolveRestoreScrollTop,
  detailViewportFallbackPx,
  originalViewportFallbackPx,
  originalReadingProgressId,
  readingProgressScopeKey,
} = require('../native-utils/box-reading-progress.js')

test('仅 5–95% 视为可恢复进度', () => {
  assert.equal(isRestorableProgressPct(4), false)
  assert.equal(isRestorableProgressPct(5), true)
  assert.equal(isRestorableProgressPct(42), true)
  assert.equal(isRestorableProgressPct(95), true)
  assert.equal(isRestorableProgressPct(96), false)
  assert.equal(isRestorableProgressPct(null), false)
})

test('百分比与滚动位置可互算', () => {
  assert.equal(progressPctFromScroll(500, 1000), 50)
  assert.equal(scrollTopFromProgressPct(50, 1000), 500)
  assert.equal(scrollTopFromProgressPct(3, 1000), 0)
})

test('详情视口回退用 tabTop 而非 bodyTop', () => {
  assert.equal(detailViewportFallbackPx(800, 88), 712)
})

test('原文半屏视口回退按 62vh', () => {
  assert.equal(originalViewportFallbackPx(800), 496)
  assert.equal(originalViewportFallbackPx(0), 0)
})

test('原文进度存储键与详情互不覆盖', () => {
  assert.equal(originalReadingProgressId(''), '')
  assert.equal(originalReadingProgressId('  GLBL_00085  '), 'GLBL_00085__original')
  assert.equal(originalReadingProgressId('GLBL_00085__original'), 'GLBL_00085__original')
  const detail = upsertProgressMap({}, 'GLBL_00085', { progressPct: 40, scrollTopPx: 200 }, '2026-08-10T10:00:00.000Z')
  const both = upsertProgressMap(detail, originalReadingProgressId('GLBL_00085'), { progressPct: 70, scrollTopPx: 880 }, '2026-08-10T11:00:00.000Z')
  assert.equal(both.GLBL_00085.progressPct, 40)
  assert.equal(both['GLBL_00085__original'].progressPct, 70)
})

test('resolveRestoreScrollTop 优先 scrollTopPx', () => {
  const record = {
    progressPct: 50,
    scrollTopPx: 420,
    updatedAt: '2026-08-10T12:00:00.000Z',
  }
  assert.equal(resolveRestoreScrollTop(record, 1000), 420)
  assert.equal(resolveRestoreScrollTop(record, 300), 300)
  assert.equal(
    resolveRestoreScrollTop({ progressPct: 50, scrollTopPx: null, updatedAt: record.updatedAt }, 1000),
    500,
  )
})

test('readingProgressScopeKey 按 token 分桶', () => {
  assert.equal(readingProgressScopeKey(''), null)
  assert.equal(readingProgressScopeKey('token-a'), readingProgressScopeKey('token-a'))
  assert.notEqual(readingProgressScopeKey('token-a'), readingProgressScopeKey('token-b'))
})

test('pickNewerProgress 取较新且可恢复的记录', () => {
  const older = { progressPct: 20, scrollTopPx: 100, updatedAt: '2026-08-10T10:00:00.000Z' }
  const newer = { progressPct: 55, scrollTopPx: 500, updatedAt: '2026-08-10T12:00:00.000Z' }
  assert.deepEqual(pickNewerProgress(older, newer), newer)
  assert.deepEqual(pickNewerProgress(newer, older), newer)
  assert.equal(pickNewerProgress(null, null), null)
})

test('upsertProgressMap 不可变写入，边缘进度清除条目', () => {
  const base = upsertProgressMap({}, 'GLBL_1', { progressPct: 40, scrollTopPx: 200 }, '2026-08-10T10:00:00.000Z')
  assert.equal(base.GLBL_1.scrollTopPx, 200)
  const cleared = upsertProgressMap(base, 'GLBL_1', { progressPct: 2, scrollTopPx: 10 }, '2026-08-10T11:00:00.000Z')
  assert.equal(Object.prototype.hasOwnProperty.call(cleared, 'GLBL_1'), false)
  assert.notStrictEqual(cleared, base)
  assert.deepEqual(readProgressMap({ GLBL_1: { progressPct: 3, updatedAt: '2026-08-10T10:00:00.000Z' } }), {})
})
