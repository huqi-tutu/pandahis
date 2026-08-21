'use strict'

const test = require('node:test')
const assert = require('node:assert/strict')
const {
  hasNodeOverlap,
  layoutMaxRadius,
  prepareRelationGraph,
  childWithinParentWedge,
  minCategorySectorGapRadians,
  CATEGORY_SECTOR_GAP_DEG,
  RING_RADIUS,
} = require('../utils/relation-mindmap-layout')

function famExtra() {
  return JSON.stringify({ 关系类别: '家庭' })
}
function hub(name, key) {
  return {
    key,
    name,
    type: 'subcategory',
    extraJson: JSON.stringify({
      isSubCategoryNode: true,
      节点类型: '二级分类',
      关系类别: '家庭',
    }),
  }
}

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
    hub('配偶', 'sub_spouses'),
    { key: 'wife', name: '太姒', type: 'person', extraJson: famExtra() },
    ...sons.map((name, i) => ({
      key: `son${i}`,
      name,
      type: 'person',
      extraJson: famExtra(),
    })),
  ]
  const edges = [
    { fromKey: 'center', toKey: 'cat_fam', label: '' },
    { fromKey: 'cat_fam', toKey: 'sub_spouses', label: '' },
    { fromKey: 'sub_spouses', toKey: 'wife', label: '妻' },
    ...sons.map((_, i) => ({ fromKey: 'wife', toKey: `son${i}`, label: '子' })),
  ]
  assert.equal(hasNodeOverlap('center', nodes, edges), false)
  const spread = layoutMaxRadius('center', nodes, edges)
  assert.ok(spread <= 760, `layout too spread out: ${spread}`)
  assert.ok(spread >= 180, `layout unexpectedly collapsed: ${spread}`)
  // 十子同圆、够摆开即可（不必占满家庭扇区），彼此不得叠牌
  const preparedDense = prepareRelationGraph('center', nodes, edges)
  const sonPts = sons.map((_, i) => {
    const p = preparedDense.positions.get(`son${i}`)
    assert.ok(p)
    return p
  })
  const radii = sonPts.map((p) => Math.hypot(p.x, p.y))
  const r0 = radii[0]
  for (const r of radii) {
    assert.ok(Math.abs(r - r0) < 1.5, `十子须在同一圆上: ${r} vs ${r0}`)
  }
  const sonAngs = sonPts.map((p) => Math.atan2(p.y, p.x)).sort((a, b) => a - b)
  const sonSpan = sonAngs[sonAngs.length - 1] - sonAngs[0]
  assert.ok(sonSpan >= 0.55, `十子应有足够跨度以摆开，span=${sonSpan}`)
  assert.ok(sonSpan <= Math.PI * 2 + 0.01, `十子跨度不应无意义撑满整圈: ${sonSpan}`)
  for (let i = 0; i < sons.length; i++) {
    for (let j = i + 1; j < sons.length; j++) {
      const dist = Math.hypot(sonPts[i].x - sonPts[j].x, sonPts[i].y - sonPts[j].y)
      assert.ok(dist >= 36, `十子叠牌: ${sons[i]}/${sons[j]} dist=${dist}`)
    }
  }
})

test('friend persons hanging on category get a visible 好友 hub on ring1', () => {
  const nodes = [
    { key: 'center', name: '尧', type: 'person' },
    {
      key: 'cat_fri',
      name: '好友',
      type: 'category',
      extraJson: JSON.stringify({ isCategoryNode: true, 关系类别: '好友' }),
    },
    { key: 'p1', name: '许由', type: 'person', extraJson: JSON.stringify({ 关系类别: '好友' }) },
    { key: 'p2', name: '巢父', type: 'person', extraJson: JSON.stringify({ 关系类别: '好友' }) },
  ]
  const edges = [
    { fromKey: 'center', toKey: 'cat_fri', label: '' },
    { fromKey: 'cat_fri', toKey: 'p1', label: '' },
    { fromKey: 'cat_fri', toKey: 'p2', label: '' },
  ]
  const prepared = prepareRelationGraph('center', nodes, edges)
  const hubNode = prepared.nodes.find((n) => n.name === '好友' && n.type === 'subcategory')
  assert.ok(hubNode, 'expected synthetic 好友 subcategory hub')
  const hubPos = prepared.positions.get(hubNode.key)
  assert.ok(hubPos, 'hub should be positioned')
  const r = Math.hypot(hubPos.x, hubPos.y)
  assert.ok(
    r > RING_RADIUS[1] - 8 && r < RING_RADIUS[1] + 8,
    `hub should sit on ring1, got r=${r}`
  )
})

