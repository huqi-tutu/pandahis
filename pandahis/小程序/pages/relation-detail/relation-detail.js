const protoPage = require('../../behaviors/proto-page.js')
const { getRelations } = require('../../data/data-loader.js')

const CATEGORY_COLOR = {
  '家庭': '#84572F',
  '君臣': '#92ADA4',
  '师从': '#9ABCC8',
  '敌对': '#E85D5D',
}

Page({
  behaviors: [protoPage],

  data: {
    name: '',
    boxTitle: '',
    info: null,
    color: '#8A8A8A',
  },

  onLoad(options) {
    const name     = options.name ? decodeURIComponent(options.name) : ''
    const boxTitle = options.box  ? decodeURIComponent(options.box)  : ''

    // 从关系数据中查找该节点的详情
    const rel = getRelations(boxTitle)
    let info = null

    for (const group of rel.groups) {
      const found = group.items.find(item => item.name === name)
      if (found) {
        info = {
          ...found,
          category: group.category,
        }
        break
      }
    }

    // 构建家族关系链
    let lineage = ''
    if (info) {
      const parts = [info.parent1, info.parent2, info.parent3, info.parent4].filter(Boolean)
      if (parts.length > 0) {
        lineage = boxTitle + ' → ' + parts.join(' → ')
      }
    }

    this.setData({
      name,
      boxTitle,
      info: info ? { ...info, lineage } : null,
      color: info ? (CATEGORY_COLOR[info.category] || '#8A8A8A') : '#8A8A8A',
    })
  },
})
