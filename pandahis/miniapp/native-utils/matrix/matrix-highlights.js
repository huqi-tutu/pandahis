/**
 * 矩阵色块 · 期间最重要大事
 * 帝王：字符串列表（1–2 条，关键词分级配色）
 * 朝代：{ text, priority, category } 列表（最多 3 条，按 P0→P1→P2→P3 展示）
 */

/** 朝代标签五类（统一分类体系） */
const TAG_CATEGORIES = [
  '立国治世',
  '制度变革',
  '战争动荡',
  '文化学术',
  '交流融合',
]

const BY_EMPEROR_ID = {
  zhong_hua_wu_di_huang_di:     ['炎黄之战'],
  zhong_hua_wu_di_yao:          ['禅让舜'],
  zhong_hua_xia_yu:             ['治水', '铸九鼎'],
  zhong_hua_shang_tang:         ['鸣条之战', '推翻夏朝'],
  zhong_hua_shang_wu_ding:      ['妇好征伐'],
  zhong_hua_zhou_wu_wang:       ['牧野之战', '武王伐纣'],
  zhong_hua_zhou_cheng_wang:    ['周公东征'],
  zhong_hua_qin_ying_zheng:     ['统一六国', '称始皇帝'],
  zhong_hua_han_gao_zu:         ['楚汉战争', '建立汉朝'],
  zhong_hua_han_wu_di:          ['北击匈奴', '丝绸之路'],
  zhong_hua_xin_wang_mang:      ['王莽篡汉'],
  zhong_hua_han_guang_wu:       ['光武中兴'],
  zhong_hua_shu_liu_bei:        ['赤壁联盟', '白帝城托孤'],
  zhong_hua_wu_sun_quan:        ['赤壁之战', '夷陵之战'],
  zhong_hua_jin_wu_di:          ['灭吴统一'],
  zhong_hua_sui_wen_di:         ['开皇之治'],
  zhong_hua_sui_yang_di:        ['开凿大运河', '三征高句丽'],
  zhong_hua_tang_li_shi_min:    ['玄武门之变', '贞观之治'],
  zhong_hua_tang_li_long_ji:    ['开元盛世'],
  zhong_hua_tang_li_yu:         ['安史之乱'],
  zhong_hua_song_zhao_kuang_yin: ['陈桥兵变', '杯酒释兵权'],
  zhong_hua_song_zhao_kuang:     ['靖康之变'],
  zhong_hua_song_zhao_gou:       ['建炎南渡'],
  zhong_hua_song_lizong:         ['联蒙灭金'],
  zhong_hua_yuan_hu_lie:        ['建立元朝', '灭南宋'],
  zhong_hua_ming_zhu_yuan_zhang: ['推翻元朝', '定都南京'],
  zhong_hua_ming_zhu_di:        ['迁都北京', '郑和下西洋'],
  zhong_hua_ming_zhu_qi_zhen:   ['土木堡之变'],
  zhong_hua_qing_nurhaci:       ['建立后金'],
  zhong_hua_qing_xuan_ye:       ['平定三藩', '收复台湾'],
  zhong_hua_qing_hong_li:       ['十全武功'],
  zhong_hua_qing_xian_feng:     ['太平天国', '第二次鸦片战争'],
}

/** 明确不展示标签（覆盖帝王表 tag） */
const NO_HIGHLIGHT_EMPEROR_IDS = new Set([
  'zhong_hua_jin_wanyan_wanyan', // 金海陵王
])

/** 不展示帝王表「标签」字段（仍展示 BY_EMPEROR_ID 期间大事） */
const HIDE_EMPEROR_TAG_FIELD_IDS = new Set([
  'zhong_hua_jin_si_ma_de_wen', // 晋恭帝
])

