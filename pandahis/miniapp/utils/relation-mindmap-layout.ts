/**
 * 关系图谱自适应紧凑布局：几何最小间距 + 碰撞外推 + 二分压缩（零重叠前提下尽量缩短连线）。
 */
import type { GraphEdge, GraphNode } from './graph-types'

export type LayoutPoint = { x: number; y: number }

export type LayoutViewport = {
  width?: number
  height?: number
}

/** 与 relation-graph-canvas 绘制半径一致 */
export const LAYOUT_NODE_R = {
  center: 28,
  category: 24,
  person: 22,
} as const

type Pos = LayoutPoint & {
  key: string
  depth: number
  isCenter?: boolean
  isCategory?: boolean
  circleR: number
  boxW: number
  boxH: number
  minR: number
}

const NODE_GAP = 10
const NODE_D = LAYOUT_NODE_R.person * 2 + NODE_GAP
const MIN_FAN = 0.16
const CATEGORY_ORDER = ['家庭', '师从', '同僚', '外敌']
const SECTOR_ANGLE: Record<string, number> = {
  家庭: -Math.PI / 2,
  师从: Math.PI,
  同僚: 0,
  外敌: Math.PI / 2,
}
const WEDGE: Record<string, number> = {
  家庭: Math.PI * 0.9,
  师从: Math.PI * 0.62,
  同僚: Math.PI * 0.62,
  外敌: Math.PI * 0.62,
}

type LayoutMetrics = {
  nodeCount: number
  maxSiblings: number
  categoryCount: number
}

function normalizeGroupName(raw: string): string {
  const g = (raw || '').trim()
  if (g === '君臣') return '同僚'
  if (g === '敌对') return '外敌'
  return g
}

function parseExtraGroup(extraJson?: string): string {
  if (!extraJson) return ''
  try {
    const o = JSON.parse(extraJson) as Record<string, unknown>
    if (o.isCategoryNode) return normalizeGroupName(String(o.关系类别 || ''))
    const raw = String(o.关系类别 || o.group || o.category || o.cat || '')
    const m = normalizeGroupName(raw).match(/家庭|同僚|师从|外敌/)
    return m ? m[0] : ''
  } catch {
    return ''
  }
}

