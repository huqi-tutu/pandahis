import { prepareRelationGraph, RING_RADIUS } from '../../utils/relation-mindmap-layout'

type GraphNode = { key: string; name?: string; type?: string; targetBoxId?: string; extraJson?: string }
type GraphEdge = { fromKey: string; toKey: string; label?: string }
type GraphPayload = { centerNodeKey?: string; nodes?: GraphNode[]; edges?: GraphEdge[] }

type EdgeDraw = {
  fromKey: string
  toKey: string
  x1: number
  y1: number
  x2: number
  y2: number
  cx: number
  cy: number
  color: string
  group: string
  label: string
  labelX: number
  labelY: number
  labelW: number
  labelH: number
}

type Pos = {
  key: string
  x: number
  y: number
  fullName: string
  displayName: string
  fontSize: number
  type: string
  depth: number
  group: string
  targetBoxId?: string
  isCategory?: boolean
  isSubCategory?: boolean
  isCenter?: boolean
  isExpandNode?: boolean
  isPerson?: boolean
  circleR: number
  boxW: number
  boxH: number
  minR: number
}

type LayoutResult = {
  positions: Pos[]
  edgeList: EdgeDraw[]
  /** 完整拓扑边（含一级分类），用于点击高亮整条关系链 */
  topologyEdges: GraphEdge[]
  bounds: { minX: number; minY: number; maxX: number; maxY: number }
  centerKey: string
  /** 各圈实际半径（扩圈后与 RING_RADIUS 基准值可能不同） */
  ringRadii: readonly number[]
}

const BG = '#F8F6F2'
const CENTER_FILL = '#4A3F3F'
const CENTER_TEXT = '#FAF8F5'
/** 绢帛色：家庭赭石 / 同僚苔绿 / 敌对绾红 / 师徒黛青 / 好友藕合 */
const GROUP_SOLID: Record<string, string> = {
  家庭: '#A2734F',
  同僚: '#7D8A6A',
  敌对: '#A46A65',
  师徒: '#63899C',
  好友: '#9A798F',
}
const GROUP_BG: Record<string, string> = {
  家庭: '#ECE4DB',
  同僚: '#E7E7DF',
  敌对: '#ECE2DE',
  师徒: '#E3E7E6',
  好友: '#EBE4E4',
}
const CATEGORY_FILL = GROUP_BG
const CATEGORY_STROKE: Record<string, string> = {
  家庭: 'rgba(162, 115, 79, 0.22)',
  同僚: 'rgba(125, 138, 106, 0.22)',
  敌对: 'rgba(164, 106, 101, 0.22)',
  师徒: 'rgba(99, 137, 156, 0.22)',
  好友: 'rgba(154, 121, 143, 0.22)',
}
const CATEGORY_TEXT = '#4A4540'
const LEAF_FILL = '#FAF8F5'
const LEAF_STROKE = 'rgba(162, 115, 79, 0.18)'
const LEAF_TEXT = '#343A40'
/**
 * 主题延伸连线（实线）：比圈层辅助线略深，
 * 但不深于旧版虚线连线（原 0.22）。
 */
const GROUP_EDGE: Record<string, string> = {
  家庭: 'rgba(162, 115, 79, 0.16)',
  同僚: 'rgba(125, 138, 106, 0.16)',
  敌对: 'rgba(164, 106, 101, 0.16)',
  师徒: 'rgba(99, 137, 156, 0.16)',
  好友: 'rgba(154, 121, 143, 0.16)',
  other: 'rgba(150, 142, 135, 0.14)',
}
/** 四圈层辅助线：极淡版(180,172,165,0.06)与深版(150,146,140,0.22)折中 */
const RING_STROKE = 'rgba(165, 159, 153, 0.14)'
/** 圈层点状虚线：[点长, 间隙] */
const RING_DASH: [number, number] = [1.2, 5.5]
const LONG_PRESS_MS = 400
const RING_DOT_DASH: [number, number] = [1.1, 3.0]
const NO_EDGE_LABEL_GROUPS = new Set(['同僚', '敌对', '师徒', '好友'])
const EDGE_LABEL_NORMALIZE: Record<string, string> = {
  父亲: '父',
  母亲: '母',
  正妻: '妻',
  正室: '妻',
  正妃: '妻',
  嫔妃: '妃',
  丈夫: '夫',
  儿子: '子',
  女儿: '女',
}
const CENTER_R = 28
const PERSON_R = 22
const NODE_GAP = 10
const CAT_FONT = 11
/** 连接线标题：嵌在线上的弱化小字牌（边框跟连线；文字用主题色） */
const REL_LABEL_H = 11
const REL_LABEL_FONT = 6
const REL_LABEL_FILL = '#FAF8F5'
const REL_LABEL_TEXT = '#4A3F3F'
const REL_LABEL_RADIUS = 3
const REL_LABEL_LINE = 0.7

function normalizeGroupName(raw: string): string {
  const g = (raw || '').trim()
  if (g === '君臣') return '同僚'
  if (g === '师从') return '师徒'
  if (g === '外敌') return '敌对'
  return g
}

function parseExtraGroup(extraJson?: string): string {
  if (!extraJson) return ''
  try {
    const o = JSON.parse(extraJson) as Record<string, unknown>
    if (o.isCategoryNode || o.isSubCategoryNode) {
      return normalizeGroupName(String(o.关系类别 || ''))
    }
    const raw = String(o.关系类别 || o.group || o.category || o.cat || '')
    const m = normalizeGroupName(raw).match(/家庭|同僚|敌对|师徒|好友/)
    return m ? m[0] : ''
  } catch {
    return ''
  }
}

function isSubCategoryNode(meta?: GraphNode): boolean {
  if (!meta) return false
  if (meta.type === 'subcategory') return true
  try {
    if (meta.extraJson) {
      const o = JSON.parse(meta.extraJson) as Record<string, unknown>
      if (o.isSubCategoryNode || o.节点类型 === '二级分类') return true
    }
  } catch {
    /* ignore */
  }
  return false
}

function isCategoryNode(meta?: GraphNode): boolean {
  if (!meta) return false
  if (isSubCategoryNode(meta)) return false
  if (meta.type === 'category') return true
  if (String(meta.key || '').startsWith('cat_')) return true
  try {
    if (meta.extraJson) {
      const o = JSON.parse(meta.extraJson) as Record<string, unknown>
      if (o.isCategoryNode) return true
    }
  } catch {
    /* ignore */
  }
  return false
}

function isExpandNode(meta?: GraphNode, name?: string): boolean {
  const n = (name || meta?.name || '').trim()
  return /展开全部|展开更多|\+(\d+)/.test(n) || meta?.type === 'expand'
}