/** 朝代卡片标签：priority = P0 | P1 | P2 | P3；category 见 TAG_CATEGORIES */
const BY_DYNASTY_NAME = {
  五帝: [
    { text: '禅让制', priority: 'P0', category: '立国治世' },
    { text: '华夏始祖', priority: 'P0', category: '立国治世' },
  ],
  夏: [
    { text: '家天下', priority: 'P0', category: '立国治世' },
    { text: '二里头', priority: 'P1', category: '文化学术' },
  ],
  商: [
    { text: '甲骨文', priority: 'P0', category: '文化学术' },
    { text: '青铜器', priority: 'P0', category: '文化学术' },
    { text: '殷墟', priority: 'P1', category: '文化学术' },
  ],
  西周: [
    { text: '分封制', priority: 'P0', category: '制度变革' },
    { text: '制礼作乐', priority: 'P0', category: '文化学术' },
    { text: '井田制', priority: 'P1', category: '制度变革' },
  ],
  春秋: [
    { text: '诸侯争霸', priority: 'P0', category: '战争动荡' },
    { text: '诸子萌芽', priority: 'P2', category: '文化学术' },
  ],
  战国: [
    { text: '百家争鸣', priority: 'P0', category: '文化学术' },
    { text: '列国变法', priority: 'P1', category: '制度变革' },
  ],
  秦: [
    { text: '天下一统', priority: 'P0', category: '立国治世' },
    { text: '郡县制', priority: 'P0', category: '制度变革' },
    { text: '书同文', priority: 'P1', category: '制度变革' },
  ],
  楚汉: [
    { text: '楚汉争霸', priority: 'P0', category: '战争动荡' },
    { text: '大泽起义', priority: 'P1', category: '战争动荡' },
  ],
  西汉: [
    { text: '独尊儒术', priority: 'P0', category: '文化学术' },
    { text: '开辟丝路', priority: 'P0', category: '交流融合' },
    { text: '汉匈征战', priority: 'P1', category: '战争动荡' },
  ],
  东汉: [
    { text: '蔡伦造纸', priority: 'P0', category: '文化学术' },
    { text: '光武中兴', priority: 'P1', category: '立国治世' },
  ],
  三国: [
    { text: '赤壁之战', priority: 'P0', category: '战争动荡' },
    { text: '建安文学', priority: 'P1', category: '文化学术' },
  ],
  西晋: [
    { text: '八王之乱', priority: 'P0', category: '战争动荡' },
  ],
  东晋: [
    { text: '衣冠南渡', priority: 'P0', category: '交流融合' },
    { text: '玄学盛行', priority: 'P2', category: '文化学术' },
  ],
  南北朝: [
    { text: '民族大融合', priority: 'P0', category: '交流融合' },
    { text: '佛教兴盛', priority: 'P1', category: '文化学术' },
  ],
  隋: [
    { text: '创立科举', priority: 'P0', category: '制度变革' },
    { text: '开凿运河', priority: 'P0', category: '制度变革' },
  ],
  唐: [
    { text: '贞观之治', priority: 'P0', category: '立国治世' },
    { text: '唐诗鼎盛', priority: 'P0', category: '文化学术' },
    { text: '万国来朝', priority: 'P1', category: '立国治世' },
  ],
  五代十国: [
    { text: '藩镇割据', priority: 'P0', category: '战争动荡' },
  ],
  辽: [
    { text: '辽宋并峙', priority: 'P0', category: '战争动荡' },
    { text: '南北面官', priority: 'P1', category: '制度变革' },
  ],
  北宋: [
    { text: '重文轻武', priority: 'P0', category: '制度变革' },
    { text: '宋词繁荣', priority: 'P0', category: '文化学术' },
    { text: '活字印刷', priority: 'P1', category: '文化学术' },
  ],
  金: [
    { text: '猛安谋克', priority: 'P0', category: '制度变革' },
    { text: '宋金对峙', priority: 'P1', category: '战争动荡' },
  ],
  南宋: [
    { text: '理学大成', priority: 'P0', category: '文化学术' },
    { text: '海上贸易', priority: 'P0', category: '交流融合' },
    { text: '崖山蹈海', priority: 'P1', category: '战争动荡' },
  ],
  元: [
    { text: '行省制度', priority: 'P0', category: '制度变革' },
    { text: '四等人制', priority: 'P1', category: '制度变革' },
  ],
  明: [
    { text: '郑和下西洋', priority: 'P0', category: '交流融合' },
    { text: '废丞相制', priority: 'P0', category: '制度变革' },
    { text: '八股取士', priority: 'P1', category: '制度变革' },
  ],
  清: [
    { text: '康乾盛世', priority: 'P0', category: '立国治世' },
    { text: '鸦片战争', priority: 'P0', category: '战争动荡' },
    { text: '闭关锁国', priority: 'P1', category: '制度变革' },
  ],
}

