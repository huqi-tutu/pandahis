/**
 * 关系图谱 - 树形结构构建与布局算法
 * 视觉与坐标对齐 V5 原型 5 号页（viewBox "-32 -118 588 788"）
 */

function buildRelationTree(relations, rootName) {
  const root = { id: 'root', name: rootName, children: [] }

  const byCategory = {}
  relations.forEach(r => {
    const cat = r['关系类别']
    if (!byCategory[cat]) byCategory[cat] = []
    byCategory[cat].push(r)
  })

  Object.keys(byCategory).forEach(cat => {
    const catNode = { id: 'cat-' + cat, name: cat, type: 'category', children: [] }

    const items = byCategory[cat]
    const levelMap = {}
    items.forEach(item => {
      const node = {
        id: item['关系ID'],
        name: item['关系节点标题'],
        role: item['上级连接线标题'],
        level: item['关系层级'],
        summary: item['关系简述'],
        levelNum: parseLevel(item['关系层级']),
        parentChain: [
          item['所属一级关系'], item['所属二级关系'],
          item['所属三级关系'], item['所属四级关系'],
        ].filter(Boolean),
        children: [],
      }
      if (!levelMap[node.levelNum]) levelMap[node.levelNum] = []
      levelMap[node.levelNum].push(node)
    })

    const levels = Object.keys(levelMap).map(Number).sort((a, b) => a - b)
    levels.forEach((lvl, idx) => {
      if (idx === 0) {
        catNode.children = levelMap[lvl]
      } else {
        const prevLevel = levels[idx - 1]
        levelMap[lvl].forEach(node => {
          const parentName = node.parentChain[node.levelNum - 2]
          const parent = levelMap[prevLevel].find(n => n.name === parentName)
          if (parent) parent.children.push(node)
        })
      }
    })

    root.children.push(catNode)
  })

  return root
}

function parseLevel(levelStr) {
  const map = { '一级': 1, '二级': 2, '三级': 3, '四级': 4, '五级': 5, '六级': 6 }
  return map[levelStr] || 1
}

/** 布局：仅做最小碰撞消解，不做大幅拉伸 */
const LAYOUT_CENTER = { x: 220, y: 400 }
const LAYOUT_SPREAD = 1.12

const V5_ROOT = { x: 220, y: 400, r: 30 }

const V5_CATEGORY = {
  '家庭': { x: 220, y: 312, w: 58, h: 24 },
  '师从': { x: 118, y: 400, w: 64, h: 24 },
  '敌对': { x: 220, y: 488, w: 58, h: 24 },
  '君臣': { x: 328, y: 400, w: 62, h: 24 },
}

/** 人物节点坐标：x, y, r, fontSize */
const V5_NODES = {
  '附宝': { x: 64, y: 198, r: 20, fontSize: 11 },
  '少典': { x: 220, y: 186, r: 20, fontSize: 11 },
  '嫘祖': { x: 392, y: 198, r: 20, fontSize: 11 },
  '玄嚣': { x: 468, y: 138, r: 18, fontSize: 11 },
  '昌意': { x: 296, y: 138, r: 18, fontSize: 11 },
  '蟜极': { x: 490, y: 64, r: 16, fontSize: 11 },
  '昌仆': { x: 242, y: 64, r: 14, fontSize: 10 },
  '颛顼': { x: 358, y: 64, r: 15, fontSize: 11 },
  '颛顼(高阳)': { x: 358, y: 64, r: 15, fontSize: 11 },
  '帝喾': { x: 490, y: 12, r: 14, fontSize: 10 },
  '帝喾(高辛)': { x: 490, y: 12, r: 14, fontSize: 10 },
  '挚': { x: 440, y: -52, r: 13, fontSize: 9 },
  '尧': { x: 548, y: -52, r: 13, fontSize: 9 },
  '尧(放勋)': { x: 548, y: -52, r: 13, fontSize: 9 },
  '岐伯': { x: 48, y: 298, r: 18, fontSize: 11 },
  '广成子': { x: 48, y: 502, r: 18, fontSize: 10 },
  '炎帝': { x: 118, y: 596, r: 18, fontSize: 11 },
  '蚩尤': { x: 220, y: 616, r: 18, fontSize: 11 },
  '荤粥': { x: 322, y: 596, r: 18, fontSize: 11 },
  '风后': { x: 412, y: 292, r: 16, fontSize: 11 },
  '力牧': { x: 412, y: 332, r: 16, fontSize: 11 },
  '常先': { x: 412, y: 372, r: 16, fontSize: 11 },
  '大鸿': { x: 412, y: 412, r: 16, fontSize: 11 },
  '仓颉': { x: 412, y: 452, r: 16, fontSize: 11 },
  '伶伦': { x: 412, y: 492, r: 16, fontSize: 11 },
  '大挠': { x: 412, y: 532, r: 16, fontSize: 11 },
}