test('武王式：圈3 唐叔虞落在家庭一级扇区内（不挤在周公小角）', () => {
  const siblings = [
    '伯邑考',
    '管叔鲜',
    '周公旦',
    '蔡叔度',
    '曹叔振铎',
    '成叔武',
    '霍叔处',
    '康叔封',
    '冉季载',
  ]
  const nodes = [
    { key: 'center', name: '周武王', type: 'person' },
    {
      key: 'cat_fam',
      name: '家庭',
      type: 'category',
      extraJson: JSON.stringify({ isCategoryNode: true, 关系类别: '家庭' }),
    },
    hub('父母', 'sub_parents'),
    hub('配偶', 'sub_spouses'),
    hub('兄弟姐妹', 'sub_sibs'),
    { key: 'father', name: '周文王', type: 'person', extraJson: famExtra() },
    { key: 'mother', name: '太姒', type: 'person', extraJson: famExtra() },
    { key: 'wife', name: '邑姜', type: 'person', extraJson: famExtra() },
    { key: 'cheng', name: '成王诵', type: 'person', extraJson: famExtra() },
    ...siblings.map((name, i) => ({
      key: `sib${i}`,
      name,
      type: 'person',
      extraJson: famExtra(),
    })),
    { key: 'tang', name: '唐叔虞', type: 'person', extraJson: famExtra() },
  ]
  const zhouKey = `sib${siblings.indexOf('周公旦')}`
  const edges = [
    { fromKey: 'center', toKey: 'cat_fam', label: '' },
    { fromKey: 'cat_fam', toKey: 'sub_parents', label: '' },
    { fromKey: 'cat_fam', toKey: 'sub_spouses', label: '' },
    { fromKey: 'cat_fam', toKey: 'sub_sibs', label: '' },
    { fromKey: 'sub_parents', toKey: 'father', label: '父' },
    { fromKey: 'sub_parents', toKey: 'mother', label: '母' },
    { fromKey: 'sub_spouses', toKey: 'wife', label: '妻' },
    { fromKey: 'wife', toKey: 'cheng', label: '子' },
    ...siblings.map((_, i) => ({ fromKey: 'sub_sibs', toKey: `sib${i}`, label: '弟' })),
    { fromKey: zhouKey, toKey: 'tang', label: '子' },
  ]

  assert.equal(hasNodeOverlap('center', nodes, edges), false)
  const prepared = prepareRelationGraph('center', nodes, edges)
  const tang = prepared.positions.get('tang')
  assert.ok(tang)
  const famHubs = ['sub_parents', 'sub_spouses', 'sub_sibs']
  const hubAngs = famHubs.map((k) => {
    const p = prepared.positions.get(k)
    assert.ok(p)
    return Math.atan2(p.y, p.x)
  })
  const lo = Math.min(...hubAngs) - 0.35
  const hi = Math.max(...hubAngs) + 0.35
  const tAng = Math.atan2(tang.y, tang.x)
  assert.ok(tAng >= lo && tAng <= hi, `唐叔虞应在家庭一级扇区附近: ang=${tAng} lo=${lo} hi=${hi}`)

  // 圈1 三个枢纽不应严重重叠
  for (let i = 0; i < famHubs.length; i++) {
    for (let j = i + 1; j < famHubs.length; j++) {
      const a = prepared.positions.get(famHubs[i])
      const b = prepared.positions.get(famHubs[j])
      assert.ok(a && b)
      const dist = Math.hypot(a.x - b.x, a.y - b.y)
      assert.ok(dist >= 40, `hubs ${famHubs[i]} vs ${famHubs[j]} too close: ${dist}`)
    }
  }
})

test('二级枢纽直接人物超过 10 时前端截断至 10', () => {
  const ministers = Array.from({ length: 15 }, (_, i) => `臣${i + 1}`)
  const nodes = [
    { key: 'center', name: '某王', type: 'person' },
    {
      key: 'cat_col',
      name: '同僚',
      type: 'category',
      extraJson: JSON.stringify({ isCategoryNode: true, 关系类别: '同僚' }),
    },
    {
      key: 'sub_min',
      name: '臣子',
      type: 'subcategory',
      extraJson: JSON.stringify({
        isSubCategoryNode: true,
        节点类型: '二级分类',
        关系类别: '同僚',
      }),
    },
    ...ministers.map((name, i) => ({
      key: `m${i}`,
      name,
      type: 'person',
      extraJson: JSON.stringify({ 关系类别: '同僚' }),
    })),
  ]
  const edges = [
    { fromKey: 'center', toKey: 'cat_col', label: '' },
    { fromKey: 'cat_col', toKey: 'sub_min', label: '' },
    ...ministers.map((_, i) => ({ fromKey: 'sub_min', toKey: `m${i}`, label: '' })),
  ]
  const prepared = prepareRelationGraph('center', nodes, edges)
  const shown = ministers.filter((_, i) => prepared.positions.has(`m${i}`))
  assert.equal(shown.length, 10, `expected 10 ministers, got ${shown.length}`)
  assert.ok(prepared.positions.has('m0'))
  assert.ok(prepared.positions.has('m9'))
  assert.equal(prepared.positions.has('m10'), false)
})

