"use strict";
/** 历史图谱 · 朝代色板（视觉规范 v2.0） */
Object.defineProperty(exports, "__esModule", { value: true });
exports.enrichUnitCards = exports.resolveCardAccent = exports.getDynastyTone = exports.getDynastyToneIndex = exports.ERA_BAR_SEGMENTS = exports.DYNASTY_CYCLE = void 0;
exports.DYNASTY_CYCLE = [
    { index: 0, color: '#A2734F', border: '#A2734F', activeBg: '#ECE4DB', barText: '#FFFFFF', badgeText: '#7B573C' },
    { index: 1, color: '#63899C', border: '#63899C', activeBg: '#E3E7E6', barText: '#FFFFFF', badgeText: '#4B6877' },
    { index: 2, color: '#B99D5B', border: '#B99D5B', activeBg: '#EFEADD', barText: '#FFFFFF', badgeText: '#8D7745' },
    { index: 3, color: '#9A798F', border: '#9A798F', activeBg: '#EBE4E4', barText: '#FFFFFF', badgeText: '#755C6D' },
    { index: 4, color: '#7D8A6A', border: '#7D8A6A', activeBg: '#E7E7DF', barText: '#FFFFFF', badgeText: '#5F6951' },
    { index: 5, color: '#A46A65', border: '#A46A65', activeBg: '#ECE2DE', barText: '#FFFFFF', badgeText: '#7D514D' },
];
/** 规范 §3.3 年代条 9 段 */
exports.ERA_BAR_SEGMENTS = [
    { label: '先秦', bg: '#A2734F', textColor: '#FFFFFF', flex: 1.5 },
    { label: '秦汉', bg: '#63899C', textColor: '#FFFFFF', flex: 1 },
    { label: '三国', bg: '#B99D5B', textColor: '#FFFFFF', flex: 1 },
    { label: '魏晋', bg: '#9A798F', textColor: '#FFFFFF', flex: 0.8 },
    { label: '隋唐', bg: '#7D8A6A', textColor: '#FFFFFF', flex: 1.2 },
    { label: '宋', bg: '#A46A65', textColor: '#FFFFFF', flex: 0.7 },
    { label: '元', bg: '#A2734F', textColor: '#FFFFFF', flex: 0.5 },
    { label: '明', bg: '#63899C', textColor: '#FFFFFF', flex: 0.5 },
    { label: '清', bg: '#B99D5B', textColor: '#FFFFFF', flex: 0.6 },
];
const ERA_RULES = [
    { index: 1, patterns: ['秦汉', '秦', '汉', '西汉', '东汉', '清', '清朝', '清代'] },
    {
        index: 2,
        patterns: ['三国', '魏晋', '南北朝', '魏', '蜀', '吴', '晋', '东晋', '西晋', '南朝', '北朝'],
    },
    { index: 3, patterns: ['隋', '唐', '五代', '隋唐', '武周', '后梁', '后唐', '后晋', '后汉', '后周'] },
    { index: 4, patterns: ['宋', '北宋', '南宋', '辽', '金', '西夏'] },
    { index: 5, patterns: ['元', '蒙古', '元朝'] },
    { index: 0, patterns: ['先秦', '夏', '商', '周', '春秋', '战国', '明', '明朝', '明代'] },
];
/** 按朝代名 / 时代名映射到 c1–c6（0–5） */
function getDynastyToneIndex(note, era) {
    const raw = `${note || ''} ${era || ''}`.trim();
    if (!raw)
        return 0;
    for (const rule of ERA_RULES) {
        for (const p of rule.patterns) {
            if (raw.includes(p))
                return rule.index;
        }
    }
    return 0;
}
exports.getDynastyToneIndex = getDynastyToneIndex;
function getDynastyTone(note, era) {
    var _a;
    const index = getDynastyToneIndex(note, era);
    return (_a = exports.DYNASTY_CYCLE[index]) !== null && _a !== void 0 ? _a : exports.DYNASTY_CYCLE[0];
}
exports.getDynastyTone = getDynastyTone;
function resolveCardAccent(note, era) {
    const tone = getDynastyTone(note, era);
    return {
        toneIndex: tone.index,
        accentHex: tone.color,
        borderHex: tone.border,
        activeBgHex: tone.activeBg,
        badgeTextHex: tone.badgeText,
    };
}
exports.resolveCardAccent = resolveCardAccent;
/** 为卡片列表附加 tone 字段（就地扩展） */
function enrichUnitCards(cards) {
    return cards.map((c) => {
        var _a, _b;
        const eraFromMeta = (_b = (_a = c.meta) === null || _a === void 0 ? void 0 : _a.split('·')[0]) === null || _b === void 0 ? void 0 : _b.trim();
        const accent = resolveCardAccent(c.note, eraFromMeta);
        return { ...c, ...accent, accentHex: accent.accentHex };
    });
}
exports.enrichUnitCards = enrichUnitCards;
