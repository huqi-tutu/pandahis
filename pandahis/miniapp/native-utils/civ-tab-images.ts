/** 文明 Tab 配图：COS 公网 URL（按 slug → 文明 CODE），避免打进小程序包 */
const COS_BASE =
  'https://pandahis-1300045339.cos.ap-chengdu.myqcloud.com/histomap/civ-tab'

/** 与后端 histomap.civ-tab.image-cache-bust 对齐；换图后递增 */
export const CIV_TAB_IMAGE_CACHE_BUST = '2026072001'

/** slug → civilization_l1.code（与 DB / COS 文件名一致） */
export const CIV_CODE_BY_SLUG: Record<string, string> = {
  huaxia: 'HX',
  chaoxian: 'CX',
  japan: 'RB',
  sea: 'DNY',
  centralasia: 'ZY',
  northasia: 'BY',
  southasia: 'NY',
  westasia: 'XY',
  southeu: 'NO',
  easteu: 'DO',
  westeu: 'XO',
  northeu: 'BO',
  northafrica: 'BF',
  westafrica: 'XF',
  eastafrica: 'DF',
  centralamerica: 'ZM',
  northamerica: 'BM',
  southamerica: 'NM',
}

export function civTabImage(id: string, cacheBust: string = CIV_TAB_IMAGE_CACHE_BUST): string {
  const code = CIV_CODE_BY_SLUG[id]
  if (!code) return ''
  const v = String(cacheBust || CIV_TAB_IMAGE_CACHE_BUST).trim()
  return `${COS_BASE}/${code}.png?v=${encodeURIComponent(v)}`
}

/** 兼容旧调用方：保留 slug → 路径表形态 */
export const CIV_TAB_IMAGES: Record<string, string> = Object.fromEntries(
  Object.keys(CIV_CODE_BY_SLUG).map((slug) => [slug, civTabImage(slug)])
)
