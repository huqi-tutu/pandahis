"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.chipBadgeToken = exports.CHIP_BADGE_TOKENS = exports.categoryRailColor = exports.categoryTone = exports.CATEGORY_TONES = void 0;
const TONE_ZHESHI = { solid: '#A2734F', deep: '#7B573C', bg: '#ECE4DB' }; /* 赭石 */
const TONE_DAIQING = { solid: '#63899C', deep: '#4B6877', bg: '#E3E7E6' }; /* 黛青 */
const TONE_QIUXIANG = { solid: '#B99D5B', deep: '#8D7745', bg: '#EFEADD' }; /* 秋香 */
const TONE_OUHE = { solid: '#9A798F', deep: '#755C6D', bg: '#EBE4E4' }; /* 藕合 */
const TONE_TAILV = { solid: '#7D8A6A', deep: '#5F6951', bg: '#E7E7DF' }; /* 苔绿 */
const TONE_WANHONG = { solid: '#A46A65', deep: '#7D514D', bg: '#ECE2DE' }; /* 绾红 */
exports.CATEGORY_TONES = {
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
};
const FALLBACK_TONE = { solid: '#8C817B', deep: '#5F5854', bg: '#ECE9E5' };
function categoryTone(categoryKey) {
    const key = String(categoryKey || '').trim();
    return exports.CATEGORY_TONES[key] || FALLBACK_TONE;
}
exports.categoryTone = categoryTone;
/** 左缘类目细条颜色（覆盖后端下发的旧色值，前端为准）；未知类目回退到传入色 */
function categoryRailColor(categoryKey, fallback) {
    const key = String(categoryKey || '').trim();
    const tone = exports.CATEGORY_TONES[key];
    if (tone)
        return tone.solid;
    return fallback || FALLBACK_TONE.solid;
}
exports.categoryRailColor = categoryRailColor;
exports.CHIP_BADGE_TOKENS = Object.keys(exports.CATEGORY_TONES).reduce((acc, key) => {
    const tone = exports.CATEGORY_TONES[key];
    acc[key] = { bg: tone.bg, text: tone.deep };
    return acc;
}, {});
function chipBadgeToken(categoryKey) {
    const key = String(categoryKey || '').trim();
    return exports.CHIP_BADGE_TOKENS[key] || { bg: FALLBACK_TONE.bg, text: FALLBACK_TONE.deep };
}
exports.chipBadgeToken = chipBadgeToken;
