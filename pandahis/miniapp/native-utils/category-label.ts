/** 人物七类 category_key（与后端 BoxCategorySupport 一致） */
export const PERSON_BOX_CATEGORY_KEYS = [
  'junji',
  'zhuhou',
  'zongqi',
  'wenchen',
  'wujiang',
  'huanguan',
  'shuzhong',
  'shichen',
  'minlu',
] as const

/** 是否为人物类史略（君王/诸侯/宗戚/文臣/武将/宦官/庶众） */
export function isPersonBoxCategory(key: string): boolean {
  const k = String(key || '').trim()
  if (!k) return false
  return (PERSON_BOX_CATEGORY_KEYS as readonly string[]).includes(k)
}

/** 盒子 category_key → 展示名（与后端 BoxCategorySupport 一致） */
export function categoryLabel(key: string): string {
  switch (key) {
    case 'junji':
      return '君王'
    case 'zhuhou':
      return '诸侯'
    case 'zongqi':
      return '宗戚'
    case 'wenchen':
      return '文臣'
    case 'wujiang':
      return '武将'
    case 'shilue':
      return '事略'
    case 'dianzhi':
      return '典制'
    case 'lunzhu':
      return '论著'
    case 'huanguan':
      return '宦官'
    case 'shuzhong':
      return '庶众'
    case 'fanzhu':
      return '蕃祚'
    case 'shichen':
      return '士臣'
    case 'minlu':
      return '民录'
    default:
      return key || '其他'
  }
}

export function buildFavoriteSummary(items: { categoryKey?: string }[]): string {
  if (!items.length) return '暂无'
  const groups: Record<string, number> = {}
  for (const it of items) {
    const label = categoryLabel(it.categoryKey || '')
    groups[label] = (groups[label] || 0) + 1
  }
  return Object.entries(groups)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 2)
    .map(([k, v]) => `${k} ${v}`)
    .join(' · ')
}
