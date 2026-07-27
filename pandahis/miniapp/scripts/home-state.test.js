const assert = require('node:assert/strict')
const test = require('node:test')

const {
  collapsedForCiv,
  mergePersistPayload,
  mergeRemoteHomeState,
  updateCollapsedForCiv,
} = require('../native-utils/home-state.js')

test('按文明不可变保存折叠状态，切回后仍可恢复且空数组有效', () => {
  const china = updateCollapsedForCiv(null, 'china', ['xia'], '2026-07-24T10:00:00Z')
  const world = updateCollapsedForCiv(china, 'world', [], '2026-07-24T10:01:00Z')

  assert.deepEqual(collapsedForCiv(world, 'china'), ['xia'])
  assert.deepEqual(collapsedForCiv(world, 'world'), [])
  assert.notStrictEqual(world, china)
})

test('兼容旧版单文明 collapsedDynastyKeys 状态', () => {
  const legacy = { civId: 'china', collapsedDynastyKeys: ['shang'] }
  assert.deepEqual(collapsedForCiv(legacy, 'china'), ['shang'])
  assert.equal(collapsedForCiv(legacy, 'world'), null)
})

test('较旧远端状态不能覆盖本地较新的空折叠数组', () => {
  const local = updateCollapsedForCiv(null, 'china', [], '2026-07-24T10:02:00Z')
  const remote = {
    civId: 'china',
    civilizationCode: 'CN',
    collapsedDynastyKeys: ['xia'],
    updatedAt: '2026-07-24T10:01:00Z',
  }
  const merged = mergeRemoteHomeState(local, remote)
  assert.deepEqual(collapsedForCiv(merged, 'china'), [])
})


test('连续合并双文明远端状态时保留其他文明的本地时间戳裁决', () => {
  const localA = updateCollapsedForCiv(null, 'A', ['a-local'], '2026-07-24T10:00:00Z')
  const local = updateCollapsedForCiv(localA, 'B', ['b-local'], '2026-07-24T10:02:00Z')
  const remoteA = {
    civId: 'A',
    collapsedDynastyKeys: ['a-remote'],
    collapsedDynastyKeysByCiv: { B: ['b-stale'] },
    collapsedDynastyUpdatedAtByCiv: { B: '2026-07-24T09:00:00Z' },
    updatedAt: '2026-07-24T10:01:00Z',
  }
  const afterA = mergeRemoteHomeState(local, remoteA)
  const remoteB = {
    civId: 'B',
    collapsedDynastyKeys: ['b-remote'],
    updatedAt: '2026-07-24T10:01:00Z',
  }

  const merged = mergeRemoteHomeState(afterA, remoteB)

  assert.deepEqual(collapsedForCiv(merged, 'B'), ['b-local'])
  assert.equal(merged.collapsedDynastyUpdatedAtByCiv.B, '2026-07-24T10:02:00Z')
})


test('损坏映射项与非法时间戳视为缺失而非明确空数组', () => {
  const damaged = {
    civId: 'china',
    collapsedDynastyKeysByCiv: {
      china: 'not-an-array',
      world: ['rome'],
      '': ['invalid'],
    },
    collapsedDynastyUpdatedAtByCiv: {
      china: 'not-a-date',
      world: '2026-07-24T10:00:00.000Z',
      '': '2026-07-24T10:00:00.000Z',
    },
  }
  assert.equal(collapsedForCiv(damaged, 'china'), null)
  assert.deepEqual(collapsedForCiv(damaged, 'world'), ['rome'])
  const updated = updateCollapsedForCiv(damaged, '', ['bad'], 'invalid')
  assert.equal(Object.prototype.hasOwnProperty.call(updated.collapsedDynastyKeysByCiv, ''), false)
})

test('远端数组映射和非法项目不会污染有效本地状态', () => {
  const local = updateCollapsedForCiv(null, 'china', ['local'], '2026-07-24T10:02:00.000Z')
  const merged = mergeRemoteHomeState(local, {
    civId: '',
    collapsedDynastyKeys: ['bad'],
    collapsedDynastyKeysByCiv: ['not-a-map'],
    collapsedDynastyUpdatedAtByCiv: { china: 'invalid' },
    updatedAt: 'invalid',
  })
  assert.deepEqual(collapsedForCiv(merged, 'china'), ['local'])
  assert.equal(Object.prototype.hasOwnProperty.call(merged.collapsedDynastyKeysByCiv, ''), false)
})


test('保存 B 当前状态时保留 existing 中 A/B 的文明映射与时间戳', () => {
  const existing = {
    civId: 'A',
    collapsedDynastyKeysByCiv: { A: ['a-old'], B: ['b-old'] },
    collapsedDynastyUpdatedAtByCiv: {
      A: '2026-07-24T10:00:00.000Z',
      B: '2026-07-24T10:01:00.000Z',
    },
    lastScrollTopPx: 120,
  }
  const next = {
    civId: 'B',
    collapsedDynastyKeys: ['b-new'],
    updatedAt: '2026-07-24T10:02:00.000Z',
    lastScrollTopPx: 0,
  }

  const merged = mergePersistPayload(existing, next)
  const updated = updateCollapsedForCiv(
    merged,
    'B',
    next.collapsedDynastyKeys,
    next.updatedAt,
  )

  assert.deepEqual(updated.collapsedDynastyKeysByCiv, {
    A: ['a-old'],
    B: ['b-new'],
  })
  assert.deepEqual(updated.collapsedDynastyUpdatedAtByCiv, {
    A: '2026-07-24T10:00:00.000Z',
    B: '2026-07-24T10:02:00.000Z',
  })
  assert.deepEqual(existing.collapsedDynastyKeysByCiv, { A: ['a-old'], B: ['b-old'] })
})

test('回顶时清除陈旧朝代锚点，避免刷新后误跳到西周', () => {
  const existing = {
    civId: 'huaxia',
    lastScrollTopPx: 840,
    lastDynastyKey: '西周',
    lastNavActiveIdx: 2,
  }
  const next = {
    civId: 'huaxia',
    lastScrollTopPx: 0,
    lastDynastyKey: '夏',
    lastNavActiveIdx: 0,
    updatedAt: '2026-07-24T10:03:00.000Z',
  }

  const merged = mergePersistPayload(existing, next)
  assert.equal(merged.lastScrollTopPx, 0)
  assert.equal(merged.lastDynastyKey, '')
  assert.equal(merged.lastNavActiveIdx, 0)
})

test('未登录场景 stripViewportFields 仅保留折叠态', () => {
  const { stripViewportFields, hasRestorableViewport } = require('../native-utils/home-state.js')
  const state = {
    civId: 'huaxia',
    lastScrollTopPx: 640,
    lastDynastyKey: '西周',
    collapsedDynastyKeys: ['xia'],
  }
  const stripped = stripViewportFields(state)
  assert.equal(stripped.lastScrollTopPx, null)
  assert.equal(stripped.lastDynastyKey, '')
  assert.deepEqual(stripped.collapsedDynastyKeys, ['xia'])
  assert.equal(hasRestorableViewport(stripped), false)
  assert.equal(hasRestorableViewport(state), true)
})
