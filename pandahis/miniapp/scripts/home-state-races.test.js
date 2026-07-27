const assert = require('node:assert/strict')
const test = require('node:test')

const { mergeRemoteLoadResult, isViewportReadCurrent } = require('../native-utils/home-state-coordinator.js')
const { createRemoteStateSaveQueue } = require('../native-utils/remote-state-save-queue.js')

function deferred() {
  let resolve
  let reject
  const promise = new Promise((ok, fail) => { resolve = ok; reject = fail })
  return { promise, resolve, reject }
}

test('远端响应到达时合并最新本地折叠，且代次变化后不允许覆盖当前 UI', () => {
  const latestLocal = {
    civId: 'china',
    collapsedDynastyKeys: ['shang'],
    collapsedDynastyKeysByCiv: { china: ['shang'] },
    collapsedDynastyUpdatedAtByCiv: { china: '2026-07-24T10:02:00.000Z' },
    updatedAt: '2026-07-24T10:02:00.000Z',
  }
  const remote = {
    civId: 'china',
    collapsedDynastyKeys: ['xia'],
    updatedAt: '2026-07-24T10:01:00.000Z',
  }
  const result = mergeRemoteLoadResult(latestLocal, remote, 1, 2)
  assert.deepEqual(result.state.collapsedDynastyKeysByCiv.china, ['shang'])
  assert.equal(result.shouldApplyUi, false)
})

test('保存队列连续三次只发送首个和最后一个快照', async () => {
  const calls = []
  const pending = []
  const queue = createRemoteStateSaveQueue(snapshot => {
    calls.push(snapshot)
    const item = deferred()
    pending.push(item)
    return item.promise
  })
  queue.enqueue({ version: 1 })
  queue.enqueue({ version: 2 })
  queue.enqueue({ version: 3 })
  assert.deepEqual(calls, [{ version: 1 }])
  pending[0].resolve()
  await Promise.resolve()
  await Promise.resolve()
  assert.deepEqual(calls, [{ version: 1 }, { version: 3 }])
  pending[1].resolve()
  await queue.idle()
})

test('保存失败后仍发送最新快照，dispose 后不产生未处理拒绝', async () => {
  const calls = []
  const pending = []
  const queue = createRemoteStateSaveQueue(snapshot => {
    calls.push(snapshot)
    const item = deferred()
    pending.push(item)
    return item.promise
  })
  queue.enqueue({ version: 1 })
  queue.enqueue({ version: 2 })
  pending[0].reject(new Error('网络失败'))
  await Promise.resolve()
  await Promise.resolve()
  assert.deepEqual(calls, [{ version: 1 }, { version: 2 }])
  queue.dispose()
  pending[1].reject(new Error('卸载后失败'))
  await queue.idle()
})

test('文明或状态代次变化后丢弃旧 DOM 滚动结果', () => {
  assert.equal(isViewportReadCurrent({ civId: 'china', generation: 3 }, { civId: 'world', generation: 3 }), false)
  assert.equal(isViewportReadCurrent({ civId: 'china', generation: 3 }, { civId: 'china', generation: 4 }), false)
  assert.equal(isViewportReadCurrent({ civId: 'china', generation: 3 }, { civId: 'china', generation: 3 }), true)
})
