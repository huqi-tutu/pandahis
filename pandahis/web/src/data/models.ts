export type CivilizationKey =
  | 'huaxia'
  | 'chaoxian'
  | 'japan'
  | 'sea'
  | 'india'
  | 'persia'
  | 'arab'
  | 'egypt'
  | 'eeu'
  | 'medi'
  | 'weu'
  | 'wafrica'
  | 'camer'
  | 'andes'

export type CategoryKey = 'junji' | 'shichen' | 'minlu' | 'dianzhi' | 'shilue'

export type Civilization = {
  id: CivilizationKey
  name: string
  colorVar: string
}

export type TimeAxisRow = {
  year: number
  label: string
  rowHeightPx: number
}

export type Unit = {
  id: string
  name: string
  /** 王朝层：朝代名称（PRD） */
  dynastyName?: string
  civilizationId: CivilizationKey
  crumbText: string
  eraText?: string
  startYear: number
  endYear: number
  durationYears: number
  summary: string
}

export type Box = {
  id: string
  unitId: string
  title: string
  categoryKey: CategoryKey
  year: number
  importanceLevel: number
  detail: string[]
  critiques: { author: string; eraText: string; content: string; source: string }[]
  relics: { name: string; description: string; museum: string }[]
  graph: { center: string; nodes: { key: string; name: string; kind: 'person' | 'event' | 'org' | 'place' | 'work'; badge?: string }[]; edges: { from: string; to: string; label: string }[] }
}

export type SearchSuggest = {
  hot: { keyword: string; hot: boolean }[]
  history: string[]
}

export type Topic = {
  id: string
  title: string
  subtitle: string
  keywords: string[]
  heroBoxIds: string[]
  heroUnitIds: string[]
}

