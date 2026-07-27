'use strict'

const test = require('node:test')
const assert = require('node:assert/strict')
const { hasNodeOverlap, layoutMaxRadius } = require('../utils/relation-mindmap-layout')

test('mindmap layout avoids overlap for dense family siblings', () => {
  const sons = [
    '伯邑考',
    '武王',
    '管叔',
    '周公',
    '蔡叔',
    '曹叔',
    '成叔',
    '霍叔',
    '康叔',
    '冉季',
  ]
  const nodes = [
    { key: 'center', name: '周文王', type: 'person' },
    {
      key: 'cat_family',
      name: '家庭',
      type: 'category',
      extraJson: JSON.stringify({ isCategoryNode: true, 关系类别: '家庭' }),
    },
    { key: 'wife', name: '太姒', type: 'person', extraJson: JSON.stringify({ 关系类别: '家庭' }) },
    ...sons.map((name, i) => ({
      key: `son${i}`,
      name,
      type: 'person',
      extraJson: JSON.stringify({ 关系类别: '家庭' }),
    })),
  ]
  const edges = [
    { fromKey: 'center', toKey: 'cat_family', label: '' },
    { fromKey: 'cat_family', toKey: 'wife', label: '妻' },
    ...sons.map((_, i) => ({ fromKey: 'wife', toKey: `son${i}`, label: '儿子' })),
  ]
  assert.equal(hasNodeOverlap('center', nodes, edges), false)
  const spread = layoutMaxRadius('center', nodes, edges)
  assert.ok(spread < 480, `layout too spread out: ${spread}`)
})