function lookupProtoCoord(name) {
  if (V5_NODES[name]) return V5_NODES[name]
  const bare = name.replace(/\(.*$/, '')
  if (V5_NODES[bare]) return V5_NODES[bare]
  const hit = Object.keys(V5_NODES).find(k => name.startsWith(k) || k.startsWith(bare))
  return hit ? V5_NODES[hit] : null
}

function buildCapsule(name, opts = {}) {
  const { isRoot = false, levelNum = 2 } = opts
  const proto = lookupProtoCoord(name)
  const displayName = displayNameOf(name, levelNum)
  const fontSize = isRoot ? 13 : (proto ? proto.fontSize : defaultFontSize(levelNum))
  const w = displayName.length * fontSize * 1.05 + 16
  const h = fontSize + 10
  return { w, h, fontSize, displayName }
}

function displayNameOf(name, levelNum) {
  const bare = name.includes('(') ? name.replace(/\(.*$/, '') : name
  if (bare.length <= 5) return bare
  return levelNum >= 3 ? bare.substring(0, 4) : bare.substring(0, 5)
}

function displayName(name, levelNum) {
  return displayNameOf(name, levelNum)
}

function defaultRadius(levelNum, category, isRoot) {
  if (isRoot) return 30
  if (levelNum === 1) return category === '家庭' ? 20 : (category === '君臣' ? 16 : 18)
  if (levelNum === 2) return 18
  if (levelNum === 3) return 15
  if (levelNum === 4) return 14
  return 13
}

function defaultFontSize(levelNum) {
  if (levelNum >= 5) return 9
  if (levelNum >= 4) return 10
  return 11
}

function nodeMetrics(name, opts = {}) {
  const { isRoot = false, levelNum = 2, category = '家庭' } = opts
  const proto = lookupProtoCoord(name)
  const r = proto ? proto.r : defaultRadius(levelNum, category, isRoot)
  const fontSize = proto ? proto.fontSize : defaultFontSize(levelNum)
  return { r, fontSize, displayName: displayName(name, levelNum), levelNum }
}

function categoryRect(name) {
  const base = V5_CATEGORY[name] || { w: 58, h: 24 }
  return { w: base.w, h: base.h, fontSize: 10 }
}

function edgeAtCircle(cx, cy, r, tx, ty) {
  const dx = tx - cx
  const dy = ty - cy
  const len = Math.hypot(dx, dy)
  if (len < 1e-6) return { x: cx, y: cy }
  return { x: cx + (dx / len) * r, y: cy + (dy / len) * r }
}

function edgeAtRect(cx, cy, w, h, tx, ty) {
  const dx = tx - cx
  const dy = ty - cy
  if (Math.abs(dx) < 1e-6 && Math.abs(dy) < 1e-6) return { x: cx, y: cy }
  const hw = w / 2
  const hh = h / 2
  const scale = Math.min(hw / Math.abs(dx), hh / Math.abs(dy))
  return { x: cx + dx * scale, y: cy + dy * scale }
}

function edgeFromNode(node, tx, ty) {
  if (node.type === 'category') {
    const rect = node.rect || categoryRect(node.name)
    return edgeAtRect(node.x, node.y, rect.w, rect.h, tx, ty)
  }
  const cap = node.capsule || buildCapsule(node.name, {
    isRoot: node.type === 'root',
    levelNum: node.levelNum || 2,
  })
  return edgeAtRect(node.x, node.y, cap.w, cap.h, tx, ty)
}

function makeLink(fromId, toId, fromNode, toNode, type, label, extra = {}) {
  const fromPt = edgeFromNode(fromNode, toNode.x, toNode.y)
  const toPt = edgeFromNode(toNode, fromNode.x, fromNode.y)
  return {
    from: fromId,
    to: toId,
    fromX: fromPt.x,
    fromY: fromPt.y,
    toX: toPt.x,
    toY: toPt.y,
    type,
    label: label || '',
    ...extra,
  }
}

/** 以中心为锚点微调坐标（factor=1 时不拉伸） */
function spreadFromCenter(nodes, factor) {
  if (Math.abs(factor - 1) < 1e-6) return
  const cx = LAYOUT_CENTER.x
  const cy = LAYOUT_CENTER.y
  nodes.forEach(n => {
    if (n.type === 'root') return
    n.x = cx + (n.x - cx) * factor
    n.y = cy + (n.y - cy) * factor
  })
}

function rebuildLinks(nodes, links) {
  const nodeMap = Object.fromEntries(nodes.map(n => [n.id, n]))
  return links.map(link => {
    const fromNode = nodeMap[link.from]
    const toNode = nodeMap[link.to]
    if (!fromNode || !toNode) return link
    const meta = {}
    if (link.labelT != null) meta.labelT = link.labelT
    if (link.labelSide != null) meta.labelSide = link.labelSide
    if (link.labelAlong != null) meta.labelAlong = link.labelAlong
    return makeLink(link.from, link.to, fromNode, toNode, link.type, link.label, meta)
  })
}

/** 估算胶囊占用（x/y 分开，避免纵向被宽度撑开） */
function nodeOccX(n) {
  if (n.type === 'category') {
    const rect = n.rect || { w: 58, h: 24 }
    return rect.w / 2 + 4
  }
  const cap = n.capsule || { w: 44, h: 22 }
  return cap.w / 2 + 4
}

function nodeOccY(n) {
  if (n.type === 'category') {
    const rect = n.rect || { w: 58, h: 24 }
    return rect.h / 2 + 4
  }
  const cap = n.capsule || { w: 44, h: 22 }
  return cap.h / 2 + 4
}

function nodeOccupancy(n) {
  return Math.max(nodeOccX(n), nodeOccY(n))
}

function resolveColumnGaps(nodes) {
  ;['君臣', '师从'].forEach(cat => {
    const col = nodes
      .filter(n => n.type === 'person' && n.category === cat)
      .sort((a, b) => a.y - b.y)
    for (let pass = 0; pass < col.length + 1; pass++) {
      for (let i = 1; i < col.length; i++) {
        const prev = col[i - 1]
        const curr = col[i]
        const minDy = nodeOccY(prev) + nodeOccY(curr) + 6
        const gap = curr.y - prev.y
        if (gap < minDy) {
          const shift = minDy - gap
          curr.y += shift
        }
      }
    }
  })
}

function resolveOverlaps(nodes) {
  resolveColumnGaps(nodes)
  const items = nodes.filter(n => n.type === 'person' || n.type === 'root')
  for (let pass = 0; pass < 5; pass++) {
    for (let i = 0; i < items.length; i++) {
      for (let j = i + 1; j < items.length; j++) {
        const a = items[i]
        const b = items[j]
        const dx = b.x - a.x
        const dy = b.y - a.y
        const dist = Math.hypot(dx, dy)
        const minDist = nodeOccupancy(a) + nodeOccupancy(b) + 6
        if (dist >= minDist || dist < 1e-6) continue
        const push = (minDist - dist) / 2 + 0.5
        const ux = dx / dist
        const uy = dy / dist
        if (a.type !== 'root') {
          a.x -= ux * push
          a.y -= uy * push
        }
        if (b.type !== 'root') {
          b.x += ux * push
          b.y += uy * push
        }
      }
    }
  }
  resolveColumnGaps(nodes)
}

function layoutRadialTree(tree, options = {}) {
  const nodes = []
  const links = []
  const placed = new Map()

  const rootCapsule = buildCapsule(tree.name, { isRoot: true, levelNum: 0 })
  const rootNode = {
    id: tree.id,
    name: tree.name,
    x: V5_ROOT.x,
    y: V5_ROOT.y,
    type: 'root',
    depth: 0,
    levelNum: 0,
    capsule: rootCapsule,
    displayName: rootCapsule.displayName,
    fontSize: rootCapsule.fontSize,
  }
  nodes.push(rootNode)
  placed.set(tree.id, rootNode)

  const catMap = {}
  tree.children.forEach(c => { catMap[c.name] = c })

  function addCategory(cat) {
    const pos = V5_CATEGORY[cat.name]
    if (!pos) return null
    const rect = categoryRect(cat.name)
    const node = {
      id: cat.id,
      name: cat.name,
      x: pos.x,
      y: pos.y,
      type: 'category',
      depth: 1,
      rect,
    }
    nodes.push(node)
    placed.set(cat.id, node)
    links.push(makeLink(tree.id, cat.id, rootNode, node, 'category', ''))
    return node
  }

  function addPerson(treeNode, category, parentNode, label, extra = {}) {
    if (placed.has(treeNode.id)) return placed.get(treeNode.id)

    const levelNum = treeNode.levelNum || 1
    const proto = lookupProtoCoord(treeNode.name)
    const capsule = buildCapsule(treeNode.name, { levelNum })
    let x = proto ? proto.x : (parentNode.x + (extra.fallbackDx || 0))
    let y = proto ? proto.y : (parentNode.y + (extra.fallbackDy || -72))

    const nodeData = {
      id: treeNode.id,
      name: treeNode.name,
      x,
      y,
      capsule,
      fontSize: capsule.fontSize,
      displayName: capsule.displayName,
      type: 'person',
      depth: levelNum + 1,
      levelNum,
      role: treeNode.role,
      category,
    }
    nodes.push(nodeData)
    placed.set(treeNode.id, nodeData)

    if (parentNode) {
      links.push(makeLink(
        parentNode.id, treeNode.id,
        parentNode, nodeData,
        category, label || treeNode.role || '',
        extra.linkMeta || {},
      ))
    }

    return nodeData
  }

  function walkTree(treeNode, category, parentNode, label, extra = {}) {
    const nodeData = addPerson(treeNode, category, parentNode, label, extra)
    ;(treeNode.children || []).forEach(child => {
      walkTree(child, category, nodeData, child.role || '')
    })
  }

  // ─── 家庭 ───
  if (catMap['家庭']) {
    const catNode = addCategory(catMap['家庭'])
    if (catNode) {
      const roleOrder = { '母亲': 0, '父亲': 1, '妻子': 2, '儿子': 3 }
      const roots = [...catMap['家庭'].children].sort(
        (a, b) => (roleOrder[a.role] ?? 9) - (roleOrder[b.role] ?? 9),
      )
      roots.forEach(root => walkTree(root, '家庭', catNode, root.role || ''))
    }
  }

  // ─── 师从（左列）───
  if (catMap['师从']) {
    const catNode = addCategory(catMap['师从'])
    if (catNode) {
      const children = catMap['师从'].children || []
      children.forEach((child, idx) => {
        const proto = lookupProtoCoord(child.name)
        const fallbackDy = (idx - (children.length - 1) / 2) * 100
        walkTree(child, '师从', catNode, child.role || '', {
          fallbackDx: proto ? 0 : -70,
          fallbackDy: proto ? 0 : fallbackDy,
        })
      })
    }
  }

  // ─── 敌对（下扇形）───
  if (catMap['敌对']) {
    const catNode = addCategory(catMap['敌对'])
    if (catNode) {
      const children = catMap['敌对'].children || []
      const n = children.length
      children.forEach((child, idx) => {
        const proto = lookupProtoCoord(child.name)
        const xSpread = n === 1 ? 0 : 204
        const fallbackDx = n === 1 ? 0 : -xSpread / 2 + idx * (xSpread / (n - 1))
        const midOffset = n > 2 && idx === Math.floor(n / 2) ? 24 : 0
        walkTree(child, '敌对', catNode, child.role || '', {
          fallbackDx: proto ? 0 : fallbackDx,
          fallbackDy: proto ? 0 : 108 + midOffset,
        })
      })
    }
  }

  // ─── 君臣（右列）───
  if (catMap['君臣']) {
    const catNode = addCategory(catMap['君臣'])
    if (catNode) {
      const children = catMap['君臣'].children || []
      children.forEach((child, idx) => {
        const proto = lookupProtoCoord(child.name)
        const spacing = children.length <= 4 ? 52 : 48
        const fallbackDy = (idx - (children.length - 1) / 2) * spacing
        walkTree(child, '君臣', catNode, child.role || '', {
          fallbackDx: proto ? 0 : 84,
          fallbackDy: proto ? 0 : fallbackDy,
        })
      })
    }
  }

  // 舒展布局 → 重建连线 → 消重叠
  spreadFromCenter(nodes, LAYOUT_SPREAD)
  let finalLinks = rebuildLinks(nodes, links)
  resolveOverlaps(nodes)
  finalLinks = rebuildLinks(nodes, finalLinks)

  // 边界（含标签留白）
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  nodes.forEach(n => {
    const occ = nodeOccupancy(n) + 14
    minX = Math.min(minX, n.x - occ)
    minY = Math.min(minY, n.y - occ)
    maxX = Math.max(maxX, n.x + occ)
    maxY = Math.max(maxY, n.y + occ)
  })
  const bounds = { minX, minY, maxX, maxY, width: maxX - minX, height: maxY - minY }

  return { nodes, links: finalLinks, bounds }
}

module.exports = {
  buildRelationTree,
  layoutRadialTree,
  nodeMetrics,
  buildCapsule,
  edgeAtCircle,
  edgeAtRect,
  lookupProtoCoord,
}