/** legacyId / entry.id 别名 → 与 BY_DYNASTY_NAME 同结构 */
const BY_DYNASTY_ID = {
  'HX-SHWD': BY_DYNASTY_NAME['五帝'],
  'HX-X': BY_DYNASTY_NAME['夏'],
  'HX-S': BY_DYNASTY_NAME['商'],
  'HX-XZ': BY_DYNASTY_NAME['西周'],
  'HX-Z': BY_DYNASTY_NAME['西周'],
  'HX-CQ': BY_DYNASTY_NAME['春秋'],
  'HX-ZG': BY_DYNASTY_NAME['战国'],
  'HX-Q': BY_DYNASTY_NAME['秦'],
  'HX-QMH': BY_DYNASTY_NAME['楚汉'],
  'HX-XH': BY_DYNASTY_NAME['西汉'],
  'HX-H': BY_DYNASTY_NAME['西汉'],
  'HX-DH': BY_DYNASTY_NAME['东汉'],
  'collapsed_三国': BY_DYNASTY_NAME['三国'],
  'HX-SG': BY_DYNASTY_NAME['三国'],
  'HX-XJ': BY_DYNASTY_NAME['西晋'],
  'HX-DJ': BY_DYNASTY_NAME['东晋'],
  'HX-S-1': BY_DYNASTY_NAME['隋'],
  'HX-SU': BY_DYNASTY_NAME['隋'],
  'HX-T': BY_DYNASTY_NAME['唐'],
  'HX-BS': BY_DYNASTY_NAME['北宋'],
  'HX-NS': BY_DYNASTY_NAME['南宋'],
  'HX-L': BY_DYNASTY_NAME['辽'],
  'HX-J': BY_DYNASTY_NAME['金'],
  'ZQ_HX_JIN_JIN': BY_DYNASTY_NAME['金'],
  'HX-Y': BY_DYNASTY_NAME['元'],
  'HX-M': BY_DYNASTY_NAME['明'],
  'HX-Q-1': BY_DYNASTY_NAME['清'],
}

function parseTagList(tag) {
  if (!tag || tag === '-') return []
  return String(tag)
    .split(/[,，]/)
    .map(s => s.trim())
    .filter(Boolean)
    .slice(0, 2)
}

function idInSet(id, legacyId, set) {
  if (!id) return false
  if (set.has(id)) return true
  if (legacyId && set.has(legacyId)) return true
  return false
}

function resolveDynastyHighlights(entry) {
  return BY_DYNASTY_ID[entry.id]
    || (entry.legacyId ? BY_DYNASTY_ID[entry.legacyId] : null)
    || BY_DYNASTY_NAME[entry.dynastyName]
    || BY_DYNASTY_NAME[entry.displayName]
    || []
}

function getMatrixHighlights(entry) {
  if (!entry) return []
  if (entry.isEmperor) {
    if (idInSet(entry.id, entry.legacyId, NO_HIGHLIGHT_EMPEROR_IDS)) return []
    const curated = BY_EMPEROR_ID[entry.id]
      || (entry.legacyId ? BY_EMPEROR_ID[entry.legacyId] : null)
    if (curated && curated.length) return curated
    if (idInSet(entry.id, entry.legacyId, HIDE_EMPEROR_TAG_FIELD_IDS)) return []
    return parseTagList(entry.tag)
  }
  return resolveDynastyHighlights(entry)
}

const TAG_TIER_STYLE = {
  1: 'background-color:#4A3F3F;color:#FDFCFA;border:none;',
  2: 'background-color:#8C817B;color:#FFFFFF;border:none;',
  3: 'background-color:#ECE8E3;color:#5F5854;border:none;',
}

/** 与首页六色轮巡一致，用于 Icon 文件名后缀 */
const TAG_THEME_HEX = ['A2734F', '63899C', 'B99D5B', '9A798F', '7D8A6A', 'A46A65']

/** 首页标签 Icon（COS；与文明 Tab 同域名，改代码即生效，无需发版后端） */
const TAG_ICON_BASE =
  'https://pandahis-1300045339.cos.ap-chengdu.myqcloud.com/histomap/home-tag-icon/'
const TAG_ICON_CACHE_VER = '2026080624'

/** 分类 → 偏白胶囊底（Icon 尺寸与文字统一，见 TAG_ICON_*） */
const TAG_CATEGORY_STYLE = {
  立国治世: { bg: '#FAF8F5', text: '#6E5C4A' },
  制度变革: { bg: '#F7F8FA', text: '#4F5F6E' },
  战争动荡: { bg: '#FAF7F5', text: '#7A5648' },
  文化学术: { bg: '#F5F9F7', text: '#2A6650' },
  交流融合: { bg: '#F5F8F9', text: '#4A7579' },
}

