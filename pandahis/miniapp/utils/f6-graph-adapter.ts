/**
 * 将后端 /boxes/:id/graph 数据转为 @antv/f6-wx RadialLayout 所需结构。
 * MIT @antv/f6-wx — 本地布局，无云端 API。
 */
import { computeMindmapPositions } from './relation-mindmap-layout'

export type ApiGraphNode = {
  key: string
  type?: string
  name?: string
  targetBoxId?: string
  extraJson?: string
}

export type ApiGraphEdge = {
  fromKey: string
  toKey: string
  label?: string
}

export type ApiGraphPayload = {
  centerNodeKey?: string
  nodes?: ApiGraphNode[]
  edges?: ApiGraphEdge[]
}

export type F6RelationType = 'center' | 'family' | 'colleague' | 'enemy' | 'teacher' | 'other'

export type F6GraphNode = {
  id: string
  label: string
  depth: number
  relationType: F6RelationType
  targetBoxId?: string
  size: number
  x?: number
  y?: number
  hasHiddenChildren?: boolean
  collapsed?: boolean
  style?: Record<string, unknown>
  labelCfg?: Record<string, unknown>
}

export type F6GraphEdge = {
  source: string
  target: string
  label?: string
  type: string
  style: Record<string, unknown>
  labelCfg?: Record<string, unknown>
}

export const MAX_RENDER_DEPTH = 4

const STROKE: Record<F6RelationType, string> = {
  center: 'rgba(140, 72, 58, 0.55)',
  family: 'rgba(162, 115, 79, 0.55)',
  colleague: 'rgba(127, 176, 105, 0.55)',
  enemy: 'rgba(180, 100, 100, 0.55)',
  teacher: 'rgba(99, 137, 156, 0.55)',
  other: 'rgba(120, 110, 105, 0.45)',
}

function parseExtra(extraJson?: string): Record<string, unknown> {
  if (!extraJson) return {}
  try {
    return JSON.parse(extraJson) as Record<string, unknown>
  } catch {
    return {}
  }
}

function normalizeCategory(raw: string): string {
  const g = (raw || '').trim()
  if (g === '君臣') return '同僚'
  if (g === '敌对') return '外敌'
  return g
}

function isCategoryNode(node: ApiGraphNode): boolean {
  if (node.type === 'category') return true
  if (String(node.key || '').startsWith('cat_')) return true
  const extra = parseExtra(node.extraJson)
  return extra.isCategoryNode === true
}

export function mapRelationType(node: ApiGraphNode, centerKey: string): F6RelationType {
  if (node.key === centerKey) return 'center'
  const extra = parseExtra(node.extraJson)
  const cat = normalizeCategory(
    String(extra['关系类别'] || extra.group || extra.category || '')
  )
  if (isCategoryNode(node)) {
    if (cat.includes('家庭') || node.name === '家庭') return 'family'
    if (cat.includes('同僚') || node.name === '同僚') return 'colleague'
    if (cat.includes('外敌') || cat.includes('敌对') || node.name === '外敌') return 'enemy'
    if (cat.includes('师从') || node.name === '师从') return 'teacher'
    return 'other'
  }
  if (cat.includes('家庭')) return 'family'
  if (cat.includes('同僚')) return 'colleague'
  if (cat.includes('外敌') || cat.includes('敌对')) return 'enemy'
  if (cat.includes('师从')) return 'teacher'
  return 'other'
}

