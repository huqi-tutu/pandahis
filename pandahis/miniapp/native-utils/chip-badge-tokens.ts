/** 史略类目 → 绢帛六色（设计系统 v3）
 *
 * 规则：按朝代详情 **11 泳道固定顺序**，依次循环 c1→c6（赭石→黛青→秋香→藕合→苔绿→绾红）。
 * 同一 category_key 在所有朝代恒定一色；标注层别名（shichen/minlu）跟随对应泳道。
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

const TONE_ZHESHI: CategoryTone = { solid: '#A2734F', deep: '#7B573C', bg: '#ECE4DB' } /* c1 赭石 */
const TONE_DAIQING: CategoryTone = { solid: '#63899C', deep: '#4B6877', bg: '#E3E7E6' } /* c2 黛青 */
const TONE_QIUXIANG: CategoryTone = { solid: '#B99D5B', deep: '#8D7745', bg: '#EFEADD' } /* c3 秋香 */
const TONE_OUHE: CategoryTone = { solid: '#9A798F', deep: '#755C6D', bg: '#EBE4E4' } /* c4 藕合 */
const TONE_TAILV: CategoryTone = { solid: '#7D8A6A', deep: '#5F6951', bg: '#E7E7DF' } /* c5 苔绿 */
const TONE_WANHONG: CategoryTone = { solid: '#A46A65', deep: '#7D514D', bg: '#ECE2DE' } /* c6 绾红 */

/** 绢帛六色母色板（固定顺序，勿打乱） */
export const SILK_TONES: readonly CategoryTone[] = [
  TONE_ZHESHI,
  TONE_DAIQING,
  TONE_QIUXIANG,
  TONE_OUHE,
  TONE_TAILV,
  TONE_WANHONG,
]

/** 朝代详情 11 泳道顺序（与 BoxCategorySupport / PRD_CATEGORY_KEYS 一致） */
export const SWIM_LANE_CATEGORY_KEYS = [
  'junji',
  'zhuhou',
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

function buildCategoryTones(): Record<string, CategoryTone> {
  const tones: Record<string, CategoryTone> = {}
  SWIM_LANE_CATEGORY_KEYS.forEach((key, index) => {
    tones[key] = SILK_TONES[index % SILK_TONES.length]
  })
  tones.shichen = tones.wenchen
  tones.minlu = tones.shuzhong
  return tones
}

export const CATEGORY_TONES: Record<string, CategoryTone> = buildCategoryTones()

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
