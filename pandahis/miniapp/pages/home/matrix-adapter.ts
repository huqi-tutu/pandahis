/** 产品 CIV_TABS slug ↔ 后端 civilization code */
export const CIV_SLUG_BY_CODE: Record<string, string> = {
  HX: 'huaxia',
  CX: 'chaoxian',
  RB: 'japan',
  DNY: 'sea',
  ZY: 'centralasia',
  BY: 'northasia',
  NY: 'southasia',
  XY: 'westasia',
  BF: 'northafrica',
  NO: 'southeu',
  DO: 'easteu',
  XO: 'westeu',
  BO: 'northeu',
  XF: 'westafrica',
  DF: 'eastafrica',
  ZM: 'centralamerica',
  BM: 'northamerica',
  NM: 'southamerica',
}

export const CIV_CODE_BY_SLUG: Record<string, string> = Object.fromEntries(
  Object.entries(CIV_SLUG_BY_CODE).map(([code, slug]) => [slug, code])
)

/** overview 热区 id 与 matrix CIV_TABS slug 对齐 */
export const OVERVIEW_SPOT_TO_MATRIX_SLUG: Record<string, string> = {
  huaxia: 'huaxia',
  chaoxian: 'chaoxian',
  japan: 'japan',
  sea: 'sea',
  india: 'southasia',
  persia: 'westasia',
  egypt: 'northafrica',
  eeu: 'easteu',
  medi: 'southeu',
  weu: 'westeu',
  wafrica: 'westafrica',
  camer: 'centralamerica',
  andes: 'southamerica',
}

export const OVERVIEW_CIV_SPOTS = [
  { id: 'huaxia', name: '华夏', color: '#C42828', img: '/配图/文明tab配图/01_华夏.png', x: 68, y: 35 },
  { id: 'chaoxian', name: '朝鲜', color: '#5B8DEF', img: '/配图/文明tab配图/02_朝鲜.png', x: 73, y: 28 },
  { id: 'japan', name: '日本', color: '#E88FB5', img: '/配图/文明tab配图/03_日本.png', x: 78, y: 30 },
  { id: 'sea', name: '东南亚', color: '#5D8D8A', img: '/配图/文明tab配图/04_东南亚.png', x: 70, y: 48 },
  { id: 'india', name: '南亚', color: '#E88B3F', img: '/配图/文明tab配图/07_南亚.png', x: 56, y: 42 },
  { id: 'persia', name: '西亚', color: '#B87A3A', img: '/配图/文明tab配图/08_西亚.png', x: 46, y: 36 },
  { id: 'egypt', name: '北非', color: '#D6A84A', img: '/配图/文明tab配图/13_北非.png', x: 36, y: 38 },
  { id: 'eeu', name: '东欧', color: '#8974B8', img: '/配图/文明tab配图/10_东欧.png', x: 32, y: 25 },
  { id: 'medi', name: '南欧', color: '#4A80D0', img: '/配图/文明tab配图/09_南欧.png', x: 28, y: 30 },
  { id: 'weu', name: '西欧', color: '#7F96B8', img: '/配图/文明tab配图/11_西欧.png', x: 22, y: 26 },
  { id: 'wafrica', name: '西非', color: '#B55E3F', img: '/配图/文明tab配图/14_西非.png', x: 26, y: 52 },
  { id: 'camer', name: '中美', color: '#D16848', img: '/配图/文明tab配图/16_中美.png', x: 10, y: 45 },
  { id: 'andes', name: '南美', color: '#A27548', img: '/配图/文明tab配图/18_南美.png', x: 12, y: 65 },
]

export function buildDynastyUnitMap(
  cells: { unitCard?: { unitId?: string; title?: string } }[]
): Record<string, string> {
  const map: Record<string, string> = {}
  for (const c of cells || []) {
    const card = c.unitCard
    if (!card?.unitId || !card.title) continue
    map[card.title] = card.unitId
    map[card.unitId] = card.unitId
  }
  return map
}

export function resolveUnitId(dynastyKey: string, map: Record<string, string>): string {
  const k = String(dynastyKey || '').trim()
  if (!k) return ''
  if (map[k]) return map[k]
  for (const [title, id] of Object.entries(map)) {
    if (title.includes(k) || k.includes(title)) return id
  }
  return ''
}

export type NavigationTargetOpts = {
  entityType?: string
  entityId?: string
  legacyId?: string
  dynastyId?: string
  person?: string
  dynasty?: string
  displayName?: string
}

/** 首页矩阵卡片 → 详情页 unitId（朝代详情优先 CD_* / dynastyId） */
export function resolveNavigationUnitId(
  opts: NavigationTargetOpts,
  map: Record<string, string>
): string {
  const entityType = String(opts.entityType || '').trim()
  const dynastyId = String(opts.dynastyId || '').trim()
  const entityId = String(opts.entityId || '').trim()
  const legacyId = String(opts.legacyId || '').trim()
  const person = String(opts.person || '').trim()
  const dynasty = String(opts.dynasty || opts.displayName || '').trim()
  const seen = new Set<string>()
  const candidates: string[] = []

  function push(id: string) {
    const v = String(id || '').trim()
    if (!v || seen.has(v)) return
    seen.add(v)
    candidates.push(v)
  }

  push(dynastyId)
  push(resolveUnitId(dynasty, map))

  if (entityType === 'emperor') {
    push(entityId)
    push(legacyId)
    push(resolveUnitId(person, map))
  } else {
    push(entityId)
    push(legacyId)
    if (person) push(resolveUnitId(person, map))
  }

  const dynastyCandidate = candidates.find((id) => id.startsWith('CD_'))
  return dynastyCandidate || candidates[0] || ''
}