function buildParentMap(centerKey: string, edges: GraphEdge[]): Map<string, string> {
  const parent = new Map<string, string>()
  const adj = new Map<string, string[]>()
  for (const e of edges || []) {
    if (!adj.has(e.fromKey)) adj.set(e.fromKey, [])
    adj.get(e.fromKey)!.push(e.toKey)
  }
  const q = [centerKey]
  const seen = new Set([centerKey])
  while (q.length) {
    const u = q.shift()!
    for (const v of adj.get(u) || []) {
      if (seen.has(v)) continue
      seen.add(v)
      parent.set(v, u)
      q.push(v)
    }
  }
  return parent
}

function nodeGroup(meta: GraphNode | undefined, fallback = 'other'): string {
  if (!meta) return fallback
  if (isCategoryNode(meta)) return normalizeGroupName(String(meta.name || '')) || fallback
  return parseExtraGroup(meta.extraJson) || fallback
}

function personFontSize(name: string): number {
  const len = name.length
  if (len <= 2) return 10
  if (len <= 3) return 9
  if (len <= 4) return 8
  return 7
}

function radialOf(x: number, y: number): number {
  return Math.hypot(x, y)
}

function categoryBox(name: string, compact = false): { w: number; h: number } {
  if (compact) return { w: Math.max(48, name.length * 10 + 18), h: 26 }
  return { w: Math.max(56, name.length * 12 + 24), h: 30 }
}

function truncateName(name: string, maxLen: number): string {
  if (name.length <= maxLen) return name
  return `${name.slice(0, Math.max(1, maxLen - 1))}…`
}

/** 中心史略名：在圆内自适应字号；过长则两行，保证完整可见 */
function fitCenterLabel(
  ctx: CanvasRenderingContext2D,
  text: string,
  circleR: number
): { fontSize: number; lines: string[] } {
  const maxW = circleR * 2 - 14
  const maxH = circleR * 2 - 14
  const chars = Array.from(text || '')
  if (!chars.length) return { fontSize: 12, lines: [''] }

  for (let fs = 14; fs >= 8; fs--) {
    ctx.font = `600 ${fs}px sans-serif`
    if (ctx.measureText(text).width <= maxW) return { fontSize: fs, lines: [text] }
  }

  const mid = Math.ceil(chars.length / 2)
  const lines = [chars.slice(0, mid).join(''), chars.slice(mid).join('')]
  for (let fs = 12; fs >= 7; fs--) {
    ctx.font = `600 ${fs}px sans-serif`
    const w = Math.max(...lines.map((l) => ctx.measureText(l).width))
    const h = fs * lines.length * 1.25
    if (w <= maxW && h <= maxH) return { fontSize: fs, lines }
  }
  return { fontSize: 7, lines }
}

function addPos(
  posMap: Map<string, Pos>,
  meta: GraphNode,
  x: number,
  y: number,
  depth: number,
  group: string,
  flags: { isCenter?: boolean; isCategory?: boolean; isSubCategory?: boolean; isExpand?: boolean }
) {
  const fullName = ((meta.name != null && String(meta.name).trim()) || meta.key).trim()
  const isCenter = !!flags.isCenter
  const isCategory = !!flags.isCategory
  const isSubCategory = !!flags.isSubCategory
  let circleR = 0
  let boxW = 0
  let boxH = 0
  let fontSize = personFontSize(fullName)
  let displayName = fullName

  if (isCenter) {
    circleR = CENTER_R
    boxW = CENTER_R * 2
    boxH = CENTER_R * 2
    // 初值按字数预估；绘制时再按 measureText 精调
    const len = Math.max(1, Array.from(fullName).length)
    fontSize = len <= 2 ? 14 : len <= 4 ? 12 : len <= 6 ? 10 : 9
  } else if (isCategory) {
    const box = categoryBox(fullName)
    boxW = box.w
    boxH = box.h
    fontSize = CAT_FONT
  } else if (isSubCategory) {
    const box = categoryBox(fullName, true)
    boxW = box.w
    boxH = box.h
    fontSize = Math.max(9, CAT_FONT - 1)
  } else {
    // 与布局侧 estimatePersonBox 对齐：人名胶囊按字数定宽，避免视觉比碰撞盒更大
    const len = Math.max(1, Array.from(fullName).length)
    boxW = Math.max(40, Math.min(76, len * 11 + 14))
    boxH = 28
    circleR = Math.max(boxW, boxH) / 2
    fontSize = personFontSize(fullName)
  }

  posMap.set(meta.key, {
    key: meta.key,
    x,
    y,
    fullName,
    displayName,
    fontSize,
    type: meta.type || 'person',
    depth,
    group,
    targetBoxId: meta.targetBoxId,
    isCategory,
    isSubCategory,
    isCenter,
    isExpandNode: !!flags.isExpand,
    isPerson: !isCenter && !isCategory && !isSubCategory,
    circleR,
    boxW,
    boxH,
    minR: isCenter ? 0 : Math.max(0, radialOf(x, y) - 4),
  })
}

function computeDepthMap(centerKey: string, edges: GraphEdge[]): Map<string, number> {
  const parent = buildParentMap(centerKey, edges)
  const depth = new Map<string, number>()
  depth.set(centerKey, 0)
  for (const key of parent.keys()) {
    let d = 0
    let cur: string | undefined = key
    while (cur && cur !== centerKey) {
      d++
      cur = parent.get(cur)
    }
    depth.set(key, d)
  }
  return depth
}

function posFromNode(meta: GraphNode, x: number, y: number, depth: number, centerKey: string): Pos {
  const posMap = new Map<string, Pos>()
  const name = ((meta.name != null && String(meta.name).trim()) || meta.key).trim()
  addPos(posMap, meta, x, y, depth, nodeGroup(meta), {
    isCenter: meta.key === centerKey,
    isCategory: isCategoryNode(meta),
    isSubCategory: isSubCategoryNode(meta),
    isExpand: isExpandNode(meta, name),
  })
  return posMap.get(meta.key)!
}

