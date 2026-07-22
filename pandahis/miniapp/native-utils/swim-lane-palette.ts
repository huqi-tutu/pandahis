/** 朝代详情 · 泳道 5 色轮换（标题栏 / 内容区均为半透明） */

/** 60% 透明 = 40% 不透明度 */
export const LANE_HEAD_ALPHA = 0.4
/** 90% 透明 = 10% 不透明度 */
export const LANE_TRACK_ALPHA = 0.1

export type SwimLaneTone = {
  solid: string
  trackAlpha: number
}

/* 视觉规范 v3：与绢帛六色对齐（赭石/黛青/秋香/藕合/苔绿/绾红）；
 * 类目固定色见 chip-badge-tokens.ts 的 CATEGORY_TONES */
export const SWIM_LANE_PALETTE: SwimLaneTone[] = [
  { solid: '#a2734f', trackAlpha: LANE_TRACK_ALPHA },
  { solid: '#63899c', trackAlpha: LANE_TRACK_ALPHA },
  { solid: '#b99d5b', trackAlpha: LANE_TRACK_ALPHA },
  { solid: '#9a798f', trackAlpha: LANE_TRACK_ALPHA },
  { solid: '#7d8a6a', trackAlpha: LANE_TRACK_ALPHA },
  { solid: '#a46a65', trackAlpha: LANE_TRACK_ALPHA },
]

/** 竖排标题 + 进度条所需最小高度，避免标题区撑破轨道背景 */
export const LANE_HEAD_MIN_HEIGHT_RPX = 80

export function resolveLaneHeightRpx(trackHeightRpx?: number | null): number {
  const track = typeof trackHeightRpx === 'number' && trackHeightRpx > 0
    ? trackHeightRpx
    : LANE_HEAD_MIN_HEIGHT_RPX
  return Math.max(track, LANE_HEAD_MIN_HEIGHT_RPX)
}

function parseHex(hex: string) {
  const h = hex.replace('#', '')
  return {
    r: parseInt(h.slice(0, 2), 16),
    g: parseInt(h.slice(2, 4), 16),
    b: parseInt(h.slice(4, 6), 16),
  }
}

export function laneTrackBackground(solid: string, alpha: number): string {
  const { r, g, b } = parseHex(solid)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

export function enrichSwimLaneVisuals<T extends Record<string, unknown>>(
  lane: T,
  laneIndex: number
): T & {
  laneToneIndex: number
  laneColor: string
  laneHeadBg: string
  laneTrackBg: string
  laneHeightRpx: number
  borderColor: string
} {
  const tone = SWIM_LANE_PALETTE[laneIndex % SWIM_LANE_PALETTE.length]
  const trackHeight = (lane as { trackHeightRpx?: number | null }).trackHeightRpx
  return {
    ...lane,
    laneToneIndex: laneIndex % SWIM_LANE_PALETTE.length,
    laneColor: tone.solid,
    laneHeadBg: laneTrackBackground(tone.solid, LANE_HEAD_ALPHA),
    laneTrackBg: laneTrackBackground(tone.solid, tone.trackAlpha),
    laneHeightRpx: resolveLaneHeightRpx(trackHeight),
    borderColor: tone.solid,
  }
}
