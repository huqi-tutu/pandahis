  /** 朝代详情固定 10 泳道顺序 */
export const PRD_CATEGORY_KEYS = [
  'junji',
  'zongqi',
  'wenchen',
  'wujiang',
  'shilue',
  'dianzhi',
  'lunzhu',
  'huanguan',
  'shuzhong',
  'fanzhu',
] as const

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
      return key || ''
  }
}