function layoutMindMap(nodes: GraphNode[], edges: GraphEdge[], centerKey: string): LayoutResult {
  const prepared = prepareRelationGraph(centerKey, nodes, edges)
  const layoutNodes = prepared.nodes
  const layoutEdges = prepared.edges
  const nodeMap = new Map(layoutNodes.map((n) => [n.key, n]))
  const centerMeta = nodeMap.get(centerKey)
  if (!centerMeta) {
    return {
      positions: [],
      edgeList: [],
      topologyEdges: [],
      bounds: { minX: -1, minY: -1, maxX: 1, maxY: 1 },
      centerKey,
      ringRadii: RING_RADIUS,
    }
  }

  const coordMap = prepared.positions
  const depthMap = computeDepthMap(centerKey, layoutEdges)
  const positions: Pos[] = []
  for (const n of layoutNodes) {
    const pt = coordMap.get(n.key)
    if (!pt) continue
    positions.push(posFromNode(n, pt.x, pt.y, depthMap.get(n.key) ?? 0, centerKey))
  }

  const edgeList = buildEdgeList(positions, layoutEdges, nodeMap)
  enrichEdgesWithCurves(edgeList)
  resolveEdgeLabelCollisions(edgeList, positions)
  return {
    positions,
    edgeList,
    topologyEdges: layoutEdges,
    bounds: computeBounds(positions, edgeList),
    centerKey,
    ringRadii: prepared.ringRadii,
  }
}

/** 与 drawNode 一致的人物框尺寸，供锚点贴边 */
function personBoxSize(p: Pos): { w: number; h: number } {
  return {
    w: Math.max(40, p.boxW || PERSON_R * 2),
    h: Math.max(26, Math.min(p.boxH || 28, 30)),
  }
}

function nodeBounds(p: Pos) {
  const hw = (p.isCategory ? p.boxW : p.boxW) / 2 + 6
  const hh = (p.isCategory ? p.boxH : p.boxH) / 2 + 6
  return { l: p.x - hw, r: p.x + hw, t: p.y - hh, b: p.y + hh }
}

function labelBox(x: number, y: number, w: number, h: number) {
  return { l: x - w / 2, r: x + w / 2, t: y - h / 2, b: y + h / 2 }
}

function boxesOverlap(
  a: { l: number; r: number; t: number; b: number },
  b: { l: number; r: number; t: number; b: number }
) {
  return a.l < b.r && a.r > b.l && a.t < b.b && a.b > b.t
}

function measureRelLabel(text: string): { w: number; h: number } {
  // 单字接近方盒；多字略加宽，整体保持弱化小尺寸
  const w = Math.max(REL_LABEL_H, text.length * (REL_LABEL_FONT + 1) + 6)
  return { w, h: REL_LABEL_H }
}

/** 沿连线采样的 t 值：优先中点，再向两端滑动找空位 */
const EDGE_LABEL_T_SAMPLES = [
  0.5, 0.42, 0.58, 0.35, 0.65, 0.28, 0.72, 0.22, 0.78, 0.4, 0.6, 0.32, 0.68,
]

type RectBox = { l: number; r: number; t: number; b: number }

/** 节点/枢纽的实际渲染障碍盒（含间距） */
function nodeObstacleBoxes(positions: Pos[]): RectBox[] {
  const boxes: RectBox[] = []
  for (const p of positions) {
    if (p.isCategory) continue
    const pad = p.isCenter ? 4 : 5
    if (p.isPerson || (!p.isSubCategory && !p.isCategory && !p.isCenter)) {
      const { w, h } = personBoxSize(p)
      boxes.push({
        l: p.x - w / 2 - pad,
        r: p.x + w / 2 + pad,
        t: p.y - h / 2 - pad,
        b: p.y + h / 2 + pad,
      })
    } else {
      const b = nodeBounds(p)
      boxes.push(b)
    }
  }
  return boxes
}

function boxCollidesAny(box: RectBox, obstacles: RectBox[]): boolean {
  for (const o of obstacles) {
    if (boxesOverlap(box, o)) return true
  }
  return false
}

/**
 * 方案 A：边标签沿连线滑动找无碰撞位置；仍冲突则隐藏该边标签。
 */
function resolveEdgeLabelCollisions(edgeList: EdgeDraw[], positions: Pos[]) {
  const nodeBoxes = nodeObstacleBoxes(positions)
  const placedLabels: RectBox[] = []

  for (const e of edgeList) {
    if (!e.label) {
      e.labelW = 0
      e.labelH = 0
      continue
    }
    const { w, h } = measureRelLabel(e.label)
    e.labelW = w
    e.labelH = h

    const edgeLen = Math.hypot(e.x2 - e.x1, e.y2 - e.y1)
    if (edgeLen < 28) {
      e.label = ''
      e.labelW = 0
      e.labelH = 0
      continue
    }

    let placed = false
    for (const t of EDGE_LABEL_T_SAMPLES) {
      const pt = pointOnEdge(e, t)
      const box = labelBox(pt.x, pt.y, w, h)
      if (boxCollidesAny(box, nodeBoxes) || boxCollidesAny(box, placedLabels)) continue
      e.labelX = pt.x
      e.labelY = pt.y
      placedLabels.push(box)
      placed = true
      break
    }

    if (!placed) {
      e.label = ''
      e.labelW = 0
      e.labelH = 0
    }
  }
}

function quadPoint(x1: number, y1: number, cx: number, cy: number, x2: number, y2: number, t: number) {
  const u = 1 - t
  return {
    x: u * u * x1 + 2 * u * t * cx + t * t * x2,
    y: u * u * y1 + 2 * u * t * cy + t * t * y2,
  }
}

/**
 * 径向连线：控制点落在两端半径之间，禁止向中心弯（消除倒挂）。
 * 同对多边仅做法向微错车道。
 */
function enrichEdgesWithCurves(edgeList: EdgeDraw[]) {
  const pairTotal = new Map<string, number>()
  for (const e of edgeList) {
    const k = [e.fromKey, e.toKey].sort().join('|')
    pairTotal.set(k, (pairTotal.get(k) || 0) + 1)
  }
  const pairIdx = new Map<string, number>()
  for (const e of edgeList) {
    const k = [e.fromKey, e.toKey].sort().join('|')
    const total = pairTotal.get(k) || 1
    const idx = pairIdx.get(k) || 0
    pairIdx.set(k, idx + 1)
    const lane = total === 1 ? 0 : (idx - (total - 1) / 2) * 10

    const r1 = Math.hypot(e.x1, e.y1)
    const r2 = Math.hypot(e.x2, e.y2)
    const a1 = Math.atan2(e.y1, e.x1)
    const a2 = Math.atan2(e.y2, e.x2)
    // 短边几乎直线；长边控制点取中间角、中间半径
    let midA = (a1 + a2) / 2
    // 处理 ±π 跨越
    let dA = a2 - a1
    while (dA > Math.PI) dA -= Math.PI * 2
    while (dA < -Math.PI) dA += Math.PI * 2
    midA = a1 + dA / 2
    const midR = (r1 + r2) / 2
    let cx = Math.cos(midA) * midR
    let cy = Math.sin(midA) * midR
    const dx = e.x2 - e.x1
    const dy = e.y2 - e.y1
    const len = Math.hypot(dx, dy) || 1
    cx += (-dy / len) * lane
    cy += (dx / len) * lane
    e.cx = cx
    e.cy = cy
  }
}

