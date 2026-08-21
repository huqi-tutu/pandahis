const assert = require('node:assert/strict')
const test = require('node:test')

const {
  buildRows,
  buildAllExpanded,
  toggleDynastyExpanded,
  isDynastyExpanded,
  TIME_HX_HIT_MIN_RPX,
} = require('../native-utils/matrix/mock-home-matrix.js')
const mingQing = require('../native-utils/matrix/ming-qing-layout.js')
const songLiaoJin = require('../native-utils/matrix/song-liao-jin-layout.js')
const nanbeiSui = require('../native-utils/matrix/nanbei-sui-layout.js')

function snapshotGroup(expanded) {
  return {
    ming: mingQing.isMingExpanded(expanded),
    song: songLiaoJin.isSongExpanded(expanded),
    nanbei: nanbeiSui.isNanbeiSuiExpanded(expanded),
  }
}

function assertSameGroupToggle(keys, fromExpanded, predicate) {
  const baseline = toggleDynastyExpanded(keys[0], Object.assign({}, fromExpanded), '华夏')
  keys.slice(1).forEach(key => {
    const next = toggleDynastyExpanded(key, Object.assign({}, fromExpanded), '华夏')
    assert.equal(
      predicate(next),
      predicate(baseline),
      `${key} 与 ${keys[0]} 应切换同一组，结果却不同`
    )
  })
}

test('明清轴标联动：明、清开关应切换同一组', () => {
  const keys = mingQing.MING_LINKED_AXIS_KEYS
  assertSameGroupToggle(keys, {}, exp => mingQing.isMingExpanded(exp))
  assertSameGroupToggle(keys, buildAllExpanded('huaxia'), exp => mingQing.isMingExpanded(exp))

  let state = toggleDynastyExpanded('清', {}, '华夏')
  assert.equal(mingQing.isMingExpanded(state), true)
  state = toggleDynastyExpanded('清', state, '华夏')
  assert.equal(mingQing.isMingExpanded(state), false)
  assert.equal(isDynastyExpanded('明', state, '华夏'), false)
  assert.equal(isDynastyExpanded('清', state, '华夏'), false)
})

test('宋辽金元轴标联动：宋、金、南宋、元开关应切换同一组', () => {
  const keys = songLiaoJin.SONG_LINKED_AXIS_KEYS
  assertSameGroupToggle(keys, {}, exp => songLiaoJin.isSongExpanded(exp))
  assertSameGroupToggle(keys, buildAllExpanded('huaxia'), exp => songLiaoJin.isSongExpanded(exp))

  let state = toggleDynastyExpanded('元', {}, '华夏')
  assert.equal(songLiaoJin.isSongExpanded(state), true)
  state = toggleDynastyExpanded('元', state, '华夏')
  assert.equal(songLiaoJin.isSongExpanded(state), false)
  assert.equal(isDynastyExpanded('元', state, '华夏'), false)
})

test('南北朝与隋轴标联动：两端开关应切换同一组', () => {
  const keys = nanbeiSui.NANBEI_LINKED_AXIS_KEYS
  assertSameGroupToggle(keys, {}, exp => nanbeiSui.isNanbeiSuiExpanded(exp))
  assertSameGroupToggle(keys, buildAllExpanded('huaxia'), exp => nanbeiSui.isNanbeiSuiExpanded(exp))
})

test('展开态可点收展的轴标行须有足够热区，避免清/元只能展开不能折叠', () => {
  const layout = buildRows('huaxia', buildAllExpanded('huaxia'))
  const labeled = (layout.rows || []).filter(r => r.expandable && r.hxLabel)
  assert.ok(labeled.length > 0)

  const thinKeys = ['金', '元', '清']
  thinKeys.forEach(key => {
    const row = labeled.find(r => r.dynastyKey === key || r.hxLabel === key)
    assert.ok(row, `缺少 ${key} 轴标行`)
    assert.equal(row.expanded, true)
    assert.ok(
      (row.hxHitH || 0) >= TIME_HX_HIT_MIN_RPX,
      `${key} 热区高度应为 ≥${TIME_HX_HIT_MIN_RPX}，实际 hxHitH=${row.hxHitH} h=${row.h}`
    )
  })

  labeled.forEach(row => {
    assert.ok(
      (row.hxHitH || 0) >= TIME_HX_HIT_MIN_RPX,
      `${row.hxLabel} 热区过小：hxHitH=${row.hxHitH} h=${row.h}`
    )
  })
})

test('折叠态明清卡片仍在，且清轴标可点', () => {
  const layout = buildRows('huaxia', {})
  const qingRow = (layout.rows || []).find(r => r.hxLabel === '清')
  const mingRow = (layout.rows || []).find(r => r.hxLabel === '明')
  assert.ok(qingRow && qingRow.expandable && !qingRow.expanded)
  assert.ok(mingRow && mingRow.expandable && !mingRow.expanded)
  const qingCard = (layout.blocks || []).find(b => b.dynasty === '清' && b.kind === 'dynasty')
  const mingCard = (layout.blocks || []).find(b => b.dynasty === '明' && b.kind === 'dynasty')
  assert.ok(qingCard && mingCard)
  assert.equal(snapshotGroup({}).ming, false)
})
