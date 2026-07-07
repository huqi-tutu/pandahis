/** 盒子 category_key → 展示名（与后端 BoxCategorySupport 一致） */
export function categoryLabel(key: string): string {
  switch (key) {
    case 'junji':
      return '君王'
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