/** 借鉴 F6 fitView：仅缩小不放大，主题仍居中 */
function fitZoomScale(w: number, h: number, bounds: LayoutResult['bounds']): number {
  const bw = bounds.maxX - bounds.minX
  const bh = bounds.maxY - bounds.minY
  if (bw <= 0 || bh <= 0) return 1
  const pad = 36
  return Math.min(1, (w - pad * 2) / bw, (h - pad * 2) / bh)
}

function pointOnEdge(e: EdgeDraw, t: number) {
  return quadPoint(e.x1, e.y1, e.cx, e.cy, e.x2, e.y2, t)
}

function computeBounds(positions: Pos[], edgeList: EdgeDraw[]) {
  let minX = -120
  let minY = -120
  let maxX = 120
  let maxY = 120
  for (const p of positions) {
    const hw = p.boxW / 2 + 10
    const hh = p.boxH / 2 + 10
    minX = Math.min(minX, p.x - hw)
    maxX = Math.max(maxX, p.x + hw)
    minY = Math.min(minY, p.y - hh)
    maxY = Math.max(maxY, p.y + hh)
  }
  for (const e of edgeList) {
    if (!e.label) continue
    const box = labelBox(e.labelX, e.labelY, e.labelW, e.labelH)
    minX = Math.min(minX, box.l)
    maxX = Math.max(maxX, box.r)
    minY = Math.min(minY, box.t)
    maxY = Math.max(maxY, box.b)
  }
  const pad = 64
  return { minX: minX - pad, minY: minY - pad, maxX: maxX + pad, maxY: maxY + pad }
}

function edgeLabelText(e: GraphEdge, a: Pos, b: Pos): string {
  if (a.isCenter && (b.isCategory || b.isSubCategory)) return ''
  // 一级分类 → 二级枢纽：不显示边标题
  if (a.isCategory && b.isSubCategory) return ''
  // 同僚 / 敌对 / 师徒 / 好友：不显示边标题
  if (NO_EDGE_LABEL_GROUPS.has(a.group || b.group)) return ''
  let labelRaw = (e.label || '').trim()
  labelRaw = EDGE_LABEL_NORMALIZE[labelRaw] || labelRaw
  labelRaw = labelRaw.slice(0, 4)
  if (!labelRaw) return ''
  if (b.fullName.includes(`(${labelRaw})`)) return ''
  return labelRaw
}

function nodeAnchor(from: Pos, to: Pos): { x: number; y: number } {
  const dx = to.x - from.x
  const dy = to.y - from.y
  const len = Math.hypot(dx, dy) || 1
  const ux = dx / len
  const uy = dy / len

  // 中心圆：贴边（无外扩空隙）
  if (from.isCenter) {
    const r = from.circleR
    return { x: from.x + ux * r, y: from.y + uy * r }
  }

  // 二级枢纽 / 人物：圆角矩形贴边
  let hw = from.boxW / 2
  let hh = from.boxH / 2
  if (from.isPerson || (!from.isSubCategory && !from.isCategory && !from.isCenter)) {
    const box = personBoxSize(from)
    hw = box.w / 2
    hh = box.h / 2
  } else if (from.isSubCategory) {
    hw = from.boxW / 2
    hh = from.boxH / 2
  }

  const ax = Math.abs(ux)
  const ay = Math.abs(uy)
  let t = Infinity
  if (ax > 1e-6) t = Math.min(t, hw / ax)
  if (ay > 1e-6) t = Math.min(t, hh / ay)
  if (!Number.isFinite(t)) t = Math.max(hw, hh)
  return { x: from.x + ux * t, y: from.y + uy * t }
}

function buildEdgeList(positions: Pos[], edges: GraphEdge[], nodeMap: Map<string, GraphNode>): EdgeDraw[] {
  const m = new Map(positions.map((p) => [p.key, p]))
  const centerPos = positions.find((p) => p.isCenter)
  const out: EdgeDraw[] = []
  for (const e of edges || []) {
    let a = m.get(e.fromKey)
    let b = m.get(e.toKey)
    if (!a || !b) continue
    // 一级分类叠在中心：不画指向一级的边；一级→二级改画为中心→二级
    if (b.isCategory) continue
    if (a.isCategory) {
      if (!centerPos) continue
      a = centerPos
    }
    if (Math.hypot(a.x - b.x, a.y - b.y) < 2) continue
    const group =
      parseExtraGroup(nodeMap.get(e.toKey)?.extraJson) ||
      parseExtraGroup(nodeMap.get(e.fromKey)?.extraJson) ||
      a.group ||
      b.group ||
      'other'
    const start = nodeAnchor(a, b)
    const end = nodeAnchor(b, a)
    const label = edgeLabelText(e, a, b)
    const { w, h } = label ? measureRelLabel(label) : { w: 0, h: 0 }
    out.push({
      fromKey: e.fromKey,
      toKey: e.toKey,
      x1: start.x,
      y1: start.y,
      x2: end.x,
      y2: end.y,
      cx: (start.x + end.x) / 2,
      cy: (start.y + end.y) / 2,
      color: GROUP_EDGE[group] || GROUP_EDGE.other,
      group,
      label,
      labelX: (start.x + end.x) / 2,
      labelY: (start.y + end.y) / 2,
      labelW: w,
      labelH: h,
    })
  }
  return out
}

function pathEdgeKeys(
  targetKey: string,
  centerKey: string,
  parentMap: Map<string, string>,
  positions?: Map<string, Pos>
): Set<string> {
  const keys = new Set<string>()
  let cur = targetKey
  while (cur && cur !== centerKey) {
    const parent = parentMap.get(cur)
    if (!parent) break
    keys.add(`${parent}|${cur}`)
    // 一级分类不绘制：其出边在画布上改挂到中心，高亮时同时匹配视觉边
    const parentPos = positions?.get(parent)
    if (parentPos?.isCategory) {
      keys.add(`${centerKey}|${cur}`)
    }
    cur = parent
  }
  return keys
}

function pathNodeKeys(targetKey: string, centerKey: string, parentMap: Map<string, string>): Set<string> {
  const keys = new Set<string>([centerKey])
  let cur = targetKey
  const chain: string[] = []
  while (cur && cur !== centerKey) {
    chain.push(cur)
    const parent = parentMap.get(cur)
    if (!parent) break
    cur = parent
  }
  for (let i = chain.length - 1; i >= 0; i--) keys.add(chain[i])
  return keys
}

