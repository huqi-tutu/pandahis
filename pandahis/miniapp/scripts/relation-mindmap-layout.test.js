'use strict'

const test = require('node:test')
const assert = require('node:assert/strict')
const { hasNodeOverlap, layoutMaxRadius } = require('../utils/relation-mindmap-layout')

test('mindmap layout avoids overlap for dense family siblings under 配偶 hub', () => {
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
      key: 'cat_fam',
      name: '家庭',
      type: 'category',
      extraJson: JSON.stringify({ isCategoryNode: true, 关系类别: '家庭' }),
    },
    {
      key: 'sub_spouses',
      name: '配偶',
      type: 'subcategory',
      extraJson: JSON.stringify({
        isSubCategoryNode: true,
        节点类型: '二级分类',
        关系类别: '家庭',
      }),
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
    { fromKey: 'center', toKey: 'cat_fam', label: '' },
    { fromKey: 'cat_fam', toKey: 'sub_spouses', label: '' },
    { fromKey: 'sub_spouses', toKey: 'wife', label: '正妻' },
    ...sons.map((_, i) => ({ fromKey: 'wife', toKey: `son${i}`, label: '子' })),
  ]
  assert.equal(hasNodeOverlap('center', nodes, edges), false)
  const spread = layoutMaxRadius('center', nodes, edges)
  assert.ok(spread < 720, `layout too spread out: ${spread}`)
})
