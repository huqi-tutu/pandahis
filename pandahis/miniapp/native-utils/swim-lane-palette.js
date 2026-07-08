/** 朝代详情 · 泳道 5 色轮换（标题栏 / 内容区均为半透明） */

/** 60% 透明 = 40% 不透明度 */
const LANE_HEAD_ALPHA = 0.4
/** 90% 透明 = 10% 不透明度 */
const LANE_TRACK_ALPHA = 0.1

const SWIM_LANE_PALETTE = [
  { solid: '#a74713', trackAlpha: LANE_TRACK_ALPHA },
  { solid: '#6cb4a5', trackAlpha: LANE_TRACK_ALPHA },
  { solid: '#e9d4af', trackAlpha: LANE_TRACK_ALPHA },
  { solid: '#dd9b4b', trackAlpha: LANE_TRACK_ALPHA },
  { solid: '#442b15', trackAlpha: LANE_TRACK_ALPHA },
]

const LANE_HEAD_MIN_HEIGHT_RPX = 80

function parseHex(hex) {
  const h = hex.replace('#', '')
  return {
    r: parseInt(h.slice(0, 2), 16),
    g: parseInt(h.slice(2, 4), 16),
    b: parseInt(h.slice(4, 6), 16),
  }
}

function laneTrackBackground(solid, alpha) {
  const { r, g, b } = parseHex(solid)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

function resolveLaneHeightRpx(trackHeightRpx) {
  const track = typeof trackHeightRpx === 'number' && trackHeightRpx > 0
    ? trackHeightRpx
    : LANE_HEAD_MIN_HEIGHT_RPX
  return Math.max(track, LANE_HEAD_MIN_HEIGHT_RPX)
}

function enrichSwimLaneVisuals(lane, laneIndex) {
  const tone = SWIM_LANE_PALETTE[laneIndex % SWIM_LANE_PALETTE.length]
  return Object.assign({}, lane, {
    laneToneIndex: laneIndex % SWIM_LANE_PALETTE.length,
    laneColor: tone.solid,
    laneHeadBg: laneTrackBackground(tone.solid, LANE_HEAD_ALPHA),
    laneTrackBg: laneTrackBackground(tone.solid, tone.trackAlpha),
    laneHeightRpx: resolveLaneHeightRpx(lane.trackHeightRpx),
    borderColor: tone.solid,
  })
}

module.exports = {
  LANE_HEAD_ALPHA,
  LANE_TRACK_ALPHA,
  SWIM_LANE_PALETTE,
  LANE_HEAD_MIN_HEIGHT_RPX,
  laneTrackBackground,
  resolveLaneHeightRpx,
  enrichSwimLaneVisuals,
}
