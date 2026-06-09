/**
 * 矩阵色块 · 期间最重要大事（1–2 条，无则留空）
 * 键：帝王 id / 王朝 id / 王朝 name
 */
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

const BY_DYNASTY_ID = {
  'HX-X': ['大禹治水'],
  'HX-S': ['甲骨文', '青铜文明'],
  'HX-Z': ['分封制', '礼乐文明'],
  'HX-Q': ['统一度量衡'],
  'HX-H': ['独尊儒术'],
  'HX-T': ['盛唐气象'],
  'HX-SG': ['三国鼎立'],
  'HX-JN': ['八王之乱'],
  'HX-NB': ['淝水之战'],
  'HX-SU': ['大运河'],
  'HX-L': ['燕云十六州'],
  'HX-XX': ['创制西夏文'],
  'HX-J': ['靖康之变'],
  'HX-Y': ['元大都'],
  'HX-M': ['郑和下西洋'],
  'HX-Q': ['康乾盛世'],
}

const BY_DYNASTY_NAME = {
  战国:   ['商鞅变法', '长平之战'],
  十六国: ['五胡乱华'],
  南北朝: ['北魏孝文帝改革'],
  五代十国: ['儿皇帝'],
  南明:   ['抗清'],
}

function parseTagList(tag) {
  if (!tag || tag === '-') return []
  return String(tag)
    .split(/[,，]/)
    .map(s => s.trim())
    .filter(Boolean)
    .slice(0, 2)
}

function getMatrixHighlights(entry) {
  if (!entry) return []
  if (entry.isEmperor) {
    if (NO_HIGHLIGHT_EMPEROR_IDS.has(entry.id)) return []
    const curated = BY_EMPEROR_ID[entry.id]
    if (curated && curated.length) return curated
    if (HIDE_EMPEROR_TAG_FIELD_IDS.has(entry.id)) return []
    return parseTagList(entry.tag)
  }
  return BY_DYNASTY_ID[entry.id] || BY_DYNASTY_NAME[entry.dynastyName] || BY_DYNASTY_NAME[entry.displayName] || []
}

module.exports = { getMatrixHighlights }
