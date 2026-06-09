import generated from './generated.json'
import type { Box, Civilization, SearchSuggest, TimeAxisRow, Topic, Unit } from './models'

/** PRD 王朝层：五类横轴展示顺序 */
export const CATEGORY_LABELS: Record<string, string> = {
  junji: '君纪',
  shichen: '士臣',
  dianzhi: '典制',
  shilue: '事略',
  minlu: '民录',
}

export function yearLabel(year: number) {
  return year < 0 ? `前${Math.abs(year)}` : String(year)
}

type GeneratedShape = {
  civilizations: Civilization[]
  timeAxis: TimeAxisRow[]
  units: Unit[]
  boxes: Box[]
  searchSuggest: SearchSuggest
  topics: Topic[]
}

const DATA = generated as unknown as GeneratedShape

export const CIVILIZATIONS = DATA.civilizations
export const TIME_AXIS = DATA.timeAxis
export const UNITS = DATA.units.map((u) => ({
  ...u,
  eraText: u.eraText ?? undefined,
})) satisfies Unit[]
export const BOXES = DATA.boxes
export const SEARCH_SUGGEST = DATA.searchSuggest
export const TOPICS = DATA.topics ?? []

export function getUnit(unitId: string) {
  return UNITS.find((u) => u.id === unitId) ?? null
}

export function getBox(boxId: string) {
  return BOXES.find((b) => b.id === boxId) ?? null
}

export function listBoxesByUnit(unitId: string) {
  return BOXES.filter((b) => b.unitId === unitId)
}

/** 年份接近的其他地域单元（用于朝代详情顶部横滑） */
export function listRelatedCrossCivUnits(center: Unit, limit = 12): Unit[] {
  return UNITS.filter((u) => u.id !== center.id && u.civilizationId !== center.civilizationId)
    .map((u) => ({
      u,
      d: Math.min(Math.abs(u.startYear - center.startYear), Math.abs(u.endYear - center.endYear)),
    }))
    .sort((a, b) => a.d - b.d || a.u.startYear - b.u.startYear)
    .slice(0, limit)
    .map((x) => x.u)
}

/** 同地域时间线上的下一单元（启发式：即位时间不早于当前单元结束） */
export function nextDynastyUnit(center: Unit): Unit | null {
  const same = UNITS.filter((u) => u.civilizationId === center.civilizationId && u.id !== center.id)
  const after = same.filter((u) => u.startYear >= center.endYear)
  if (after.length) {
    return [...after].sort((a, b) => a.startYear - b.startYear || a.endYear - b.endYear)[0] ?? null
  }
  const later = same.filter((u) => u.startYear > center.startYear)
  return later.sort((a, b) => a.startYear - b.startYear)[0] ?? null
}

export function searchAll(q: string) {
  const qq = q.trim()
  if (!qq) return []

  const hitsBoxes = BOXES.filter((b) => b.title.includes(qq)).map((b) => ({
    type: 'box' as const,
    id: b.id,
    title: b.title,
    pathText: (() => {
      const u = UNITS.find((x) => x.id === b.unitId)
      const catName = CATEGORY_LABELS[b.categoryKey] ?? b.categoryKey
      if (!u) return `… › ${catName}`
      const civ = u.crumbText.split(' · ')[0] ?? '文明'
      return `${civ} › ${u.name} › ${catName}`
    })(),
    desc: b.detail.join(''),
  }))

  const hitsUnits = UNITS.filter((u) => u.name.includes(qq)).map((u) => ({
    type: 'unit' as const,
    id: u.id,
    title: u.name,
    pathText: `${u.crumbText.replaceAll(' · ', ' › ')}`,
    desc: u.summary,
  }))

  return [...hitsBoxes, ...hitsUnits]
}

export function getTopic(topicId: string) {
  return TOPICS.find((t) => t.id === topicId) ?? null
}

