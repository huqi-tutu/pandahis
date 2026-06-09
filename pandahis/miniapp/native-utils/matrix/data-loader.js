/**
 * 历史图谱 · 数据加载器
 * 从 JSON 数据文件加载关系、评述、见证数据
 * 按关联史略名称筛选
 */

const RELATIONS = require('../assets/data/relations.js')
const CRITIQUES = require('../assets/data/critiques.js')
const RELICS    = require('../assets/data/relics.js')

/**
 * 获取某史略的关系数据，按类别分组
 * @param {string} boxTitle - 史略名称，如"黄帝"
 * @returns {Object} { groups: [{category, items}], total }
 */
function getRelations(boxTitle) {
  const filtered = RELATIONS.filter(r => r['关联史略名称'] === boxTitle)

  // 按关系类别分组
  const categoryOrder = ['家庭', '君臣', '师从', '敌对']
  const categoryMap = {}

  filtered.forEach(item => {
    const cat = item['关系类别'] || '其他'
    if (!categoryMap[cat]) categoryMap[cat] = []
    categoryMap[cat].push({
      id:        item['关系ID'],
      name:      item['关系节点标题'],
      role:      item['上级连接线标题'],
      level:     item['关系层级'],
      summary:   item['关系简述'],
      parent1:   item['所属一级关系'],
      parent2:   item['所属二级关系'],
      parent3:   item['所属三级关系'],
      parent4:   item['所属四级关系'],
    })
  })

  const groups = categoryOrder
    .filter(cat => categoryMap[cat])
    .map(cat => ({
      category: cat,
      icon: CATEGORY_ICON[cat] || '●',
      color:  CATEGORY_COLOR[cat] || '#8A8A8A',
      items:  categoryMap[cat],
    }))

  // 处理不在 categoryOrder 里的类别
  Object.keys(categoryMap).forEach(cat => {
    if (!categoryOrder.includes(cat)) {
      groups.push({
        category: cat,
        icon: '●',
        color: '#8A8A8A',
        items: categoryMap[cat],
      })
    }
  })

  return { groups, total: filtered.length }
}

const CATEGORY_ICON = {
  '家庭': '👨‍👩‍👧‍👦',
  '君臣': '⚔️',
  '师从': '📖',
  '敌对': '🔥',
}

const CATEGORY_COLOR = {
  '家庭': '#5b8a72',  // 青绿
  '君臣': '#8e7ca8',  // 紫灰
  '师从': '#5b7fa8',  // 蓝灰
  '敌对': '#b87a6b',  // 暖褐
}

/**
 * 获取某史略的评述数据
 * @param {string} boxTitle - 史略名称
 * @returns {Array} 评述列表
 */
function getCritiques(boxTitle) {
  return CRITIQUES
    .filter(c => c['关联史略名称'] === boxTitle)
    .map(c => ({
      title:   c['评述标题'],
      author:  c['评述人'],
      book:    c['评述著作'],
      era:     c['评述年代'],
      content: c['评述内容'],
      summary: c['简介'],
    }))
}

/**
 * 获取某史略的见证（文物）数据，按优先级排序
 * @param {string} boxTitle - 史略名称
 * @returns {Array} 文物列表
 */
function getRelics(boxTitle) {
  const priorityOrder = { P0: 0, P1: 1, P2: 2, P3: 3 }
  return RELICS
    .filter(r => r['关联史略名称'] === boxTitle)
    .sort((a, b) => {
      const pa = priorityOrder[a['优先级']] ?? 9
      const pb = priorityOrder[b['优先级']] ?? 9
      return pa - pb
    })
    .map(r => ({
      name:     r['文物名称'],
      location: r['现藏地点'],
      detail:   r['详细介绍'],
      summary:  r['简介'],
      image:    r['图片'],
    }))
}

module.exports = { getRelations, getCritiques, getRelics }
