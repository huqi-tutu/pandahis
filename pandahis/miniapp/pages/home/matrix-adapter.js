"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.resolveNavigationUnitId = exports.resolveDetailUnitIds = exports.resolveUnitId = exports.buildDynastyUnitMap = exports.OVERVIEW_CIV_SPOTS = exports.OVERVIEW_SPOT_TO_MATRIX_SLUG = exports.CIV_CODE_BY_SLUG = exports.CIV_SLUG_BY_CODE = void 0;
/** 产品 CIV_TABS slug ↔ 后端 civilization code */
const civ_tab_images_1 = require("../../native-utils/civ-tab-images");
/** 与素材 01–18 / DB sort_order 一致 */
exports.CIV_SLUG_BY_CODE = {
    HX: 'huaxia',
    CX: 'chaoxian',
    RB: 'japan',
    DNY: 'sea',
    ZY: 'centralasia',
    BY: 'northasia',
    NY: 'southasia',
    XY: 'westasia',
    NO: 'southeu',
    DO: 'easteu',
    XO: 'westeu',
    BO: 'northeu',
    BF: 'northafrica',
    XF: 'westafrica',
    DF: 'eastafrica',
    ZM: 'centralamerica',
    BM: 'northamerica',
    NM: 'southamerica',
};
exports.CIV_CODE_BY_SLUG = Object.fromEntries(Object.entries(exports.CIV_SLUG_BY_CODE).map(([code, slug]) => [slug, code]));
/** overview 热区 id 与 matrix CIV_TABS slug 对齐 */
exports.OVERVIEW_SPOT_TO_MATRIX_SLUG = {
    huaxia: 'huaxia',
    chaoxian: 'chaoxian',
    japan: 'japan',
    sea: 'sea',
    india: 'southasia',
    persia: 'westasia',
    egypt: 'northafrica',
    eeu: 'easteu',
    medi: 'southeu',
    weu: 'westeu',
    wafrica: 'westafrica',
    camer: 'centralamerica',
    andes: 'southamerica',
};
exports.OVERVIEW_CIV_SPOTS = [
    { id: 'huaxia', name: '华夏', color: '#C42828', img: (0, civ_tab_images_1.civTabImage)('huaxia'), x: 68, y: 35 },
    { id: 'chaoxian', name: '朝鲜', color: '#5B8DEF', img: (0, civ_tab_images_1.civTabImage)('chaoxian'), x: 73, y: 28 },
    { id: 'japan', name: '日本', color: '#E88FB5', img: (0, civ_tab_images_1.civTabImage)('japan'), x: 78, y: 30 },
    { id: 'sea', name: '东南亚', color: '#5D8D8A', img: (0, civ_tab_images_1.civTabImage)('sea'), x: 70, y: 48 },
    { id: 'india', name: '南亚', color: '#E88B3F', img: (0, civ_tab_images_1.civTabImage)('southasia'), x: 56, y: 42 },
    { id: 'persia', name: '西亚', color: '#B87A3A', img: (0, civ_tab_images_1.civTabImage)('westasia'), x: 46, y: 36 },
    { id: 'egypt', name: '北非', color: '#D6A84A', img: (0, civ_tab_images_1.civTabImage)('northafrica'), x: 36, y: 38 },
    { id: 'eeu', name: '东欧', color: '#8974B8', img: (0, civ_tab_images_1.civTabImage)('easteu'), x: 32, y: 25 },
    { id: 'medi', name: '南欧', color: '#4A80D0', img: (0, civ_tab_images_1.civTabImage)('southeu'), x: 28, y: 30 },
    { id: 'weu', name: '西欧', color: '#7F96B8', img: (0, civ_tab_images_1.civTabImage)('westeu'), x: 22, y: 26 },
    { id: 'wafrica', name: '西非', color: '#B55E3F', img: (0, civ_tab_images_1.civTabImage)('westafrica'), x: 26, y: 52 },
    { id: 'camer', name: '中美', color: '#D16848', img: (0, civ_tab_images_1.civTabImage)('centralamerica'), x: 10, y: 45 },
    { id: 'andes', name: '南美', color: '#A27548', img: (0, civ_tab_images_1.civTabImage)('southamerica'), x: 12, y: 65 },
];
function buildDynastyUnitMap(cells) {
    const map = {};
    for (const c of cells || []) {
        const card = c.unitCard;
        if (!(card === null || card === void 0 ? void 0 : card.unitId) || !card.title)
            continue;
        map[card.title] = card.unitId;
        map[card.unitId] = card.unitId;
    }
    return map;
}
exports.buildDynastyUnitMap = buildDynastyUnitMap;
function resolveUnitId(dynastyKey, map) {
    const k = String(dynastyKey || '').trim();
    if (!k)
        return '';
    if (map[k])
        return map[k];
    const fallback = DYNASTY_UNIT_FALLBACK[k];
    if (fallback)
        return fallback;
    for (const [title, id] of Object.entries(map)) {
        if (title.includes(k) || k.includes(title))
            return id;
    }
    return '';
}
exports.resolveUnitId = resolveUnitId;
/** 首页矩阵内部占位 ID，不能作为详情页 unitId */
const SYNTHETIC_MATRIX_ID = /^(collapsed_|merged_)/;
/** 本地矩阵条目缺少 dynastyId 时的朝代详情兜底 */
const DYNASTY_UNIT_FALLBACK = {
    五帝: 'CD_HX_WUDI',
    夏: 'CD_HX_XIA',
    商: 'CD_HX_SHANG',
    西周: 'CD_HX_XIZHOU',
    春秋: 'CD_HX_CHUNQIU',
    战国: 'CD_HX_ZHANGUO',
    春秋战国: 'CD_HX_CHUNQIU',
    秦: 'CD_HX_QIN',
    'HX-CQ': 'CD_HX_CHUNQIU',
    'HX-ZG': 'CD_HX_ZHANGUO',
};
function isNavigableUnitId(id) {
    const v = String(id || '').trim();
    if (!v || SYNTHETIC_MATRIX_ID.test(v))
        return false;
    return true;
}
/** 朝代详情页 API 候选 ID（按优先级去重） */
function resolveDetailUnitIds(unitId, dynastyHint) {
    const seen = new Set();
    const out = [];
    const push = (id) => {
        const v = String(id || '').trim();
        if (!isNavigableUnitId(v) || seen.has(v))
            return;
        seen.add(v);
        out.push(v);
    };
    push(unitId);
    push(DYNASTY_UNIT_FALLBACK[dynastyHint]);
    push(resolveUnitId(dynastyHint, {}));
    return out;
}
exports.resolveDetailUnitIds = resolveDetailUnitIds;
/** 首页矩阵卡片 → 详情页 unitId（朝代详情优先 CD_* / dynastyId） */
function resolveNavigationUnitId(opts, map) {
    const entityType = String(opts.entityType || '').trim();
    const dynastyId = String(opts.dynastyId || '').trim();
    const entityId = String(opts.entityId || '').trim();
    const legacyId = String(opts.legacyId || '').trim();
    const person = String(opts.person || '').trim();
    const dynasty = String(opts.dynasty || opts.displayName || '').trim();
    const seen = new Set();
    const candidates = [];
    function push(id) {
        const v = String(id || '').trim();
        if (!isNavigableUnitId(v) || seen.has(v))
            return;
        seen.add(v);
        candidates.push(v);
    }
    push(dynastyId);
    push(DYNASTY_UNIT_FALLBACK[dynasty]);
    push(DYNASTY_UNIT_FALLBACK[legacyId]);
    push(resolveUnitId(dynasty, map));
    if (entityType === 'emperor') {
        push(entityId);
        push(legacyId);
        push(resolveUnitId(person, map));
    }
    else {
        push(entityId);
        push(legacyId);
        if (person)
            push(resolveUnitId(person, map));
    }
    const dynastyCandidate = candidates.find((id) => id.startsWith('CD_'));
    return dynastyCandidate || candidates[0] || '';
}
exports.resolveNavigationUnitId = resolveNavigationUnitId;
