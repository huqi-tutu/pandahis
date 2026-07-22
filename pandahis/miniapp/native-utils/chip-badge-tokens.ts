/** 史略类目 → 绢帛六色固定映射（视觉规范 v3）
 * 同一类目在所有朝代恒定一色；六色不够十类，复用色在类目顺序上间隔 ≥ 4，相邻类目不同色。
 * junji 君王=赭石 · zongqi 宗戚=绾红 · wenchen 文臣=黛青 · wujiang 武将=秋香
 * shilue 事略=苔绿 · dianzhi 典制=藕合 · lunzhu 论著=黛青 · huanguan 宦官=赭石
 * shuzhong 庶众=秋香 · fanzhu 蕃祚=绾红
 */
export type ChipBadgeToken = {
  bg: string
  text: string
}

export type CategoryTone = {
  /** 左缘类目细条 / 徽章底 */
  solid: string
  /** 小号文字（标签字、类目名） */
  deep: string
  /** 标签底：本色 14% 叠纸底后的预混不透明色 */
  bg: string
}

const TONE_ZHESHI: CategoryTone = { solid: '#A2734F', deep: '#7B573C', bg: '#ECE4DB' } /* 赭石 */
const TONE_DAIQING: CategoryTone = { solid: '#63899C', deep: '#4B6877', bg: '#E3E7E6' } /* 黛青 */
const TONE_QIUXIANG: CategoryTone = { solid: '#B99D5B', deep: '#8D7745', bg: '#EFEADD' } /* 秋香 */
const TONE_OUHE: CategoryTone = { solid: '#9A798F', deep: '#755C6D', bg: '#EBE4E4' } /* 藕合 */
const TONE_TAILV: CategoryTone = { solid: '#7D8A6A', deep: '#5F6951', bg: '#E7E7DF' } /* 苔绿 */
const TONE_WANHONG: CategoryTone = { solid: '#A46A65', deep: '#7D514D', bg: '#ECE2DE' } /* 绾红 */

export const CATEGORY_TONES: Record<string, CategoryTone> = {
  junji: TONE_ZHESHI,
  zongqi: TONE_WANHONG,
  wenchen: TONE_DAIQING,
  wujiang: TONE_QIUXIANG,
  shilue: TONE_TAILV,
  dianzhi: TONE_OUHE,
  lunzhu: TONE_DAIQING,
  huanguan: TONE_ZHESHI,
  shuzhong: TONE_QIUXIANG,
  fanzhu: TONE_WANHONG,
  /* 标注层别名 → 泳道类目 */
  shichen: TONE_DAIQING,
  minlu: TONE_QIUXIANG,
}

const FALLBACK_TONE: CategoryTone = { solid: '#8C817B', deep: '#5F5854', bg: '#ECE9E5' }

export function categoryTone(categoryKey?: string): CategoryTone {
  const key = String(categoryKey || '').trim()
  return CATEGORY_TONES[key] || FALLBACK_TONE
}

/** 左缘类目细条颜色（覆盖后端下发的旧色值，前端为准）；未知类目回退到传入色 */
export function categoryRailColor(categoryKey?: string, fallback?: string): string {
  const key = String(categoryKey || '').trim()
  const tone = CATEGORY_TONES[key]
  if (tone) return tone.solid
  return fallback || FALLBACK_TONE.solid
}

export const CHIP_BADGE_TOKENS: Record<string, ChipBadgeToken> = Object.keys(CATEGORY_TONES).reduce(
  (acc, key) => {
    const tone = CATEGORY_TONES[key]
    acc[key] = { bg: tone.bg, text: tone.deep }
    return acc
  },
  {} as Record<string, ChipBadgeToken>,
)

export function chipBadgeToken(categoryKey?: string): ChipBadgeToken {
  const key = String(categoryKey || '').trim()
  return CHIP_BADGE_TOKENS[key] || { bg: FALLBACK_TONE.bg, text: FALLBACK_TONE.deep }
}
