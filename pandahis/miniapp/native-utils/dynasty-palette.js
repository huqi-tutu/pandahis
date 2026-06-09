"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ERA_BAR_SEGMENTS = exports.DYNASTY_CYCLE = void 0;
exports.getDynastyToneIndex = getDynastyToneIndex;
exports.getDynastyTone = getDynastyTone;
exports.resolveCardAccent = resolveCardAccent;
exports.enrichUnitCards = enrichUnitCards;

exports.DYNASTY_CYCLE = [
  { index: 0, color: '#84572F', border: '#84572F', activeBg: '#F0E8E0', barText: '#FFFFFF', badgeText: '#84572F' },
  { index: 1, color: '#F1A805', border: '#F1A805', activeBg: '#FFF5E0', barText: '#5A3A00', badgeText: '#F1A805' },
  { index: 2, color: '#F2D6A1', border: '#E0C088', activeBg: '#F5F0E0', barText: '#6B5E3A', badgeText: '#6B5E3A' },
  { index: 3, color: '#92ADA4', border: '#92ADA4', activeBg: '#EAF0EA', barText: '#3A4A3E', badgeText: '#3A4A3E' },
  { index: 4, color: '#B3D9E0', border: '#9ABCC8', activeBg: '#EDF4F8', barText: '#3A5A6A', badgeText: '#3A5A6A' },
  { index: 5, color: '#EDD5C0', border: '#D4B098', activeBg: '#F5EAE4', barText: '#6A4A3A', badgeText: '#6A4A3A' },
];

exports.ERA_BAR_SEGMENTS = [
  { label: '先秦', bg: '#84572F', textColor: '#FFFFFF', flex: 1.5 },
  { label: '秦汉', bg: '#F1A805', textColor: '#5A3A00', flex: 1 },
  { label: '三国', bg: '#F2D6A1', textColor: '#6B5E3A', flex: 1 },
  { label: '魏晋', bg: '#92ADA4', textColor: '#3A4A3E', flex: 0.8 },
  { label: '隋唐', bg: '#B3D9E0', textColor: '#3A5A6A', flex: 1.2 },
  { label: '宋', bg: '#EDD5C0', textColor: '#6A4A3A', flex: 0.7 },
  { label: '元', bg: '#84572F', textColor: '#FFFFFF', flex: 0.5 },
  { label: '明', bg: '#F1A805', textColor: '#5A3A00', flex: 0.5 },
  { label: '清', bg: '#F2D6A1', textColor: '#6B5E3A', flex: 0.6 },
];

const ERA_RULES = [
  { index: 1, patterns: ['秦汉', '秦', '汉', '西汉', '东汉', '清', '清朝', '清代'] },
  { index: 2, patterns: ['三国', '魏晋', '南北朝', '魏', '蜀', '吴', '晋', '东晋', '西晋', '南朝', '北朝'] },
  { index: 3, patterns: ['隋', '唐', '五代', '隋唐', '武周', '后梁', '后唐', '后晋', '后汉', '后周'] },
  { index: 4, patterns: ['宋', '北宋', '南宋', '辽', '金', '西夏'] },
  { index: 5, patterns: ['元', '蒙古', '元朝'] },
  { index: 0, patterns: ['先秦', '夏', '商', '周', '春秋', '战国', '明', '明朝', '明代'] },
];

function getDynastyToneIndex(note, era) {
  const raw = `${note || ''} ${era || ''}`.trim();
  if (!raw) return 0;
  for (const rule of ERA_RULES) {
    for (const p of rule.patterns) {
      if (raw.includes(p)) return rule.index;
    }
  }
  return 0;
}

function getDynastyTone(note, era) {
  const index = getDynastyToneIndex(note, era);
  return exports.DYNASTY_CYCLE[index] ?? exports.DYNASTY_CYCLE[0];
}

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

function enrichUnitCards(cards) {
  return cards.map((c) => {
    const eraFromMeta = c.meta?.split('·')[0]?.trim();
    const accent = resolveCardAccent(c.note, eraFromMeta);
    return Object.assign(Object.assign({}, c), accent, { accentHex: accent.accentHex });
  });
}
