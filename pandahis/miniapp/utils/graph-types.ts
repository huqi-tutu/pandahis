/** 关系图谱 API 与布局共用类型（与 F6 无关） */
export type GraphNode = {
  key: string
  type?: string
  name?: string
  targetBoxId?: string
  extraJson?: string
}

export type GraphEdge = {
  fromKey: string
  toKey: string
  label?: string
}

export type GraphPayload = {
  centerNodeKey?: string
  nodes?: GraphNode[]
  edges?: GraphEdge[]
}
