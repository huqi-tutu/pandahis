"use strict";
/** 朝代详情 · 泳道 5 色轮换（标题栏 / 内容区均为半透明） */
Object.defineProperty(exports, "__esModule", { value: true });
exports.enrichSwimLaneVisuals = exports.laneTrackBackground = exports.resolveLaneHeightRpx = exports.LANE_HEAD_MIN_HEIGHT_RPX = exports.SWIM_LANE_PALETTE = exports.LANE_TRACK_ALPHA = exports.LANE_HEAD_ALPHA = void 0;
/** 60% 透明 = 40% 不透明度 */
exports.LANE_HEAD_ALPHA = 0.4;
/** 90% 透明 = 10% 不透明度 */
exports.LANE_TRACK_ALPHA = 0.1;
/* 视觉规范 v3：绢帛六色按泳道顺序循环（与 chip-badge-tokens.SILK_TONES 一致） */
exports.SWIM_LANE_PALETTE = [
    { solid: '#a2734f', trackAlpha: exports.LANE_TRACK_ALPHA },
    { solid: '#63899c', trackAlpha: exports.LANE_TRACK_ALPHA },
    { solid: '#b99d5b', trackAlpha: exports.LANE_TRACK_ALPHA },
    { solid: '#9a798f', trackAlpha: exports.LANE_TRACK_ALPHA },
    { solid: '#7d8a6a', trackAlpha: exports.LANE_TRACK_ALPHA },
    { solid: '#a46a65', trackAlpha: exports.LANE_TRACK_ALPHA },
];
/** 竖排标题 + 进度条所需最小高度，避免标题区撑破轨道背景 */
exports.LANE_HEAD_MIN_HEIGHT_RPX = 80;
function resolveLaneHeightRpx(trackHeightRpx) {
    const track = typeof trackHeightRpx === 'number' && trackHeightRpx > 0
        ? trackHeightRpx
        : exports.LANE_HEAD_MIN_HEIGHT_RPX;
    return Math.max(track, exports.LANE_HEAD_MIN_HEIGHT_RPX);
}
exports.resolveLaneHeightRpx = resolveLaneHeightRpx;
function parseHex(hex) {
    const h = hex.replace('#', '');
    return {
        r: parseInt(h.slice(0, 2), 16),
        g: parseInt(h.slice(2, 4), 16),
        b: parseInt(h.slice(4, 6), 16),
    };
}
function laneTrackBackground(solid, alpha) {
    const { r, g, b } = parseHex(solid);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}
exports.laneTrackBackground = laneTrackBackground;
function enrichSwimLaneVisuals(lane, laneIndex) {
    const tone = exports.SWIM_LANE_PALETTE[laneIndex % exports.SWIM_LANE_PALETTE.length];
    const trackHeight = lane.trackHeightRpx;
    return {
        ...lane,
        laneToneIndex: laneIndex % exports.SWIM_LANE_PALETTE.length,
        laneColor: tone.solid,
        laneHeadBg: laneTrackBackground(tone.solid, exports.LANE_HEAD_ALPHA),
        laneTrackBg: laneTrackBackground(tone.solid, tone.trackAlpha),
        laneHeightRpx: resolveLaneHeightRpx(trackHeight),
        borderColor: tone.solid,
    };
}
exports.enrichSwimLaneVisuals = enrichSwimLaneVisuals;
