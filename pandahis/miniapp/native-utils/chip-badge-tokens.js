"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.chipBadgeToken = exports.CHIP_BADGE_TOKENS = exports.categoryRailColor = exports.categoryTone = exports.CATEGORY_TONES = exports.SWIM_LANE_CATEGORY_KEYS = exports.SILK_TONES = void 0;
const TONE_ZHESHI = { solid: '#A2734F', deep: '#7B573C', bg: '#ECE4DB' }; /* c1 赭石 */
const TONE_DAIQING = { solid: '#63899C', deep: '#4B6877', bg: '#E3E7E6' }; /* c2 黛青 */
const TONE_QIUXIANG = { solid: '#B99D5B', deep: '#8D7745', bg: '#EFEADD' }; /* c3 秋香 */
const TONE_OUHE = { solid: '#9A798F', deep: '#755C6D', bg: '#EBE4E4' }; /* c4 藕合 */
const TONE_TAILV = { solid: '#7D8A6A', deep: '#5F6951', bg: '#E7E7DF' }; /* c5 苔绿 */
const TONE_WANHONG = { solid: '#A46A65', deep: '#7D514D', bg: '#ECE2DE' }; /* c6 绾红 */
/** 绢帛六色母色板（固定顺序，勿打乱） */
exports.SILK_TONES = [
    TONE_ZHESHI,
    TONE_DAIQING,
    TONE_QIUXIANG,
    TONE_OUHE,
    TONE_TAILV,
    TONE_WANHONG,
];
/** 朝代详情 11 泳道顺序（与 BoxCategorySupport / PRD_CATEGORY_KEYS 一致） */
exports.SWIM_LANE_CATEGORY_KEYS = [
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
];
function buildCategoryTones() {
    const tones = {};
    exports.SWIM_LANE_CATEGORY_KEYS.forEach((key, index) => {
        tones[key] = exports.SILK_TONES[index % exports.SILK_TONES.length];
    });
    tones.shichen = tones.wenchen;
    tones.minlu = tones.shuzhong;
    return tones;
}
exports.CATEGORY_TONES = buildCategoryTones();
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