function roundRectPath(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  const rr = Math.min(r, w / 2, h / 2)
  ctx.beginPath()
  ctx.moveTo(x + rr, y)
  ctx.lineTo(x + w - rr, y)
  ctx.quadraticCurveTo(x + w, y, x + w, y + rr)
  ctx.lineTo(x + w, y + h - rr)
  ctx.quadraticCurveTo(x + w, y + h, x + w - rr, y + h)
  ctx.lineTo(x + rr, y + h)
  ctx.quadraticCurveTo(x, y + h, x, y + h - rr)
  ctx.lineTo(x, y + rr)
  ctx.quadraticCurveTo(x, y, x + rr, y)
  ctx.closePath()
}

/** 带边框小字牌：不透明底盖住连线；边框跟连线色，文字用主题色 */
function drawRelLabelChip(
  ctx: CanvasRenderingContext2D,
  text: string,
  x: number,
  y: number,
  w: number,
  h: number,
  lineColor: string,
  dimmed: boolean
) {
  if (!text || w <= 0 || h <= 0) return
  const border = lineColor || GROUP_EDGE.other
  ctx.save()
  ctx.globalAlpha = dimmed ? 0.35 : 1
  const left = x - w / 2
  const top = y - h / 2
  roundRectPath(ctx, left, top, w, h, REL_LABEL_RADIUS)
  ctx.fillStyle = REL_LABEL_FILL
  ctx.fill()
  ctx.strokeStyle = border
  ctx.lineWidth = REL_LABEL_LINE
  ctx.setLineDash([])
  ctx.stroke()
  ctx.fillStyle = REL_LABEL_TEXT
  ctx.font = `400 ${REL_LABEL_FONT}px sans-serif`
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(text, x, y + 0.3)
  ctx.restore()
}

function drawCatRect(
  ctx: CanvasRenderingContext2D,
  p: Pos,
  highlighted: boolean,
  dimmed: boolean
) {
  ctx.save()
  ctx.globalAlpha = dimmed ? 0.38 : 1
  const x = p.x - p.boxW / 2
  const y = p.y - p.boxH / 2
  roundRectPath(ctx, x, y, p.boxW, p.boxH, 8)
  ctx.fillStyle = CATEGORY_FILL[p.group] || 'rgba(248,246,242,0.95)'
  ctx.fill()
  ctx.strokeStyle = highlighted
    ? (GROUP_EDGE[p.group] || GROUP_EDGE.other).replace(/[\d.]+\)$/, '0.75)')
    : CATEGORY_STROKE[p.group] || 'rgba(162,115,79,0.28)'
  ctx.lineWidth = highlighted ? 1.5 : 1
  ctx.stroke()
  ctx.fillStyle = CATEGORY_TEXT
  ctx.font = `500 ${p.fontSize}px sans-serif`
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(p.fullName, p.x, p.y)
  ctx.restore()
}