export function buildParentMap(centerKey: string, edges: ApiGraphEdge[]): Map<string, string> {
  const adj = new Map<string, string[]>()
  for (const e of edges || []) {
    if (!adj.has(e.fromKey)) adj.set(e.fromKey, [])
    adj.get(e.fromKey)!.push(e.toKey)
  }
  const parent = new Map<string, string>()
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

export function computeDepths(centerKey: string, edges: ApiGraphEdge[]): Map<string, number> {
  const adj = new Map<string, string[]>()
  for (const e of edges || []) {
    if (!adj.has(e.fromKey)) adj.set(e.fromKey, [])
    adj.get(e.fromKey)!.push(e.toKey)
  }
  const depth = new Map<string, number>()
  depth.set(centerKey, 0)
  const q = [centerKey]
  while (q.length) {
    const u = q.shift()!
    for (const v of adj.get(u) || []) {
      if (depth.has(v)) continue
      depth.set(v, (depth.get(u) || 0) + 1)
      q.push(v)
    }
  }
  return depth
}

function nodeVisible(
  key: string,
  depthMap: Map<string, number>,
  parentMap: Map<string, string>,
  expandedKeys: Set<string>
): boolean {
  const d = depthMap.get(key)
  if (d === undefined) return false
  if (d <= MAX_RENDER_DEPTH) return true
  if (d !== MAX_RENDER_DEPTH + 1) return false
  const parent = parentMap.get(key)
  if (!parent) return false
  return (depthMap.get(parent) === MAX_RENDER_DEPTH && expandedKeys.has(parent))
}

export type GraphLayoutViewport = {
  width?: number
  height?: number
}

export function toF6GraphData(
  payload: ApiGraphPayload,
  expandedKeys: Set<string> = new Set(),
  viewport?: GraphLayoutViewport
): { nodes: F6GraphNode[]; edges: F6GraphEdge[]; centerId: string; hiddenCount: number } {
  const nodes = payload.nodes || []
  const edges = payload.edges || []
  const centerId = payload.centerNodeKey || nodes[0]?.key || ''
  if (!centerId) return { nodes: [], edges: [], centerId: '', hiddenCount: 0 }

  const depthMap = computeDepths(centerId, edges)
  const parentMap = buildParentMap(centerId, edges)
  const nodeByKey = new Map(nodes.map((n) => [n.key, n]))

  let hiddenCount = 0
  for (const n of nodes) {
    const d = depthMap.get(n.key)
    if (d !== undefined && d > MAX_RENDER_DEPTH && !nodeVisible(n.key, depthMap, parentMap, expandedKeys)) {
      hiddenCount++
    }
  }

  const visibleIds = new Set<string>()
  for (const n of nodes) {
    if (nodeVisible(n.key, depthMap, parentMap, expandedKeys)) visibleIds.add(n.key)
  }

  const f6Nodes: F6GraphNode[] = []
  for (const id of visibleIds) {
    const n = nodeByKey.get(id)
    if (!n) continue
    const depth = depthMap.get(id) ?? 0
    const relationType = mapRelationType(n, centerId)
    const name = (n.name || n.key).trim()
    const childBeyond = (edges || []).some(
      (e) => e.fromKey === id && (depthMap.get(e.toKey) ?? 999) > MAX_RENDER_DEPTH
    )
    const hasHiddenChildren = depth === MAX_RENDER_DEPTH && childBeyond
    const collapsed = hasHiddenChildren && !expandedKeys.has(id)
    const label = collapsed ? `${name} ▸` : expandedKeys.has(id) && hasHiddenChildren ? `${name} ▾` : name
    const size = relationType === 'center' ? 64 : isCategoryNode(n) ? 52 : 46

    const style: Record<string, unknown> =
      relationType === 'center'
        ? { fill: '#B85C48', stroke: 'rgba(140, 72, 58, 0.85)', lineWidth: 2 }
        : { fill: '#FAF8F5', stroke: STROKE[relationType], lineWidth: 1.5 }

    f6Nodes.push({
      id,
      label,
      depth,
      relationType,
      targetBoxId: n.targetBoxId,
      size,
      hasHiddenChildren,
      collapsed,
      style,
      labelCfg: {
        style: {
          fontSize: relationType === 'center' ? 13 : 11,
          fill: relationType === 'center' ? '#FAF8F5' : '#343A40',
          fontWeight: relationType === 'center' ? 600 : 400,
        },
      },
    })
  }

  const f6Edges: F6GraphEdge[] = []
  const edgesBySource = new Map<string, F6GraphEdge[]>()
  for (const e of edges || []) {
    if (!visibleIds.has(e.fromKey) || !visibleIds.has(e.toKey)) continue
    const target = nodeByKey.get(e.toKey)
    const relationType = target ? mapRelationType(target, centerId) : 'other'
    const label = (e.label || '').trim()
    const edge: F6GraphEdge = {
      source: e.fromKey,
      target: e.toKey,
      label: label || undefined,
      type: 'quadratic',
      style: {
        stroke: STROKE[relationType],
        lineWidth: 1.5,
        lineDash: [4, 4],
        endArrow: false,
      },
    }
    f6Edges.push(edge)
    if (!edgesBySource.has(e.fromKey)) edgesBySource.set(e.fromKey, [])
    edgesBySource.get(e.fromKey)!.push(edge)
  }

  for (const group of edgesBySource.values()) {
    group.sort((a, b) => a.target.localeCompare(b.target))
    group.forEach((edge, idx) => {
      if (!edge.label) return
      const n = group.length
      const refY = n <= 1 ? 0 : -10 + (idx / Math.max(1, n - 1)) * 20
      edge.labelCfg = {
        autoRotate: true,
        refY,
        style: {
          fontSize: 9,
          fill: '#FAF8F5',
          background: {
            fill: 'rgba(108, 117, 125, 0.88)',
            padding: [2, 5, 2, 5],
            radius: 4,
          },
        },
      }
    })
  }

  const layoutNodes = nodes.filter((n) => visibleIds.has(n.key))
  const layoutEdges = (edges || []).filter(
    (e) => visibleIds.has(e.fromKey) && visibleIds.has(e.toKey)
  )
  const positions = computeMindmapPositions(centerId, layoutNodes, layoutEdges, viewport)
  for (const node of f6Nodes) {
    const p = positions.get(node.id)
    if (p) {
      node.x = p.x
      node.y = p.y
    }
  }

  return { nodes: f6Nodes, edges: f6Edges, centerId, hiddenCount }
}

export function strokeForRelation(relationType: F6RelationType): string {
  return STROKE[relationType] || STROKE.other
}