test('武王：外敌人物不得闯入臣子/兄弟姐妹角域', () => {
  const ministers = Array.from({ length: 6 }, (_, i) => `臣${i}`)
  const sibs = ['管叔鲜', '周公旦', '蔡叔度', '史佚']
  const nodes = [
    { key: 'center', name: '周武王', type: 'person' },
    {
      key: 'cat_fam',
      name: '家庭',
      type: 'category',
      extraJson: JSON.stringify({ isCategoryNode: true, 关系类别: '家庭' }),
    },
    {
      key: 'cat_col',
      name: '同僚',
      type: 'category',
      extraJson: JSON.stringify({ isCategoryNode: true, 关系类别: '同僚' }),
    },
    {
      key: 'cat_ene',
      name: '敌对',
      type: 'category',
      extraJson: JSON.stringify({ isCategoryNode: true, 关系类别: '敌对' }),
    },
    hub('兄弟姐妹', 'sub_sibs'),
    {
      key: 'sub_min',
      name: '臣子',
      type: 'subcategory',
      extraJson: JSON.stringify({
        isSubCategoryNode: true,
        节点类型: '二级分类',
        关系类别: '同僚',
      }),
    },
    {
      key: 'sub_foe',
      name: '外敌',
      type: 'subcategory',
      extraJson: JSON.stringify({
        isSubCategoryNode: true,
        节点类型: '二级分类',
        关系类别: '敌对',
      }),
    },
    ...sibs.map((name, i) => ({
      key: `sib${i}`,
      name,
      type: 'person',
      extraJson: famExtra(),
    })),
    ...ministers.map((name, i) => ({
      key: `m${i}`,
      name,
      type: 'person',
      extraJson: JSON.stringify({ 关系类别: '同僚' }),
    })),
    {
      key: 'foe',
      name: '商纣王',
      type: 'person',
      extraJson: JSON.stringify({ 关系类别: '敌对' }),
    },
  ]
  // hub() helper tags 家庭; override 兄弟姐妹 already via hub()
  const edges = [
    { fromKey: 'center', toKey: 'cat_fam', label: '' },
    { fromKey: 'center', toKey: 'cat_col', label: '' },
    { fromKey: 'center', toKey: 'cat_ene', label: '' },
    { fromKey: 'cat_fam', toKey: 'sub_sibs', label: '' },
    { fromKey: 'cat_col', toKey: 'sub_min', label: '' },
    { fromKey: 'cat_ene', toKey: 'sub_foe', label: '' },
    ...sibs.map((_, i) => ({ fromKey: 'sub_sibs', toKey: `sib${i}`, label: '弟' })),
    ...ministers.map((_, i) => ({ fromKey: 'sub_min', toKey: `m${i}`, label: '' })),
    { fromKey: 'sub_foe', toKey: 'foe', label: '' },
  ]

  assert.ok(childWithinParentWedge('center', nodes, edges, 'sub_foe', 'foe'))
  assert.equal(
    childWithinParentWedge('center', nodes, edges, 'sub_min', 'foe'),
    false,
    '商纣王不得落入臣子角域'
  )
  assert.equal(
    childWithinParentWedge('center', nodes, edges, 'sub_sibs', 'foe'),
    false,
    '商纣王不得落入兄弟姐妹角域'
  )
  for (let i = 0; i < ministers.length; i++) {
    assert.ok(childWithinParentWedge('center', nodes, edges, 'sub_min', `m${i}`))
  }
  for (let i = 0; i < sibs.length; i++) {
    assert.ok(childWithinParentWedge('center', nodes, edges, 'sub_sibs', `sib${i}`))
  }
  assert.equal(hasNodeOverlap('center', nodes, edges), false)
})