function isCategoryNode(meta?: GraphNode): boolean {
  if (!meta) return false
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

function childrenOf(parentKey: string, edges: GraphEdge[]): string[] {
  return (edges || [])
    .filter((e) => e.fromKey === parentKey)
    .map((e) => e.toKey)
    .sort()
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

function buildChildrenMap(edges: GraphEdge[]): Map<string, string[]> {
  const m = new Map<string, string[]>()
  for (const e of edges || []) {
    if (!m.has(e.fromKey)) m.set(e.fromKey, [])
    m.get(e.fromKey)!.push(e.toKey)
  }
  for (const [k, list] of m) m.set(k, [...list].sort())
  return m
}

function analyzeLayoutMetrics(
  centerKey: string,
  nodes: GraphNode[],
  edges: GraphEdge[]
): LayoutMetrics {
  let maxSiblings = 1
  const seenParents = new Set<string>()
  for (const e of edges || []) {
    if (seenParents.has(e.fromKey)) continue
    seenParents.add(e.fromKey)
    const count = childrenOf(e.fromKey, edges).filter((k) => {
      const m = nodes.find((n) => n.key === k)
      return m && !isCategoryNode(m)
    }).length
    if (count > maxSiblings) maxSiblings = count
  }
  const categoryCount = nodes.filter((n) => isCategoryNode(n)).length
  return {
    nodeCount: nodes.length,
    maxSiblings,
    categoryCount: Math.max(1, categoryCount),
  }
}

function polar(cx: number, cy: number, angle: number, dist: number): LayoutPoint {
  return { x: cx + Math.cos(angle) * dist, y: cy + Math.sin(angle) * dist }
}

function radialOf(x: number, y: number): number {
  return Math.hypot(x, y)
}

function categoryBox(name: string): { w: number; h: number } {
  return { w: Math.max(56, name.length * 11 + 22), h: 30 }
}

function categoryRadius(name: string): number {
  const box = categoryBox(name)
  return Math.max(box.w, box.h) / 2
}

function collisionRadius(p: Pos): number {
  if (p.isCenter || p.isCategory) return Math.max(p.boxW, p.boxH) / 2 + NODE_GAP * 0.45
  return p.circleR + NODE_GAP * 0.45
}

function nodesOverlap(a: Pos, b: Pos): boolean {
  if (a.key === b.key) return false
  const dx = b.x - a.x
  const dy = b.y - a.y
  const minDist = collisionRadius(a) + collisionRadius(b)
  return dx * dx + dy * dy < minDist * minDist
}

function findFirstOverlap(positions: Pos[]): [Pos, Pos] | null {
  for (let i = 0; i < positions.length; i++) {
    for (let j = i + 1; j < positions.length; j++) {
      if (nodesOverlap(positions[i], positions[j])) return [positions[i], positions[j]]
    }
  }
  return null
}

function hasAnyOverlap(positions: Pos[]): boolean {
  return findFirstOverlap(positions) != null
}

/** 同一扇区内 n 个兄弟不重叠所需的最小弦长 */
function minChordForSector(sectorRad: number, slotCount: number): number {
  if (slotCount <= 1) return NODE_D * 1.04
  const half = sectorRad / slotCount / 2
  return NODE_D / (2 * Math.sin(Math.max(half, 0.04)))
}

/** 两节点 hub 之间的最小连线：边缘相切 + 扇区弦长约束 */
function hubLinkLength(
  fromR: number,
  toR: number,
  sectorRad: number,
  slotCount: number
): number {
  const edgeClear = fromR + toR + NODE_GAP * 0.65
  const chord = minChordForSector(sectorRad, slotCount)
  return Math.max(edgeClear, chord)
}

function moveSubtree(
  rootKey: string,
  dx: number,
  dy: number,
  childrenMap: Map<string, string[]>,
  posByKey: Map<string, Pos>
) {
  const stack = [rootKey]
  const seen = new Set<string>()
  while (stack.length) {
    const k = stack.pop()!
    if (seen.has(k)) continue
    seen.add(k)
    const p = posByKey.get(k)
    if (!p) continue
    p.x += dx
    p.y += dy
    if (!p.isCenter) p.minR = Math.max(p.minR, radialOf(p.x, p.y) - 4)
    for (const c of childrenMap.get(k) || []) stack.push(c)
  }
}

function pushSubtreeOutward(
  nodeKey: string,
  delta: number,
  parentMap: Map<string, string>,
  posByKey: Map<string, Pos>,
  childrenMap: Map<string, string[]>
) {
  const parentKey = parentMap.get(nodeKey)
  if (!parentKey) return
  const parent = posByKey.get(parentKey)
  const node = posByKey.get(nodeKey)
  if (!parent || !node) return
  const angle = Math.atan2(node.y - parent.y, node.x - parent.x)
  moveSubtree(nodeKey, Math.cos(angle) * delta, Math.sin(angle) * delta, childrenMap, posByKey)
}

function resolveOverlaps(
  positions: Pos[],
  parentMap: Map<string, string>,
  childrenMap: Map<string, string[]>,
  maxPass = 240
) {
  const posByKey = new Map(positions.map((p) => [p.key, p]))
  for (let pass = 0; pass < maxPass; pass++) {
    const pair = findFirstOverlap(positions)
    if (!pair) return
    const [a, b] = pair
    const delta = pass < 80 ? 4 : 6
    if (a.depth === b.depth) {
      pushSubtreeOutward(a.key, delta, parentMap, posByKey, childrenMap)
      pushSubtreeOutward(b.key, delta, parentMap, posByKey, childrenMap)
    } else {
      const mover = a.depth > b.depth ? a : b
      pushSubtreeOutward(mover.key, delta + 1, parentMap, posByKey, childrenMap)
    }
  }
}

/**
 * 在不重叠前提下，二分求最小压缩比（缩短连线、缩小画布跨度）。
 */
function compactToMinimumScale(positions: Pos[], centerKey: string): number {
  if (positions.length <= 1) return 1
  const snapshot = positions.map((p) => ({ x: p.x, y: p.y }))

  const applyScale = (scale: number) => {
    positions.forEach((p, i) => {
      if (p.key === centerKey || p.isCenter) {
        p.x = 0
        p.y = 0
        return
      }
      p.x = snapshot[i].x * scale
      p.y = snapshot[i].y * scale
    })
  }

  if (!hasAnyOverlap(positions)) {
    let lo = 0.22
    let hi = 1
    applyScale(hi)
    if (hasAnyOverlap(positions)) return 1

    for (let i = 0; i < 18; i++) {
      const mid = (lo + hi) / 2
      applyScale(mid)
      if (hasAnyOverlap(positions)) lo = mid
      else hi = mid
    }
    applyScale(hi)
    return hi
  }

  return 1
}

function subtreeWeight(
  key: string,
  edges: GraphEdge[],
  nodeMap: Map<string, GraphNode>,
  cache = new Map<string, number>()
): number {
  if (cache.has(key)) return cache.get(key)!
  const kids = childrenOf(key, edges).filter((k) => {
    const m = nodeMap.get(k)
    return m && !isCategoryNode(m)
  })
  if (!kids.length) {
    cache.set(key, 1)
    return 1
  }
  const w = kids.reduce((sum, k) => sum + subtreeWeight(k, edges, nodeMap, cache), 0)
  cache.set(key, Math.max(w, 1))
  return cache.get(key)!
}

function addPos(
  posMap: Map<string, Pos>,
  meta: GraphNode,
  x: number,
  y: number,
  depth: number,
  flags: { isCenter?: boolean; isCategory?: boolean }
) {
  const fullName = ((meta.name != null && String(meta.name).trim()) || meta.key).trim()
  const isCenter = !!flags.isCenter
  const isCategory = !!flags.isCategory
  let circleR: number = LAYOUT_NODE_R.person
  let boxW = LAYOUT_NODE_R.person * 2
  let boxH = LAYOUT_NODE_R.person * 2

  if (isCenter) {
    circleR = LAYOUT_NODE_R.center
    boxW = LAYOUT_NODE_R.center * 2
    boxH = LAYOUT_NODE_R.center * 2
  } else if (isCategory) {
    const box = categoryBox(fullName)
    boxW = box.w
    boxH = box.h
    circleR = categoryRadius(fullName)
  }

  posMap.set(meta.key, {
    key: meta.key,
    x,
    y,
    depth,
    isCenter,
    isCategory,
    circleR,
    boxW,
    boxH,
    minR: isCenter ? 0 : Math.max(0, radialOf(x, y) - 4),
  })
}

function placeSubtree(
  key: string,
  hubX: number,
  hubY: number,
  angleStart: number,
  angleEnd: number,
  linkLen: number,
  depth: number,
  edges: GraphEdge[],
  nodeMap: Map<string, GraphNode>,
  posMap: Map<string, Pos>
) {
  const meta = nodeMap.get(key)
  if (!meta) return
  const midAngle = (angleStart + angleEnd) / 2
  const pos = polar(hubX, hubY, midAngle, linkLen)
  addPos(posMap, meta, pos.x, pos.y, depth, {})

  const kids = childrenOf(key, edges).filter((k) => {
    const m = nodeMap.get(k)
    return m && !isCategoryNode(m)
  })
  if (!kids.length) return

  const sector = Math.max(angleEnd - angleStart, MIN_FAN)
  const weights = kids.map((k) => subtreeWeight(k, edges, nodeMap))
  const total = weights.reduce((a, b) => a + b, 0) || kids.length
  const nextLink = hubLinkLength(LAYOUT_NODE_R.person, LAYOUT_NODE_R.person, sector, kids.length)

  let cursor = angleStart
  kids.forEach((kid, i) => {
    const slice = (weights[i] / total) * sector
    const a0 = cursor
    const a1 = cursor + slice
    cursor += slice
    placeSubtree(kid, pos.x, pos.y, a0, a1, nextLink, depth + 1, edges, nodeMap, posMap)
  })
}

function layoutCluster(
  catMeta: GraphNode,
  edges: GraphEdge[],
  nodeMap: Map<string, GraphNode>,
  posMap: Map<string, Pos>,
  metrics: LayoutMetrics
) {
  const g = normalizeGroupName(String(catMeta.name || ''))
  const base = SECTOR_ANGLE[g] ?? -Math.PI / 2
  const wedge = WEDGE[g] ?? Math.PI * 0.5
  const catName = String(catMeta.name || '')
  const catR = categoryRadius(catName)
  const linkToCat = hubLinkLength(
    LAYOUT_NODE_R.center,
    catR,
    (Math.PI * 2) / metrics.categoryCount,
    1
  )
  const catPos = polar(0, 0, base, linkToCat)
  addPos(posMap, catMeta, catPos.x, catPos.y, 1, { isCategory: true })

  const topKids = childrenOf(catMeta.key, edges).filter((k) => {
    const m = nodeMap.get(k)
    return m && !isCategoryNode(m)
  })
  if (!topKids.length) return

  const weights = topKids.map((k) => subtreeWeight(k, edges, nodeMap))
  const total = weights.reduce((a, b) => a + b, 0) || topKids.length
  const start = base - wedge / 2
  let cursor = start
  topKids.forEach((kid, i) => {
    const slice = (weights[i] / total) * wedge
    const a0 = cursor
    const a1 = cursor + slice
    cursor += slice
    const link = hubLinkLength(catR, LAYOUT_NODE_R.person, slice, Math.max(1, topKids.length))
    placeSubtree(kid, catPos.x, catPos.y, a0, a1, link, 2, edges, nodeMap, posMap)
  })
}

function buildPosList(
  centerKey: string,
  nodes: GraphNode[],
  edges: GraphEdge[]
): Pos[] {
  const nodeMap = new Map(nodes.map((n) => [n.key, n]))
  const metrics = analyzeLayoutMetrics(centerKey, nodes, edges)
  const posMap = new Map<string, Pos>()
  const centerMeta = nodeMap.get(centerKey)
  if (!centerMeta) return []

  addPos(posMap, centerMeta, 0, 0, 0, { isCenter: true })

  const categoryNodes = CATEGORY_ORDER.map((g) =>
    nodes.find((n) => isCategoryNode(n) && normalizeGroupName(String(n.name || '')) === g)
  ).filter((n): n is GraphNode => n != null)

  for (const cat of categoryNodes) {
    layoutCluster(cat, edges, nodeMap, posMap, metrics)
  }

  const orphanDist = hubLinkLength(LAYOUT_NODE_R.center, LAYOUT_NODE_R.person, Math.PI / 4, 1)
  for (const n of nodes) {
    if (posMap.has(n.key)) continue
    addPos(posMap, n, orphanDist, orphanDist, 2, {})
  }

  const positions = nodes.map((n) => posMap.get(n.key)).filter((p): p is Pos => p != null)
  const parentMap = buildParentMap(centerKey, edges)
  const childrenMap = buildChildrenMap(edges)
  resolveOverlaps(positions, parentMap, childrenMap)
  compactToMinimumScale(positions, centerKey)
  return positions
}

/** 计算以 centerKey 为原点的节点坐标（F6 fitView 会自动居中） */
export function computeMindmapPositions(
  centerKey: string,
  nodes: GraphNode[],
  edges: GraphEdge[],
  _viewport?: LayoutViewport
): Map<string, LayoutPoint> {
  const positions = buildPosList(centerKey, nodes, edges)
  const out = new Map<string, LayoutPoint>()
  for (const p of positions) {
    out.set(p.key, { x: p.x, y: p.y })
  }
  return out
}

/** 检测布局是否存在节点重叠（测试用） */
export function hasNodeOverlap(
  centerKey: string,
  nodes: GraphNode[],
  edges: GraphEdge[]
): boolean {
  const positions = buildPosList(centerKey, nodes, edges)
  return hasAnyOverlap(positions)
}

/** 布局紧凑度指标（测试用）：非中心节点到原点的最大距离 */
export function layoutMaxRadius(
  centerKey: string,
  nodes: GraphNode[],
  edges: GraphEdge[]
): number {
  const positions = computeMindmapPositions(centerKey, nodes, edges)
  let maxR = 0
  for (const [key, p] of positions) {
    if (key === centerKey) continue
    maxR = Math.max(maxR, Math.hypot(p.x, p.y))
  }
  return maxR
}