Component({
  properties: {
    graph: {
      type: Object,
      value: null as unknown as GraphPayload,
      observer: 'onGraphObserver',
    },
    notedNames: {
      type: Array,
      value: [] as string[],
      observer: 'paintCached',
    },
  },
  data: {
    hint: '',
    scaleLabel: '100%',
    selectionBarVisible: false,
    selectionBarLeft: 0,
    selectionBarTop: 0,
    selectionBarPlacement: 'above',
    selectionBarText: '',
  },
  lifetimes: {
    attached() {
      this.scheduleDraw()
    },
    detached() {
      this.clearLongPressTimer()
    },
  },

  methods: {
    onGraphObserver() {
      this.hideSelectionBar()
      this.scheduleDraw()
    },

    clearLongPressTimer() {
      const timer = (this as any)._longPressTimer as ReturnType<typeof setTimeout> | null
      if (timer) {
        clearTimeout(timer)
        ;(this as any)._longPressTimer = null
      }
    },

    hideSelectionBar() {
      if (!this.data.selectionBarVisible && !this.data.selectionBarText) return
      this.setData({
        selectionBarVisible: false,
        selectionBarText: '',
      })
    },

    layoutToLocal(lx: number, ly: number): { x: number; y: number } {
      const rect = (this as any)._rect as WechatMiniprogram.BoundingClientRectCallbackResult | undefined
      const w = Number(rect?.width) || 0
      const h = Number(rect?.height) || 0
      const s = (this as any)._zoomScale || 1
      const panX = (this as any)._panX || 0
      const panY = (this as any)._panY || 0
      return {
        x: lx * s + w / 2 + panX,
        y: ly * s + h / 2 + panY,
      }
    },

    showSelectionBarForNode(hit: Pos) {
      const text = String(hit.fullName || hit.displayName || '').trim()
      if (!text) return
      const rect = (this as any)._rect as WechatMiniprogram.BoundingClientRectCallbackResult | undefined
      const w = Number(rect?.width) || 0
      const h = Number(rect?.height) || 0
      const s = (this as any)._zoomScale || 1
      const local = this.layoutToLocal(hit.x, hit.y)
      const boxW = Math.max(hit.boxW || hit.circleR * 2 || 40, 24) * s
      const boxH = Math.max(hit.boxH || hit.circleR * 2 || 28, 24) * s
      const sys = wx.getSystemInfoSync()
      const rpx = (sys.windowWidth || 375) / 750
      // 与 text-selection-bar（4 按钮：复制/查询/笔记/纠错）尺寸对齐
      // 宽：4×88 + 3×14 gap + 两侧 padding 14 = 422rpx
      // 高：padding 16+14 + icon 40 + gap 8 + label ~28 ≈ 106rpx
      const barW = 422 * rpx
      const barH = 106 * rpx
      const gap = 14 * rpx
      const edge = 12
      let centerX = local.x
      centerX = Math.max(edge + barW / 2, Math.min(w - edge - barW / 2, centerX))
      const spaceAbove = local.y - boxH / 2
      const spaceBelow = h - (local.y + boxH / 2)
      const placement = spaceAbove >= barH + gap || spaceAbove >= spaceBelow ? 'above' : 'below'
      const left = centerX - barW / 2
      const top =
        placement === 'above'
          ? Math.max(edge, local.y - boxH / 2 - gap - barH)
          : Math.min(h - edge - barH, local.y + boxH / 2 + gap)
      ;(this as any)._selectedKey = hit.key
      ;(this as any)._longPressFired = true
      this.paintCached()
      try {
        wx.vibrateShort({ type: 'light' })
      } catch {
        // ignore
      }
      this.setData({
        selectionBarVisible: true,
        selectionBarText: text,
        selectionBarLeft: left,
        selectionBarTop: top,
        selectionBarPlacement: placement,
      })
      this.triggerEvent('nodeLongPress', { key: hit.key, text })
    },

    onSelectionCopy() {
      const text = this.data.selectionBarText
      this.hideSelectionBar()
      if (!text) return
      this.triggerEvent('selectionCopy', { text })
    },
    onSelectionQuery() {
      const text = this.data.selectionBarText
      this.hideSelectionBar()
      if (!text) return
      this.triggerEvent('selectionQuery', { text })
    },
    onSelectionNote() {
      const text = this.data.selectionBarText
      this.hideSelectionBar()
      if (!text) return
      this.triggerEvent('selectionNote', { text })
    },
    onSelectionCorrection() {
      const text = this.data.selectionBarText
      this.hideSelectionBar()
      if (!text) return
      this.triggerEvent('selectionCorrection', { text })
    },
    focusNodeByName(name: string) {
      const target = String(name || '').trim()
      if (!target) return false
      const layout = (this as any)._layout as LayoutResult | null
      const hit = (layout?.positions || []).find(
        (p) => p.fullName === target || p.displayName === target
      )
      if (!hit) return false
      ;(this as any)._selectedKey = hit.key
      this.paintCached()
      return true
    },
    noop() {},

    scheduleDraw() {
      wx.nextTick(() => setTimeout(() => this.draw(), 48))
    },

    redraw() {
      this.draw()
    },

    formatScaleLabel(scale: number) {
      const pct = Math.round(scale * 100)
      return `${Math.max(25, Math.min(300, pct))}%`
    },

    syncScaleLabel() {
      const scale = (this as any)._zoomScale || 1
      const label = this.formatScaleLabel(scale)
      if (label !== this.data.scaleLabel) this.setData({ scaleLabel: label })
      this.triggerEvent('zoomChange', { scale })
    },

    zoomIn() {
      const cur = (this as any)._zoomScale || 1
      ;(this as any)._zoomScale = Math.min(3, +(cur * 1.18).toFixed(4))
      this.syncScaleLabel()
      this.paintCached()
    },

    zoomOut() {
      const cur = (this as any)._zoomScale || 1
      ;(this as any)._zoomScale = Math.max(0.25, +(cur / 1.18).toFixed(4))
      this.syncScaleLabel()
      this.paintCached()
    },

    resetZoom() {
      ;(this as any)._zoomScale = 1
      ;(this as any)._selectedKey = ''
      this.centerView()
      this.syncScaleLabel()
      this.paintCached()
    },

    centerView() {
      // 布局原点即主题人物 (0,0)，视口 translate(w/2,h/2) 后 pan 归零即正中
      ;(this as any)._panX = 0
      ;(this as any)._panY = 0
    },

    getZoomScale() {
      return (this as any)._zoomScale || 1
    },

    paintCached() {
      const layout = (this as any)._layout as LayoutResult | undefined
      const w = (this as any)._w as number
      const h = (this as any)._h as number
      const dpr = (this as any)._dpr || 1
      let ctx = (this as any)._ctx as CanvasRenderingContext2D | undefined
      const canvas = (this as any)._canvas as WechatMiniprogram.Canvas | undefined
      if (!layout || !w || !h) return
      if (!ctx && canvas) {
        ctx = canvas.getContext('2d') as unknown as CanvasRenderingContext2D
        ;(this as any)._ctx = ctx
      }
      if (!ctx) return
      ctx.setTransform(1, 0, 0, 1, 0, 0)
      ctx.scale(dpr, dpr)
      this.paint(ctx, w, h, layout)
    },

    draw() {
      const graph = this.properties.graph as GraphPayload
      const nodes = graph?.nodes || []
      const edges = graph?.edges || []
      if (!nodes.length) {
        this.setData({ hint: '暂无关系数据' })
        return
      }
      this.setData({ hint: '' })

      const query = wx.createSelectorQuery().in(this)
      query
        .select('#relGraphCanvas')
        .fields({ node: true, size: true })
        .exec((res) => {
          const info = res && res[0]
          if (!info || !info.node) return
          const canvas = info.node as WechatMiniprogram.Canvas
          const w = info.width as number
          const h = info.height as number
          if (!w || !h) return

          const dpr = wx.getWindowInfo().pixelRatio || 1
          ;(this as any)._w = w
          ;(this as any)._h = h
          ;(this as any)._dpr = dpr
          canvas.width = w * dpr
          canvas.height = h * dpr

          const ctx = canvas.getContext('2d') as unknown as CanvasRenderingContext2D
          ;(this as any)._ctx = ctx
          ;(this as any)._canvas = canvas
          ctx.setTransform(1, 0, 0, 1, 0, 0)
          ctx.scale(dpr, dpr)

          const centerKey = graph.centerNodeKey || nodes[0]?.key || ''
          ;(this as any)._selectedKey = ''
          const layout = layoutMindMap(nodes, edges, centerKey)
          ;(this as any)._layout = layout
          // 必须用完整拓扑边（含一级分类），否则点击无法点亮整条关系链
          ;(this as any)._parentMap = buildParentMap(centerKey, layout.topologyEdges)
          ;(this as any)._zoomScale = fitZoomScale(w, h, layout.bounds)
          this.centerView()
          this.syncScaleLabel()
          this.paint(ctx, w, h, layout)

          wx.createSelectorQuery()
            .in(this)
            .select('#relGraphCanvas')
            .boundingClientRect((r) => {
              ;(this as any)._rect = r
            })
            .exec()
        })
    },

    paint(ctx: CanvasRenderingContext2D, w: number, h: number, layout: LayoutResult) {
      const s = (this as any)._zoomScale || 1
      const panX = (this as any)._panX || 0
      const panY = (this as any)._panY || 0
      const selectedKey = ((this as any)._selectedKey as string) || ''
      const parentMap = ((this as any)._parentMap as Map<string, string>) || new Map()
      const posByKey = new Map(layout.positions.map((p) => [p.key, p]))
      const highlightEdges = selectedKey
        ? pathEdgeKeys(selectedKey, layout.centerKey, parentMap, posByKey)
        : new Set<string>()
      const highlightNodes = selectedKey
        ? pathNodeKeys(selectedKey, layout.centerKey, parentMap)
        : new Set<string>()

      ctx.save()
      ctx.clearRect(0, 0, w, h)
      ctx.fillStyle = BG
      ctx.fillRect(0, 0, w, h)
      ctx.translate(w / 2 + panX, h / 2 + panY)
      ctx.scale(s, s)

      // 四圈层：更淡的点状虚线环（半径与布局一致，人物中心落在圆上）
      const ringRadii = layout.ringRadii?.length ? layout.ringRadii : RING_RADIUS
      for (let i = 1; i < ringRadii.length; i++) {
        ctx.beginPath()
        ctx.arc(0, 0, ringRadii[i], 0, Math.PI * 2)
        ctx.strokeStyle = RING_STROKE
        ctx.lineWidth = 1
        ctx.setLineDash(RING_DOT_DASH)
        ctx.lineCap = 'round'
        ctx.stroke()
        ctx.setLineDash([])
      }

      // 史略主题延伸连线：实线，略深于圈层、浅于旧版连线
      for (const e of layout.edgeList) {
        const id = `${e.fromKey}|${e.toKey}`
        const visualId = `${layout.centerKey}|${e.toKey}`
        const active =
          !selectedKey || highlightEdges.has(id) || highlightEdges.has(visualId)
        const highlighted = highlightEdges.has(id) || highlightEdges.has(visualId)
        ctx.beginPath()
        ctx.moveTo(e.x1, e.y1)
        ctx.quadraticCurveTo(e.cx, e.cy, e.x2, e.y2)
        ctx.strokeStyle = active ? e.color : 'rgba(180, 172, 165, 0.05)'
        ctx.globalAlpha = highlighted ? 0.95 : active ? 0.85 : 1
        ctx.lineWidth = highlighted ? 1.2 : 1
        ctx.setLineDash([])
        ctx.lineCap = 'round'
        ctx.stroke()
        ctx.globalAlpha = 1
      }

      for (const p of layout.positions) {
        this.drawNode(ctx, p, highlightNodes.has(p.key), !!selectedKey)
      }

      for (const e of layout.edgeList) {
        const id = `${e.fromKey}|${e.toKey}`
        const active = !selectedKey || highlightEdges.has(id)
        if (!e.label || !active) continue
        drawRelLabelChip(
          ctx,
          e.label,
          e.labelX,
          e.labelY,
          e.labelW,
          e.labelH,
          e.color,
          !!selectedKey && !highlightEdges.has(id)
        )
      }
      ctx.restore()
    },

    drawNode(ctx: CanvasRenderingContext2D, p: Pos, highlighted: boolean, hasSelection: boolean) {
      const dimmed = hasSelection && !highlighted
      ctx.save()
      ctx.globalAlpha = dimmed ? 0.38 : 1

      // 一级分类不绘制（仅后端分组）
      if (p.isCategory) {
        ctx.restore()
        return
      }

      if (p.isCenter) {
        ctx.beginPath()
        ctx.arc(p.x, p.y, p.circleR, 0, Math.PI * 2)
        ctx.fillStyle = CENTER_FILL
        ctx.fill()
        // 主题圆无描边；字号/行数自适应，保证史略名完整可见
        const { fontSize, lines } = fitCenterLabel(ctx, p.fullName, p.circleR)
        ctx.fillStyle = CENTER_TEXT
        ctx.font = `600 ${fontSize}px sans-serif`
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        if (lines.length === 1) {
          ctx.fillText(lines[0], p.x, p.y)
        } else {
          const lh = fontSize * 1.25
          const y0 = p.y - ((lines.length - 1) * lh) / 2
          lines.forEach((line, i) => ctx.fillText(line, p.x, y0 + i * lh))
        }
        ctx.restore()
        return
      }

      if (p.isSubCategory) {
        // 二级枢纽：主题色实底 + 浅字
        const solid = GROUP_SOLID[p.group] || '#6C757D'
        roundRectPath(ctx, p.x - p.boxW / 2, p.y - p.boxH / 2, p.boxW, p.boxH, 8)
        ctx.fillStyle = solid
        ctx.fill()
        ctx.strokeStyle = highlighted ? solid : CATEGORY_STROKE[p.group] || 'rgba(108,117,125,0.3)'
        ctx.lineWidth = highlighted ? 1.5 : 1
        ctx.stroke()
        ctx.fillStyle = '#FAF8F5'
        ctx.font = `500 ${p.fontSize}px sans-serif`
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        ctx.fillText(p.fullName, p.x, p.y)
        ctx.restore()
        return
      }

      // 人物节点：浅主题底圆角矩形（与二级枢纽同形）
      const { w: pw, h: ph } = personBoxSize(p)
      roundRectPath(ctx, p.x - pw / 2, p.y - ph / 2, pw, ph, 8)
      ctx.fillStyle = GROUP_BG[p.group] || LEAF_FILL
      ctx.fill()
      ctx.strokeStyle = highlighted
        ? (GROUP_EDGE[p.group] || GROUP_EDGE.other).replace(/[\d.]+\)$/, '0.85)')
        : CATEGORY_STROKE[p.group] || LEAF_STROKE
      ctx.lineWidth = highlighted ? 1.5 : 1
      ctx.stroke()
      ctx.fillStyle = LEAF_TEXT
      const text = p.fullName
      let fs = p.fontSize
      for (; fs >= 6; fs--) {
        ctx.font = `400 ${fs}px sans-serif`
        if (ctx.measureText(text).width <= pw - 10) break
      }
      let show = text
      if (fs === 6 && ctx.measureText(show).width > pw - 10) {
        show = truncateName(text, 4)
      }
      ctx.font = `400 ${fs}px sans-serif`
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText(show, p.x, p.y)
      const noted = ((this.properties.notedNames as string[]) || []).some(
        (n) => n === p.fullName || n === p.displayName
      )
      if (noted) {
        ctx.strokeStyle = '#B99D5B'
        ctx.lineWidth = 2
        ctx.beginPath()
        ctx.moveTo(p.x - pw / 2 + 6, p.y + ph / 2 - 4)
        ctx.lineTo(p.x + pw / 2 - 6, p.y + ph / 2 - 4)
        ctx.stroke()
      }
      ctx.restore()
    },

    onZoomInTap() {
      this.zoomIn()
    },

    onZoomOutTap() {
      this.zoomOut()
    },

    touchDistance(touches: WechatMiniprogram.TouchDetail[]) {
      if (touches.length < 2) return 0
      return Math.hypot(touches[1].clientX - touches[0].clientX, touches[1].clientY - touches[0].clientY)
    },

    screenToLayout(x: number, y: number) {
      const w = (this as any)._w as number
      const h = (this as any)._h as number
      const s = (this as any)._zoomScale || 1
      const panX = (this as any)._panX || 0
      const panY = (this as any)._panY || 0
      return { x: (x - w / 2 - panX) / s, y: (y - h / 2 - panY) / s }
    },

    hitTestNode(layout: LayoutResult, lx: number, ly: number): Pos | null {
      const ordered = [...layout.positions].sort((a, b) => {
        const pa = (a.isCenter ? 3 : 0) + (a.isCategory ? 2 : 0) + (a.isSubCategory ? 1 : 0)
        const pb = (b.isCenter ? 3 : 0) + (b.isCategory ? 2 : 0) + (b.isSubCategory ? 1 : 0)
        return pa - pb
      })
      for (let i = ordered.length - 1; i >= 0; i--) {
        const p = ordered[i]
        if (p.isCategory || p.isSubCategory || p.isCenter) {
          if (
            lx >= p.x - p.boxW / 2 - 4 &&
            lx <= p.x + p.boxW / 2 + 4 &&
            ly >= p.y - p.boxH / 2 - 4 &&
            ly <= p.y + p.boxH / 2 + 4
          ) {
            return p
          }
          continue
        }
        if (Math.hypot(lx - p.x, ly - p.y) <= p.circleR + 6) return p
      }
      return null
    },

    /** 双指缩放结束后，用剩余手指当前位置重锚定，避免沿用旧起点造成跳动 */
    reanchorPanFromTouch(touch: WechatMiniprogram.TouchDetail) {
      ;(this as any)._touchStartX = touch.clientX
      ;(this as any)._touchStartY = touch.clientY
      ;(this as any)._panStartX = (this as any)._panX || 0
      ;(this as any)._panStartY = (this as any)._panY || 0
    },

    onTouchStart(e: WechatMiniprogram.TouchEvent) {
      const layout = (this as any)._layout as LayoutResult | null
      if (!layout?.positions.length) return
      this.clearLongPressTimer()
      ;(this as any)._pinchJustEnded = false
      ;(this as any)._longPressFired = false
      const touches = e.touches
      if (touches.length >= 2) {
        ;(this as any)._touchMode = 'pinch'
        ;(this as any)._pinchStartDist = this.touchDistance(touches)
        ;(this as any)._pinchStartScale = (this as any)._zoomScale || 1
        return
      }
      const touch = touches[0]
      ;(this as any)._touchMode = 'pending'
      this.reanchorPanFromTouch(touch)

      const rect = (this as any)._rect as WechatMiniprogram.BoundingClientRectCallbackResult | undefined
      if (!rect || !touch) return
      const pt = this.screenToLayout(touch.clientX - rect.left, touch.clientY - rect.top)
      const hit = this.hitTestNode(layout, pt.x, pt.y)
      if (!hit) return
      ;(this as any)._longPressTimer = setTimeout(() => {
        ;(this as any)._longPressTimer = null
        if ((this as any)._touchMode !== 'pending') return
        this.showSelectionBarForNode(hit)
      }, LONG_PRESS_MS)
    },

    onTouchMove(e: WechatMiniprogram.TouchEvent) {
      const touches = e.touches
      if ((this as any)._touchMode === 'pinch' && touches.length >= 2) {
        this.clearLongPressTimer()
        this.hideSelectionBar()
        const startDist = (this as any)._pinchStartDist as number
        const curDist = this.touchDistance(touches)
        if (startDist > 0 && curDist > 0) {
          ;(this as any)._zoomScale = Math.max(
            0.25,
            Math.min(3, ((this as any)._pinchStartScale || 1) * (curDist / startDist))
          )
          this.syncScaleLabel()
          this.paintCached()
        }
        return
      }
      // 缩放过程中手指数偶发变成 1：立刻重锚定，禁止用缩放前旧坐标去平移
      if ((this as any)._touchMode === 'pinch' && touches.length === 1) {
        this.clearLongPressTimer()
        ;(this as any)._pinchJustEnded = true
        ;(this as any)._touchMode = 'pending'
        this.reanchorPanFromTouch(touches[0])
        this.syncScaleLabel()
        return
      }
      const touch = touches[0]
      if (!touch) return
      const dx = touch.clientX - ((this as any)._touchStartX || 0)
      const dy = touch.clientY - ((this as any)._touchStartY || 0)
      if ((this as any)._touchMode === 'pending' && Math.hypot(dx, dy) > 8) {
        this.clearLongPressTimer()
        this.hideSelectionBar()
        ;(this as any)._touchMode = 'pan'
      }
      if ((this as any)._touchMode !== 'pan') return
      ;(this as any)._panX = ((this as any)._panStartX || 0) + dx
      ;(this as any)._panY = ((this as any)._panStartY || 0) + dy
      this.paintCached()
    },

    onTouchEnd(e: WechatMiniprogram.TouchEvent) {
      this.clearLongPressTimer()
      if ((this as any)._touchMode === 'pinch') {
        if (e.touches.length >= 2) return
        ;(this as any)._pinchJustEnded = true
        if (e.touches.length === 1) {
          // 仍留一指：以当前指位重锚定，松手/续拖都不会突然跳
          ;(this as any)._touchMode = 'pending'
          this.reanchorPanFromTouch(e.touches[0])
        } else {
          ;(this as any)._touchMode = ''
        }
        this.syncScaleLabel()
        return
      }
      if ((this as any)._touchMode === 'pan') {
        ;(this as any)._touchMode = ''
        return
      }
      // 双指缩放刚结束：吞掉松手点击，避免误选节点，也不产生位移
      if ((this as any)._pinchJustEnded) {
        ;(this as any)._pinchJustEnded = false
        ;(this as any)._touchMode = ''
        return
      }
      // 长按已弹出选字浮层：吞掉短按
      if ((this as any)._longPressFired) {
        ;(this as any)._longPressFired = false
        ;(this as any)._touchMode = ''
        return
      }
      const layout = (this as any)._layout as LayoutResult | null
      const rect = (this as any)._rect as WechatMiniprogram.BoundingClientRectCallbackResult | undefined
      const touch = e.changedTouches?.[0]
      if (!layout || !rect || !touch) return
      const pt = this.screenToLayout(touch.clientX - rect.left, touch.clientY - rect.top)
      const hit = this.hitTestNode(layout, pt.x, pt.y)
      if (!hit || hit.isCategory || hit.isSubCategory) {
        if ((this as any)._selectedKey) {
          ;(this as any)._selectedKey = ''
          this.paintCached()
        }
        this.hideSelectionBar()
        this.triggerEvent('nodeTap', { key: '', cancelled: true })
        return
      }
      this.hideSelectionBar()
      ;(this as any)._selectedKey = hit.key
      this.paintCached()
      this.triggerEvent('nodeTap', { key: hit.key, targetBoxId: hit.targetBoxId, nodeType: hit.type })
    },
  },
})