/** 与 .entry-tag-text 字号一致；宽度略留余量容纳最宽 Icon（文化学术 ≈1.18） */
const TAG_ICON_HEIGHT_RPX = 15
const TAG_ICON_WIDTH_RPX = 18

/** 主题色 → 文字色（与 Icon 同色系，避免 Icon / 文字脱节） */
const TAG_THEME_TEXT = {
  A2734F: '#7A5538',
  '63899C': '#4F6775',
  B99D5B: '#8A7340',
  '9A798F': '#6E5768',
  '7D8A6A': '#5A6349',
  A46A65: '#865651',
}

const TAG_PRIORITY_META = {
  P0: { fontWeight: 600, pillOpacity: 1 },
  P1: { fontWeight: 500, pillOpacity: 0.9 },
  P2: { fontWeight: 400, pillOpacity: 0.78 },
  P3: { fontWeight: 400, pillOpacity: 0.78 },
}

function resolveTagIconSrc(category, themeIndex) {
  if (!category || !TAG_CATEGORY_STYLE[category]) return ''
  const hex = TAG_THEME_HEX[(themeIndex || 0) % TAG_THEME_HEX.length]
  // 中文文件名需 encode，否则真机部分环境加载失败
  const file = `${encodeURIComponent(category)}_${hex}.png`
  return `${TAG_ICON_BASE}${file}?v=${TAG_ICON_CACHE_VER}`
}

function buildDynastyTagVisual(item, themeIndex) {
  const priority = item.priority || 'P2'
  const meta = TAG_PRIORITY_META[priority] || TAG_PRIORITY_META.P2
  const category = item.category || ''
  const catStyle = TAG_CATEGORY_STYLE[category] || TAG_CATEGORY_STYLE['文化学术']
  const themeHex = TAG_THEME_HEX[(themeIndex || 0) % TAG_THEME_HEX.length]
  const textColor = TAG_THEME_TEXT[themeHex] || catStyle.text
  return {
    text: item.text,
    category,
    iconSrc: resolveTagIconSrc(category, themeIndex),
    iconStyle: `width:${TAG_ICON_WIDTH_RPX}rpx;height:${TAG_ICON_HEIGHT_RPX}rpx;`,
    textStyle: `font-weight:${meta.fontWeight};color:${textColor};`,
    tagStyle: `background-color:${catStyle.bg};color:${textColor};opacity:${meta.pillOpacity};border:none;`,
    tagClass: 'entry-tag--v2',
  }
}
const DYNASTY_PRIORITY_ORDER = { P0: 0, P1: 1, P2: 2, P3: 3 }
const TAG_TIER1_KEYWORDS = ['开国', '中兴', '统一', '一统', '亡国', '篡', '摄政']
const TAG_TIER2_KEYWORDS = ['明君', '暴君', '贤君', '昏君']
const TAG_TIER3_KEYWORDS = ['被废', '禅让', '战死', '迁都', '被杀', '被俘']

function dynastyPriorityToTier(priority) {
  if (priority === 'P0') return 1
  if (priority === 'P1') return 2
  return 3
}

function classifyEmperorTagTier(text) {
  const s = String(text || '')
  if (TAG_TIER1_KEYWORDS.some(k => s.includes(k))) return 1
  if (TAG_TIER2_KEYWORDS.some(k => s.includes(k))) return 2
  if (TAG_TIER3_KEYWORDS.some(k => s.includes(k))) return 3
  return 3
}

function isDynastyHighlightTag(item) {
  return item && typeof item === 'object' && typeof item.text === 'string'
}

/** 胶囊标签：朝代最多 3 条（按 P0→P1→P2→P3），帝王最多 2 条（关键词分级） */
function buildHighlightTagList(labels, context) {
  const list = (labels || []).filter(Boolean)
  if (!list.length) return []

  if (isDynastyHighlightTag(list[0])) {
    const themeIndex = context?.themeIndex != null ? context.themeIndex : 0
    return list
      .slice()
      .sort((a, b) =>
        (DYNASTY_PRIORITY_ORDER[a.priority] ?? 9) - (DYNASTY_PRIORITY_ORDER[b.priority] ?? 9)
      )
      .slice(0, 3)
      .map(item => buildDynastyTagVisual(item, themeIndex))
  }

  return list.slice(0, 2).map(text => ({
    text,
    category: '',
    tagStyle: TAG_TIER_STYLE[classifyEmperorTagTier(text)],
  }))
}

module.exports = {
  getMatrixHighlights,
  buildHighlightTagList,
  BY_DYNASTY_NAME,
  TAG_CATEGORIES,
}