test('圈2 臣子多人标签不得重叠（文王/武王式同僚扇区）', () => {
  const ministers = ['太颠', '闳夭', '散宜生', '鬻熊', '辛甲大夫', '南宫适', '尹佚', '虢叔', '毕公', '召公']
  const nodes = [
    { key: 'center', name: '周文王', type: 'person' },
    {
      key: 'cat_fam',
      name: '家庭',
      type: 'category',
      extraJson: JSON.stringify({ isCategoryNode: true, 关系类别: '家庭' }),
    },
    {
      key: 'cat_col',
      name: '同僚',
      type: 'category',
      extraJson: JSON.stringify({ isCategoryNode: true, 关系类别: '同僚' }),
    },
    {
      key: 'sub_parents',
      name: '父母',
      type: 'subcategory',
      extraJson: JSON.stringify({
        isSubCategoryNode: true,
        节点类型: '二级分类',
        关系类别: '家庭',
      }),
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
    {
      key: 'sub_king',
      name: '君王',
      type: 'subcategory',
      extraJson: JSON.stringify({
        isSubCategoryNode: true,
        节点类型: '二级分类',
        关系类别: '同僚',
      }),
    },
    {
      key: 'sub_min',
      name: '臣子',
      type: 'subcategory',
      extraJson: JSON.stringify({
        isSubCategoryNode: true,
        节点类型: '二级分类',
        关系类别: '同僚',
      }),
    },
    {
      key: 'sub_col',
      name: '同僚',
      type: 'subcategory',
      extraJson: JSON.stringify({
        isSubCategoryNode: true,
        节点类型: '二级分类',
        关系类别: '同僚',
      }),
    },
    { key: 'father', name: '王季', type: 'person', extraJson: famExtra() },
    { key: 'mother', name: '太任', type: 'person', extraJson: famExtra() },
    { key: 'wife', name: '太姒', type: 'person', extraJson: famExtra() },
    {
      key: 'king',
      name: '商纣',
      type: 'person',
      extraJson: JSON.stringify({ 关系类别: '同僚' }),
    },
    {
      key: 'peer',
      name: '伯夷',
      type: 'person',
      extraJson: JSON.stringify({ 关系类别: '同僚' }),
    },
    ...ministers.map((name, i) => ({
      key: `m${i}`,
      name,
      type: 'person',
      extraJson: JSON.stringify({ 关系类别: '同僚' }),
    })),
  ]
  const edges = [
    { fromKey: 'center', toKey: 'cat_fam', label: '' },
    { fromKey: 'center', toKey: 'cat_col', label: '' },
    { fromKey: 'cat_fam', toKey: 'sub_parents', label: '' },
    { fromKey: 'cat_fam', toKey: 'sub_spouses', label: '' },
    { fromKey: 'cat_col', toKey: 'sub_king', label: '' },
    { fromKey: 'cat_col', toKey: 'sub_min', label: '' },
    { fromKey: 'cat_col', toKey: 'sub_col', label: '' },
    { fromKey: 'sub_parents', toKey: 'father', label: '父' },
    { fromKey: 'sub_parents', toKey: 'mother', label: '母' },
    { fromKey: 'sub_spouses', toKey: 'wife', label: '妻' },
    { fromKey: 'sub_king', toKey: 'king', label: '' },
    { fromKey: 'sub_col', toKey: 'peer', label: '' },
    ...ministers.map((_, i) => ({ fromKey: 'sub_min', toKey: `m${i}`, label: '' })),
  ]

  assert.equal(hasNodeOverlap('center', nodes, edges), false)
  const prepared = prepareRelationGraph('center', nodes, edges)
  for (let i = 0; i < ministers.length; i++) {
    for (let j = i + 1; j < ministers.length; j++) {
      const a = prepared.positions.get(`m${i}`)
      const b = prepared.positions.get(`m${j}`)
      assert.ok(a && b)
      const dist = Math.hypot(a.x - b.x, a.y - b.y)
      assert.ok(dist >= 48, `臣子 ${ministers[i]}/${ministers[j]} 过近: ${dist}`)
    }
  }
})

test('圈2 同枢纽人物等分，且多人数枢纽扇区明显宽于少人数枢纽', () => {
  const siblings = Array.from({ length: 9 }, (_, i) => `弟${i}`)
  const nodes = [
    { key: 'center', name: '周武王', type: 'person' },
    {
      key: 'cat_fam',
      name: '家庭',
      type: 'category',
      extraJson: JSON.stringify({ isCategoryNode: true, 关系类别: '家庭' }),
    },
    {
      key: 'sub_parents',
      name: '父母',
      type: 'subcategory',
      extraJson: JSON.stringify({
        isSubCategoryNode: true,
        节点类型: '二级分类',
        关系类别: '家庭',
      }),
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
    {
      key: 'sub_sibs',
      name: '兄弟姐妹',
      type: 'subcategory',
      extraJson: JSON.stringify({
        isSubCategoryNode: true,
        节点类型: '二级分类',
        关系类别: '家庭',
      }),
    },
    { key: 'father', name: '周文王', type: 'person', extraJson: famExtra() },
    { key: 'mother', name: '太姒', type: 'person', extraJson: famExtra() },
    { key: 'wife', name: '邑姜', type: 'person', extraJson: famExtra() },
    ...siblings.map((name, i) => ({
      key: `sib${i}`,
      name,
      type: 'person',
      extraJson: famExtra(),
    })),
  ]
  const edges = [
    { fromKey: 'center', toKey: 'cat_fam', label: '' },
    { fromKey: 'cat_fam', toKey: 'sub_parents', label: '' },
    { fromKey: 'cat_fam', toKey: 'sub_spouses', label: '' },
    { fromKey: 'cat_fam', toKey: 'sub_sibs', label: '' },
    { fromKey: 'sub_parents', toKey: 'father', label: '父' },
    { fromKey: 'sub_parents', toKey: 'mother', label: '母' },
    { fromKey: 'sub_spouses', toKey: 'wife', label: '妻' },
    ...siblings.map((_, i) => ({ fromKey: 'sub_sibs', toKey: `sib${i}`, label: '弟' })),
  ]

  const prepared = prepareRelationGraph('center', nodes, edges)
  const ang = (key) => {
    const p = prepared.positions.get(key)
    assert.ok(p, key)
    return Math.atan2(p.y, p.x)
  }
  const signedDelta = (a, b) => {
    let d = b - a
    while (d > Math.PI) d -= Math.PI * 2
    while (d < -Math.PI) d += Math.PI * 2
    return d
  }

  // 按布局顺序（边序）量相邻角距，避开 ±π 排序陷阱
  const sibKeys = siblings.map((_, i) => `sib${i}`)
  const sibGaps = []
  for (let i = 1; i < sibKeys.length; i++) {
    sibGaps.push(Math.abs(signedDelta(ang(sibKeys[i - 1]), ang(sibKeys[i]))))
  }
  const mean = sibGaps.reduce((s, g) => s + g, 0) / sibGaps.length
  for (const g of sibGaps) {
    assert.ok(Math.abs(g - mean) / mean < 0.12, `兄弟姐妹角距不均: gap=${g} mean=${mean}`)
  }

  const parentSpan = Math.abs(signedDelta(ang('father'), ang('mother')))
  const sibSpan = sibGaps.reduce((s, g) => s + g, 0)
  // 9 人兄弟张角应明显大于 2 人父母
  assert.ok(
    sibSpan / Math.max(parentSpan, 0.01) >= 3.2,
    `兄弟姐妹扇区过窄或父母过宽: sibSpan=${sibSpan} parentSpan=${parentSpan}`
  )
  // 人均角距不应差太多（标签保底后父母可略宽，但不应数倍）
  assert.ok(
    parentSpan / mean < 2.2,
    `父母人均过松: parentSpan=${parentSpan} sibMean=${mean}`
  )
})

test('跨一级扇区：老师与父母胶囊不得重叠（武王接缝场景）', () => {
  const nodes = [
    { key: 'center', name: '周武王', type: 'person' },
    {
      key: 'cat_fam',
      name: '家庭',
      type: 'category',
      extraJson: JSON.stringify({ isCategoryNode: true, 关系类别: '家庭' }),
    },
    {
      key: 'cat_col',
      name: '同僚',
      type: 'category',
      extraJson: JSON.stringify({ isCategoryNode: true, 关系类别: '同僚' }),
    },
    {
      key: 'cat_ene',
      name: '敌对',
      type: 'category',
      extraJson: JSON.stringify({ isCategoryNode: true, 关系类别: '敌对' }),
    },
    {
      key: 'cat_tea',
      name: '师徒',
      type: 'category',
      extraJson: JSON.stringify({ isCategoryNode: true, 关系类别: '师徒' }),
    },
    {
      key: 'sub_parents',
      name: '父母',
      type: 'subcategory',
      extraJson: JSON.stringify({
        isSubCategoryNode: true,
        节点类型: '二级分类',
        关系类别: '家庭',
      }),
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
    {
      key: 'sub_sibs',
      name: '兄弟姐妹',
      type: 'subcategory',
      extraJson: JSON.stringify({
        isSubCategoryNode: true,
        节点类型: '二级分类',
        关系类别: '家庭',
      }),
    },
    {
      key: 'sub_min',
      name: '臣子',
      type: 'subcategory',
      extraJson: JSON.stringify({
        isSubCategoryNode: true,
        节点类型: '二级分类',
        关系类别: '同僚',
      }),
    },
    {
      key: 'sub_foe',
      name: '外敌',
      type: 'subcategory',
      extraJson: JSON.stringify({
        isSubCategoryNode: true,
        节点类型: '二级分类',
        关系类别: '敌对',
      }),
    },
    {
      key: 'sub_teacher',
      name: '老师',
      type: 'subcategory',
      extraJson: JSON.stringify({
        isSubCategoryNode: true,
        节点类型: '二级分类',
        关系类别: '师徒',
      }),
    },
    { key: 'father', name: '周文王', type: 'person', extraJson: famExtra() },
    { key: 'mother', name: '太姒', type: 'person', extraJson: famExtra() },
    { key: 'wife', name: '邑姜', type: 'person', extraJson: famExtra() },
    ...Array.from({ length: 9 }, (_, i) => ({
      key: `sib${i}`,
      name: `弟${i}`,
      type: 'person',
      extraJson: famExtra(),
    })),
    ...Array.from({ length: 10 }, (_, i) => ({
      key: `m${i}`,
      name: `臣${i}`,
      type: 'person',
      extraJson: JSON.stringify({ 关系类别: '同僚' }),
    })),
    {
      key: 'foe',
      name: '纣',
      type: 'person',
      extraJson: JSON.stringify({ 关系类别: '敌对' }),
    },
    {
      key: 'teacher',
      name: '姜太公',
      type: 'person',
      extraJson: JSON.stringify({ 关系类别: '师徒' }),
    },
  ]
  const edges = [
    { fromKey: 'center', toKey: 'cat_fam', label: '' },
    { fromKey: 'center', toKey: 'cat_col', label: '' },
    { fromKey: 'center', toKey: 'cat_ene', label: '' },
    { fromKey: 'center', toKey: 'cat_tea', label: '' },
    { fromKey: 'cat_fam', toKey: 'sub_parents', label: '' },
    { fromKey: 'cat_fam', toKey: 'sub_spouses', label: '' },
    { fromKey: 'cat_fam', toKey: 'sub_sibs', label: '' },
    { fromKey: 'cat_col', toKey: 'sub_min', label: '' },
    { fromKey: 'cat_ene', toKey: 'sub_foe', label: '' },
    { fromKey: 'cat_tea', toKey: 'sub_teacher', label: '' },
    { fromKey: 'sub_parents', toKey: 'father', label: '父' },
    { fromKey: 'sub_parents', toKey: 'mother', label: '母' },
    { fromKey: 'sub_spouses', toKey: 'wife', label: '妻' },
    ...Array.from({ length: 9 }, (_, i) => ({
      fromKey: 'sub_sibs',
      toKey: `sib${i}`,
      label: '弟',
    })),
    ...Array.from({ length: 10 }, (_, i) => ({
      fromKey: 'sub_min',
      toKey: `m${i}`,
      label: '',
    })),
    { fromKey: 'sub_foe', toKey: 'foe', label: '' },
    { fromKey: 'sub_teacher', toKey: 'teacher', label: '' },
  ]

  const prepared = prepareRelationGraph('center', nodes, edges)
  const parents = prepared.positions.get('sub_parents')
  const teacher = prepared.positions.get('sub_teacher')
  assert.ok(parents && teacher, '父母/老师枢纽须存在')
  const dist = Math.hypot(parents.x - teacher.x, parents.y - teacher.y)
  // 胶囊半宽约 24~30，间距应明显大于相切弦长
  assert.ok(dist >= 56, `老师与父母胶囊重叠或过近: dist=${dist}`)
  assert.equal(hasNodeOverlap('center', nodes, edges), false)

  // 任意两圈1枢纽中心距均须达标
  const hubKeys = [
    'sub_parents',
    'sub_spouses',
    'sub_sibs',
    'sub_min',
    'sub_foe',
    'sub_teacher',
  ]
  for (let i = 0; i < hubKeys.length; i++) {
    for (let j = i + 1; j < hubKeys.length; j++) {
      const a = prepared.positions.get(hubKeys[i])
      const b = prepared.positions.get(hubKeys[j])
      assert.ok(a && b)
      const d = Math.hypot(a.x - b.x, a.y - b.y)
      assert.ok(d >= 52, `hub ${hubKeys[i]} vs ${hubKeys[j]} too close: ${d}`)
    }
  }
})

test('魏文侯式：圈4 多孙辈同圆且不叠牌（不被圈3 窄楔夹死）', () => {
  const nodes = [
    { key: 'center', name: '魏文侯', type: 'person' },
    {
      key: 'cat_fam',
      name: '家庭',
      type: 'category',
      extraJson: JSON.stringify({ isCategoryNode: true, 关系类别: '家庭' }),
    },
    hub('配偶', 'sub_spouses'),
    { key: 'wife', name: '文侯正妻', type: 'person', extraJson: famExtra() },
    { key: 'son', name: '子击', type: 'person', extraJson: famExtra() },
    { key: 'g1', name: '魏罃', type: 'person', extraJson: famExtra() },
    { key: 'g2', name: '公子缓', type: 'person', extraJson: famExtra() },
    { key: 'g3', name: '魏嗣', type: 'person', extraJson: famExtra() },
  ]
  const edges = [
    { fromKey: 'center', toKey: 'cat_fam', label: '' },
    { fromKey: 'cat_fam', toKey: 'sub_spouses', label: '' },
    { fromKey: 'sub_spouses', toKey: 'wife', label: '妻' },
    { fromKey: 'wife', toKey: 'son', label: '子' },
    { fromKey: 'son', toKey: 'g1', label: '子' },
    { fromKey: 'son', toKey: 'g2', label: '子' },
    { fromKey: 'son', toKey: 'g3', label: '子' },
  ]
  assert.equal(hasNodeOverlap('center', nodes, edges), false)
  const prepared = prepareRelationGraph('center', nodes, edges)
  const pts = ['g1', 'g2', 'g3'].map((k) => {
    const p = prepared.positions.get(k)
    assert.ok(p)
    return p
  })
  const radii = pts.map((p) => Math.hypot(p.x, p.y))
  for (const r of radii) {
    assert.ok(Math.abs(r - radii[0]) < 1.5, `孙辈须同圆: ${r} vs ${radii[0]}`)
  }
  for (let i = 0; i < pts.length; i++) {
    for (let j = i + 1; j < pts.length; j++) {
      const dist = Math.hypot(pts[i].x - pts[j].x, pts[i].y - pts[j].y)
      assert.ok(dist >= 36, `孙辈叠牌 dist=${dist}`)
    }
  }
})

test('黄帝式：圈3 子女摊开家庭扇区，圈4 仍靠近圈3 父节点', () => {
  const nodes = [
    { key: 'center', name: '黄帝', type: 'person' },
    {
      key: 'cat_fam',
      name: '家庭',
      type: 'category',
      extraJson: JSON.stringify({ isCategoryNode: true, 关系类别: '家庭' }),
    },
    hub('配偶', 'sub_spouses'),
    { key: 'lei', name: '嫘祖', type: 'person', extraJson: famExtra() },
    { key: 'mo', name: '嫫母', type: 'person', extraJson: famExtra() },
    { key: 'xuan', name: '玄嚣', type: 'person', extraJson: famExtra() },
    { key: 'chang', name: '昌意', type: 'person', extraJson: famExtra() },
    { key: 'zhuan', name: '颛顼', type: 'person', extraJson: famExtra() },
  ]
  const edges = [
    { fromKey: 'center', toKey: 'cat_fam', label: '' },
    { fromKey: 'cat_fam', toKey: 'sub_spouses', label: '' },
    { fromKey: 'sub_spouses', toKey: 'lei', label: '妻' },
    { fromKey: 'sub_spouses', toKey: 'mo', label: '妾' },
    { fromKey: 'lei', toKey: 'xuan', label: '子' },
    { fromKey: 'lei', toKey: 'chang', label: '子' },
    { fromKey: 'chang', toKey: 'zhuan', label: '子' },
  ]
  // 圈4 仍跟圈3 父节点角域
  assert.ok(childWithinParentWedge('center', nodes, edges, 'chang', 'zhuan'))
  const prepared = prepareRelationGraph('center', nodes, edges)
  const a = prepared.positions.get('xuan')
  const b = prepared.positions.get('chang')
  assert.ok(a && b)
  const dist = Math.hypot(a.x - b.x, a.y - b.y)
  assert.ok(dist >= 28, `玄嚣/昌意 too close: ${dist}`)
  assert.equal(hasNodeOverlap('center', nodes, edges), false)
})

test('汉高祖式：高密度家庭/臣子/敌对阵营不得叠牌（方案 B 弹性扩圈）', () => {
  const famExtra = () => JSON.stringify({ 关系类别: '家庭' })
  const colExtra = () => JSON.stringify({ 关系类别: '同僚' })
  const foeExtra = () => JSON.stringify({ 关系类别: '敌对' })
  const masExtra = () => JSON.stringify({ 关系类别: '师徒' })
  const friExtra = () => JSON.stringify({ 关系类别: '好友' })
  const hubNode = (name, key, group) => ({
    key,
    name,
    type: 'subcategory',
    extraJson: JSON.stringify({
      isSubCategoryNode: true,
      节点类型: '二级分类',
      关系类别: group,
    }),
  })
  const catNode = (name, key, group) => ({
    key,
    name,
    type: 'category',
    extraJson: JSON.stringify({ isCategoryNode: true, 关系类别: group }),
  })
  const person = (key, name, extra) => ({ key, name, type: 'person', extraJson: extra })

  const ministers = [
    '萧何',
    '曹参',
    '张良',
    '韩信',
    '陈平',
    '樊哙',
    '周勃',
    '灌婴',
    '郦食其',
    '王陵',
  ]
  const innerFoes = [
    '韩信',
    '彭越',
    '黥布',
    '陈豨',
    '卢绾',
    '臧荼',
    '利几',
    '贯高',
    '雍齿',
    '曹无伤',
  ]
  const outerFoes = ['项羽', '章邯', '共尉', '韩王信', '冒顿']
  const wives = ['吕后', '戚夫人', '薄太后', '不详']
  const childrenByWife = {
    吕后: ['刘盈', '鲁元公主'],
    戚夫人: ['刘如意'],
    薄太后: ['刘恒'],
    不详: ['刘肥', '刘恢', '刘友', '刘长', '刘建'],
  }

  const nodes = [
    person('center', '汉高祖', famExtra()),
    catNode('家庭', 'cat_fam', '家庭'),
    catNode('同僚', 'cat_col', '同僚'),
    catNode('敌对', 'cat_foe', '敌对'),
    catNode('师徒', 'cat_mas', '师徒'),
    catNode('好友', 'cat_fri', '好友'),
    hubNode('父母', 'sub_parents', '家庭'),
    hubNode('配偶', 'sub_spouses', '家庭'),
    hubNode('兄弟姐妹', 'sub_sibs', '家庭'),
    hubNode('臣子', 'sub_min', '同僚'),
    hubNode('内敌', 'sub_in_foe', '敌对'),
    hubNode('外敌', 'sub_out_foe', '敌对'),
    hubNode('老师', 'sub_teacher', '师徒'),
    hubNode('好友', 'sub_friends', '好友'),
    person('father', '刘太公', famExtra()),
    person('mother', '刘媪', famExtra()),
    ...wives.map((n, i) => person(`wife${i}`, n, famExtra())),
    person('sib1', '刘伯', famExtra()),
    person('sib2', '刘仲', famExtra()),
    person('sib3', '刘交', famExtra()),
    ...ministers.map((n, i) => person(`min${i}`, n, colExtra())),
    ...innerFoes.map((n, i) => person(`ifo${i}`, n, foeExtra())),
    ...outerFoes.map((n, i) => person(`ofo${i}`, n, foeExtra())),
    person('teacher', '张良', masExtra()),
    person('friend1', '卢绾', friExtra()),
    person('friend2', '王媪', friExtra()),
  ]

  for (const [wi, wname] of wives.entries()) {
    for (const [ci, cname] of (childrenByWife[wname] || []).entries()) {
      nodes.push(person(`child_${wi}_${ci}`, cname, famExtra()))
    }
  }

  const edges = [
    { fromKey: 'center', toKey: 'cat_fam', label: '' },
    { fromKey: 'center', toKey: 'cat_col', label: '' },
    { fromKey: 'center', toKey: 'cat_foe', label: '' },
    { fromKey: 'center', toKey: 'cat_mas', label: '' },
    { fromKey: 'center', toKey: 'cat_fri', label: '' },
    { fromKey: 'cat_fam', toKey: 'sub_parents', label: '' },
    { fromKey: 'cat_fam', toKey: 'sub_spouses', label: '' },
    { fromKey: 'cat_fam', toKey: 'sub_sibs', label: '' },
    { fromKey: 'cat_col', toKey: 'sub_min', label: '' },
    { fromKey: 'cat_foe', toKey: 'sub_in_foe', label: '' },
    { fromKey: 'cat_foe', toKey: 'sub_out_foe', label: '' },
    { fromKey: 'cat_mas', toKey: 'sub_teacher', label: '' },
    { fromKey: 'cat_fri', toKey: 'sub_friends', label: '' },
    { fromKey: 'sub_parents', toKey: 'father', label: '父' },
    { fromKey: 'sub_parents', toKey: 'mother', label: '母' },
    ...wives.map((_, i) => ({ fromKey: 'sub_spouses', toKey: `wife${i}`, label: '妻' })),
    { fromKey: 'sub_sibs', toKey: 'sib1', label: '兄' },
    { fromKey: 'sub_sibs', toKey: 'sib2', label: '兄' },
    { fromKey: 'sub_sibs', toKey: 'sib3', label: '弟' },
    ...ministers.map((_, i) => ({ fromKey: 'sub_min', toKey: `min${i}`, label: '' })),
    ...innerFoes.map((_, i) => ({ fromKey: 'sub_in_foe', toKey: `ifo${i}`, label: '' })),
    ...outerFoes.map((_, i) => ({ fromKey: 'sub_out_foe', toKey: `ofo${i}`, label: '' })),
    { fromKey: 'sub_teacher', toKey: 'teacher', label: '' },
    { fromKey: 'sub_friends', toKey: 'friend1', label: '' },
    { fromKey: 'sub_friends', toKey: 'friend2', label: '' },
  ]

  for (const [wi, wname] of wives.entries()) {
    for (const [ci, cname] of (childrenByWife[wname] || []).entries()) {
      const label = cname.includes('公主') ? '女' : '子'
      edges.push({ fromKey: `wife${wi}`, toKey: `child_${wi}_${ci}`, label })
    }
  }

  assert.equal(hasNodeOverlap('center', nodes, edges), false)
  const preparedHg = prepareRelationGraph('center', nodes, edges)
  const ring3 = preparedHg.ringRadii[3]
  for (const n of preparedHg.nodes) {
    if (!n.key.startsWith('child_')) continue
    const pt = preparedHg.positions.get(n.key)
    assert.ok(pt, n.name)
    const r = Math.hypot(pt.x, pt.y)
    assert.ok(
      Math.abs(r - ring3) < 1.5,
      `${n.name} 须落在圈3 虚线上: r=${r.toFixed(1)} ring3=${ring3}`
    )
  }
  const spread = layoutMaxRadius('center', nodes, edges)
  assert.ok(spread <= 900, `汉高祖式布局过散: ${spread}`)
  assert.ok(spread >= 180, `汉高祖式布局过扁: ${spread}`)
})

test('一级关系扇区之间保留可见角向缝隙（家庭/好友等边界可辨）', () => {
  const famExtra = () => JSON.stringify({ 关系类别: '家庭' })
  const colExtra = () => JSON.stringify({ 关系类别: '同僚' })
  const foeExtra = () => JSON.stringify({ 关系类别: '敌对' })
  const masExtra = () => JSON.stringify({ 关系类别: '师徒' })
  const friExtra = () => JSON.stringify({ 关系类别: '好友' })
  const hubNode = (name, key, group) => ({
    key,
    name,
    type: 'subcategory',
    extraJson: JSON.stringify({
      isSubCategoryNode: true,
      节点类型: '二级分类',
      关系类别: group,
    }),
  })
  const catNode = (name, key, group) => ({
    key,
    name,
    type: 'category',
    extraJson: JSON.stringify({ isCategoryNode: true, 关系类别: group }),
  })
  const person = (key, name, extra) => ({ key, name, type: 'person', extraJson: extra })
  const nodes = [
    person('center', '汉高祖', famExtra()),
    catNode('家庭', 'cat_fam', '家庭'),
    catNode('同僚', 'cat_col', '同僚'),
    catNode('敌对', 'cat_foe', '敌对'),
    catNode('师徒', 'cat_mas', '师徒'),
    catNode('好友', 'cat_fri', '好友'),
    hubNode('父母', 'sub_parents', '家庭'),
    hubNode('配偶', 'sub_spouses', '家庭'),
    hubNode('臣子', 'sub_min', '同僚'),
    hubNode('内敌', 'sub_in_foe', '敌对'),
    hubNode('老师', 'sub_teacher', '师徒'),
    hubNode('好友', 'sub_friends', '好友'),
    person('father', '刘太公', famExtra()),
    person('wife0', '吕后', famExtra()),
    person('min0', '萧何', colExtra()),
    person('ifo0', '韩信', foeExtra()),
    person('teacher', '张良', masExtra()),
    person('friend1', '卢绾', friExtra()),
  ]
  const edges = [
    { fromKey: 'center', toKey: 'cat_fam', label: '' },
    { fromKey: 'center', toKey: 'cat_col', label: '' },
    { fromKey: 'center', toKey: 'cat_foe', label: '' },
    { fromKey: 'center', toKey: 'cat_mas', label: '' },
    { fromKey: 'center', toKey: 'cat_fri', label: '' },
    { fromKey: 'cat_fam', toKey: 'sub_parents', label: '' },
    { fromKey: 'cat_fam', toKey: 'sub_spouses', label: '' },
    { fromKey: 'cat_col', toKey: 'sub_min', label: '' },
    { fromKey: 'cat_foe', toKey: 'sub_in_foe', label: '' },
    { fromKey: 'cat_mas', toKey: 'sub_teacher', label: '' },
    { fromKey: 'cat_fri', toKey: 'sub_friends', label: '' },
    { fromKey: 'sub_parents', toKey: 'father', label: '父' },
    { fromKey: 'sub_spouses', toKey: 'wife0', label: '妻' },
    { fromKey: 'sub_min', toKey: 'min0', label: '' },
    { fromKey: 'sub_in_foe', toKey: 'ifo0', label: '' },
    { fromKey: 'sub_teacher', toKey: 'teacher', label: '' },
    { fromKey: 'sub_friends', toKey: 'friend1', label: '' },
  ]
  const gap = minCategorySectorGapRadians('center', nodes, edges)
  const expect = (CATEGORY_SECTOR_GAP_DEG * Math.PI) / 180
  assert.ok(gap >= expect * 0.85, `五类齐全时缝隙不足: ${((gap * 180) / Math.PI).toFixed(2)}°`)
})
