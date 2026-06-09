/** 全景总览地图热区坐标（百分比），按 civilization code 映射 */
export const CIV_SPOT_BY_CODE: Record<string, { x: number; y: number }> = {
  HX: { x: 68, y: 35 },
  CX: { x: 73, y: 28 },
  RB: { x: 78, y: 30 },
  DNY: { x: 70, y: 48 },
  ZY: { x: 52, y: 32 },
  BY: { x: 58, y: 18 },
  NY: { x: 56, y: 42 },
  XY: { x: 46, y: 36 },
  NO: { x: 28, y: 30 },
  DO: { x: 32, y: 25 },
  XO: { x: 22, y: 26 },
  BO: { x: 26, y: 16 },
  BF: { x: 36, y: 38 },
  XF: { x: 26, y: 52 },
  DF: { x: 48, y: 55 },
  ZM: { x: 10, y: 45 },
  BM: { x: 8, y: 32 },
  NM: { x: 12, y: 65 },
}

export type CivSpot = {
  id: number
  name: string
  color: string
  img: string
  x: number
  y: number
}

export function buildCivSpots(
  civilizations: { id: number; displayName: string; code?: string; colorHex: string; tabImageUrl?: string }[]
): CivSpot[] {
  return civilizations.map((c, i) => {
    const code = (c.code || '').trim().toUpperCase()
    const pos = CIV_SPOT_BY_CODE[code] || { x: 20 + (i % 6) * 10, y: 30 + Math.floor(i / 6) * 12 }
    return {
      id: c.id,
      name: c.displayName,
      color: c.colorHex || '#84572F',
      img: c.tabImageUrl || '',
      x: pos.x,
      y: pos.y,
    }
  })
}
