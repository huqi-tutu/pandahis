/**
 * 历史图谱 · 朝代详情 Mock 数据
 *
 * 泳道排布原则：
 *   - 每条泳道有一组平铺的 bars（无须手动分行）
 *   - buildSwimData 调用 packBars 自动按贪心区间调度分行，保证同行无重叠
 *   - 每条泳道最多显示 MAX_VISIBLE 条，超出部分折叠
 *   - 类目：君纪、士臣、典制、事略、民录、著作、思想
 */

const MAX_VISIBLE = 10   // 每条泳道最多展示条数（士臣泳道全量展示）
const SHICHEN_LABEL = '士臣'

// 泳道类型标记：连续型(true)有时间线，孤立型(false)纯胶囊
// 连续型：君纪、士臣、典制、事略（有明确起止时间）
// 孤立型：民录、著作、思想（概念性/时间点事件）
const LANE_CONTINUOUS = {
  '君纪': true,
  '士臣': true,
  '典制': true,
  '事略': true,
  '民录': false,
  '著作': false,
  '思想': false,
}

// 优先级映射：type → 优先级等级（P0最高，P3最低）
// P0/P1: 100% 不透明 | P2: 75% | P3: 50%
const TYPE_TO_PRIORITY = {
  'accent':  'p0',   // 重要事件/人物 → P0 全显
  'marker':  'p1',   // 可跳转详情   → P1 全显
  '':        'p2',   // 普通条目     → P2 75%
  'narrow':  'p2',   // 短事件       → P2 75%
  'ghost':   'p3',   // 背景性/淡   → P3 50%
}

/** 时间轴刻度：公元前用 -XX，比 BCE/前 更省宽 */
function fmtAxisYear(y) {
  if (y < 0) return `-${Math.abs(y)}`
  return String(y)
}

/* ═══════════════════════════════════════════════════
   全球文明朝代数据库（用于并发政权计算）
   两个时段重叠条件：d.start < endYear AND d.end > startYear
═══════════════════════════════════════════════════ */
const WORLD_DYNASTIES = [
  // ── 华夏 ──
  { civ: '华夏', title: '五帝',     start: -2698, end: -2205 },
  { civ: '华夏', title: '夏',       start: -2070, end: -1600 },
  { civ: '华夏', title: '商',       start: -1600, end: -1046 },
  { civ: '华夏', title: '西周',     start: -1046, end: -771  },
  { civ: '华夏', title: '春秋',     start: -770,  end: -476  },
  { civ: '华夏', title: '战国',     start: -475,  end: -221  },
  { civ: '华夏', title: '秦',       start: -221,  end: -207  },
  { civ: '华夏', title: '西汉',     start: -202,  end: 8     },
  { civ: '华夏', title: '东汉',     start: 25,    end: 220   },
  { civ: '华夏', title: '唐',       start: 618,  end: 907  },
  { civ: '华夏', title: '五代',     start: 907,  end: 960  },
  { civ: '华夏', title: '北宋',     start: 960,  end: 1127 },
  { civ: '华夏', title: '南宋',     start: 1127, end: 1279 },
  { civ: '华夏', title: '元',       start: 1271, end: 1368 },
  { civ: '华夏', title: '明',       start: 1368, end: 1644 },
  { civ: '华夏', title: '清',       start: 1644, end: 1912 },
  // ── 辽/契丹 ──
  { civ: '辽',   title: '辽',       start: 907,  end: 1125 },
  { civ: '辽',   title: '西辽',     start: 1124, end: 1218 },
  // ── 金/女真 ──
  { civ: '金',   title: '金',       start: 1115, end: 1234 },
  // ── 西夏 ──
  { civ: '西夏', title: '西夏',     start: 1038, end: 1227 },
  // ── 大理 ──
  { civ: '大理', title: '大理',     start: 937,  end: 1253 },
  // ── 蒙古 ──
  { civ: '蒙古', title: '蒙古汗国', start: 1206, end: 1368 },
  // ── 吐蕃 ──
  { civ: '吐蕃', title: '吐蕃',     start: 618,  end: 842  },
  { civ: '吐蕃', title: '吐蕃诸部', start: 842,  end: 1247 },
  // ── 回鹘 ──
  { civ: '回鹘', title: '回鹘汗国', start: 744,  end: 840  },
  { civ: '回鹘', title: '甘州回鹘', start: 848,  end: 1036 },
  // ── 南诏 ──
  { civ: '南诏', title: '南诏',     start: 738,  end: 902  },
  // ── 渤海 ──
  { civ: '渤海', title: '渤海国',   start: 698,  end: 926  },
  // ── 高丽/朝鲜 ──
  { civ: '高丽', title: '新罗',     start: -57,  end: 935  },
  { civ: '高丽', title: '高丽',     start: 918,  end: 1392 },
  { civ: '朝鲜', title: '李氏朝鲜', start: 1392, end: 1897 },
  // ── 日本 ──
  { civ: '日本', title: '奈良时代', start: 710,  end: 794  },
  { civ: '日本', title: '平安时代', start: 794,  end: 1185 },
  { civ: '日本', title: '镰仓幕府', start: 1185, end: 1333 },
  { civ: '日本', title: '室町幕府', start: 1336, end: 1573 },
  { civ: '日本', title: '江户幕府', start: 1603, end: 1868 },
  { civ: '日本', title: '明治',     start: 1868, end: 1912 },
  // ── 越南 ──
  { civ: '越南', title: '丁朝',     start: 968,  end: 980  },
  { civ: '越南', title: '前黎朝',   start: 980,  end: 1009 },
  { civ: '越南', title: '李朝',     start: 1009, end: 1225 },
  { civ: '越南', title: '陈朝',     start: 1225, end: 1400 },
  { civ: '越南', title: '后黎朝',   start: 1428, end: 1789 },
  // ── 准噶尔 ──
  { civ: '准噶尔', title: '准噶尔汗国', start: 1634, end: 1755 },
  // ── 俄罗斯 ──
  { civ: '俄罗斯', title: '沙皇俄国',   start: 1547, end: 1917 },
  // ── 英国 ──
  { civ: '英国',   title: '大不列颠',   start: 1707, end: 2000 },
  // ── 阿拉伯 ──
  { civ: '阿拉伯', title: '阿拔斯王朝', start: 750,  end: 1258 },
  // ── 草原政权 ──
  { civ: '草原',   title: '北元',        start: 1368, end: 1635 },
  { civ: '草原',   title: '瓦剌',        start: 1388, end: 1634 },
]

function getConcurrentItems(selfCiv, selfTitle, startYear, endYear) {
  const overlapping = WORLD_DYNASTIES.filter(d =>
    d.start < endYear && d.end > startYear
  )
  const self   = overlapping.find(d => d.civ === selfCiv && d.title === selfTitle)
  const others = overlapping.filter(d => !(d.civ === selfCiv && d.title === selfTitle))
  return [self, ...others].filter(Boolean).map(d => `${d.civ}·${d.title}`)
}

/* ═══════════════════════════════════════════════════
   朝代数据库（每条泳道用 bars 平铺，不再手动分行）
═══════════════════════════════════════════════════ */
const DYNASTY_DB = {
  /* ════ 五帝 ════ */
  '五帝': {
    title: '五帝', civ: '华夏', range: '约前2698–前2205', startYear: -2698, endYear: -2205,
    capital: '有熊（传说）',
    intro: '五帝时代（约前2698—前2205）是华夏文明的起源期。黄帝统一各部落，奠定华夏族基础；颛顼、帝喾承续治理；尧舜以禅让传位，开创了"天下为公"的政治理想。这一时期的诸多创举——造字、制乐、作历、论医、养蚕——被视为中华文明的源头。',
    next: { title: '夏 · 阳城', dynasty: '夏' },
    lanes: [
      { label: '君纪', borderColor: '#F1A805', bars: [
        { title: '黄帝', start: -2698, end: -2598, type: 'accent', boxKey: 'box-detail', boxTitle: '黄帝' },
        { title: '颛顼', start: -2514, end: -2436, type: '' },
        { title: '帝喾', start: -2436, end: -2366, type: '' },
        { title: '尧',   start: -2356, end: -2255, type: 'accent' },
        { title: '舜',   start: -2255, end: -2205, type: 'accent' },
      ]},
      { label: '士臣', borderColor: '#E0C088', bars: [
        { title: '风后', birth: -2700, death: -2600, appearStart: -2680, appearEnd: -2610, type: '' },
        { title: '力牧', birth: -2700, death: -2600, appearStart: -2680, appearEnd: -2610, type: '' },
        { title: '仓颉', birth: -2700, death: -2600, appearStart: -2660, appearEnd: -2610, type: '' },
        { title: '伶伦', birth: -2690, death: -2600, appearStart: -2660, appearEnd: -2610, type: '' },
        { title: '大挠', birth: -2690, death: -2610, appearStart: -2660, appearEnd: -2620, type: '' },
        { title: '岐伯', birth: -2700, death: -2600, appearStart: -2670, appearEnd: -2610, type: '' },
        { title: '嫘祖', birth: -2700, death: -2610, appearStart: -2690, appearEnd: -2620, type: '' },
      ]},
      { label: '典制', borderColor: '#92ADA4', bars: [
        { title: '甲子干支', start: -2680, end: -2650, type: '' },
        { title: '十二律',   start: -2670, end: -2640, type: '' },
        { title: '禅让制',   start: -2360, end: -2205, type: 'accent' },
      ]},
      { label: '事略', borderColor: '#9ABCC8', bars: [
        { title: '阪泉之战', start: -2680, end: -2670, type: 'accent' },
        { title: '涿鹿之战', start: -2670, end: -2660, type: 'accent' },
        { title: '北逐荤粥', start: -2660, end: -2650, type: '' },
        { title: '尧舜禅让', start: -2260, end: -2250, type: 'marker' },
      ]},
      { label: '民录', borderColor: '#D4B098', bars: [
        { title: '部落融合', start: -2680, end: -2600, type: '' },
        { title: '农耕初兴', start: -2600, end: -2400, type: '' },
      ]},
      { label: '著作', borderColor: '#A894B8', bars: [
        { title: '黄帝内经', start: -2650, end: -2600, type: 'accent' },
        { title: '黄帝四经', start: -2600, end: -2550, type: 'ghost' },
      ]},
      { label: '思想', borderColor: '#7F9EB5', bars: [
        { title: '天人合一', start: -2680, end: -2500, type: '' },
        { title: '黄老之道', start: -2500, end: -2300, type: '' },
      ]},
    ]
  },

  /* ════ 北宋 ════ */
  '北宋': {
    title: '北宋', civ: '华夏', range: '960–1127', startYear: 960, endYear: 1127,
    capital: '汴京',
    intro: '北宋（960—1127）是华夏文治最盛的王朝之一，太祖陈桥兵变立国，历九帝一百六十七年，科举大兴、士大夫当政，经济与文化成就卓著，然积弱于边患，终因金兵南下、靖康之变而亡。',
    next: { title: '南宋 · 临安', dynasty: '南宋' },
    lanes: [
      { label: '君纪', borderColor: '#F1A805', bars: [
        { title: '太祖赵匡胤', start: 960,  end: 976,  type: ''       },
        { title: '太宗赵光义', start: 976,  end: 997,  type: ''       },
        { title: '真宗',       start: 997,  end: 1022, type: ''       },
        { title: '仁宗',       start: 1022, end: 1063, type: ''       },
        { title: '英宗',       start: 1063, end: 1067, type: ''       },
        { title: '神宗',       start: 1067, end: 1085, type: 'accent' },
        { title: '哲宗',       start: 1085, end: 1100, type: ''       },
        { title: '徽宗',       start: 1100, end: 1125, type: ''       },
        { title: '钦宗',       start: 1125, end: 1127, type: ''       },
      ]},
      { label: '士臣', borderColor: '#E0C088', bars: [
        { title: '晏殊',   birth: 991,  death: 1055, appearStart: 1020, appearEnd: 1048, type: ''       },
        { title: '范仲淹', birth: 989,  death: 1052, appearStart: 1040, appearEnd: 1052, type: ''       },
        { title: '包拯',   birth: 999,  death: 1062, appearStart: 1037, appearEnd: 1062, type: ''       },
        { title: '欧阳修', birth: 1007, death: 1072, appearStart: 1045, appearEnd: 1072, type: ''       },
        { title: '富弼',   birth: 1004, death: 1083, appearStart: 1042, appearEnd: 1065, type: ''       },
        { title: '韩琦',   birth: 1008, death: 1075, appearStart: 1042, appearEnd: 1075, type: ''       },
        { title: '司马光', birth: 1019, death: 1086, appearStart: 1068, appearEnd: 1086, type: ''       },
        { title: '王安石', birth: 1021, death: 1086, appearStart: 1069, appearEnd: 1086, type: 'accent' },
        { title: '沈括',   birth: 1031, death: 1095, appearStart: 1063, appearEnd: 1095, type: ''       },
        { title: '苏轼',   birth: 1037, death: 1101, appearStart: 1065, appearEnd: 1085, type: ''       },
        { title: '黄庭坚', birth: 1045, death: 1105, appearStart: 1070, appearEnd: 1094, type: ''       },
        { title: '秦观',   birth: 1049, death: 1100, appearStart: 1080, appearEnd: 1100, type: ''       },
        { title: '蔡京',   birth: 1047, death: 1126, appearStart: 1094, appearEnd: 1120, type: ''       },
      ]},
      { label: '典制', borderColor: '#92ADA4', bars: [
        { title: '青苗法',   start: 1069, end: 1085, type: ''      },
        { title: '募役法',   start: 1071, end: 1085, type: ''      },
        { title: '学制整理', start: 1080, end: 1110, type: 'ghost' },
      ]},
      { label: '事略', borderColor: '#9ABCC8', bars: [
        { title: '熙宁变法', start: 1069, end: 1085, type: 'accent' },
        { title: '乌台诗案', start: 1079, end: 1080, type: 'marker', boxKey: 'box-detail', boxTitle: '乌台诗案' },
        { title: '元丰改制', start: 1082, end: 1095, type: 'ghost'  },
        { title: '靖康之变', start: 1125, end: 1127, type: 'accent', boxKey: 'box-detail', boxTitle: '靖康之变' },
      ]},
      { label: '民录', borderColor: '#D4B098', bars: [
        { title: '赋役重压', start: 1079, end: 1124, type: ''       },
        { title: '方腊',     start: 1120, end: 1122, type: 'narrow' },
      ]},
      { label: '著作', borderColor: '#A894B8', bars: [
        { title: '资治通鉴', start: 1066, end: 1084, type: 'accent' },
        { title: '梦溪笔谈', start: 1088, end: 1095, type: ''       },
        { title: '营造法式', start: 1100, end: 1103, type: 'ghost'  },
      ]},
      { label: '思想', borderColor: '#7F9EB5', bars: [
        { title: '理学初兴', start: 1032, end: 1107, type: ''       },
        { title: '荆公新学', start: 1069, end: 1085, type: 'accent' },
      ]},
    ]
  },

  /* ════ 唐 ════ */
  '唐': {
    title: '唐', civ: '华夏', range: '618–907', startYear: 618, endYear: 907,
    capital: '长安',
    intro: '唐朝（618—907）是继隋之后的大一统王朝，共历二十一帝二百八十九年，贞观之治开创盛世，丝路贯通中西、文化多元包容，唐诗成就举世无双，然安史之乱后藩镇割据、宦官专权，终由黄巢起义动摇根基而亡。',
    next: { title: '五代 · 汴梁', dynasty: '五代' },
    lanes: [
      { label: '君纪', borderColor: '#F1A805', bars: [
        { title: '高祖', start: 618, end: 626, type: ''       },
        { title: '太宗', start: 626, end: 649, type: 'accent' },
        { title: '高宗', start: 649, end: 683, type: ''       },
        { title: '武周', start: 690, end: 705, type: ''       },
        { title: '玄宗', start: 712, end: 756, type: 'accent' },
        { title: '代宗', start: 762, end: 779, type: ''       },
        { title: '宪宗', start: 805, end: 820, type: ''       },
        { title: '宣宗', start: 846, end: 859, type: ''       },
      ]},
      { label: '士臣', borderColor: '#E0C088', bars: [
        { title: '房玄龄', birth: 579, death: 648, appearStart: 626, appearEnd: 648, type: '' },
        { title: '魏征',   birth: 580, death: 643, appearStart: 626, appearEnd: 643, type: '' },
        { title: '李白',   birth: 701, death: 762, appearStart: 742, appearEnd: 762, type: '' },
        { title: '杜甫',   birth: 712, death: 770, appearStart: 755, appearEnd: 770, type: '' },
        { title: '韩愈',   birth: 768, death: 824, appearStart: 802, appearEnd: 824, type: '' },
      ]},
      { label: '典制', borderColor: '#92ADA4', bars: [
        { title: '均田制',   start: 618, end: 780, type: ''       },
        { title: '科举完善', start: 622, end: 907, type: 'ghost'  },
        { title: '两税法',   start: 780, end: 907, type: 'accent' },
      ]},
      { label: '事略', borderColor: '#9ABCC8', bars: [
        { title: '玄武门之变', start: 626, end: 627, type: 'marker', boxKey: 'box-detail', boxTitle: '玄武门之变' },
        { title: '安史之乱',   start: 755, end: 763, type: 'accent' },
        { title: '甘露之变',   start: 835, end: 836, type: 'marker', boxKey: 'box-detail', boxTitle: '甘露之变' },
      ]},
      { label: '民录', borderColor: '#D4B098', bars: [
        { title: '贞观之治', start: 627, end: 649, type: '' },
        { title: '开元盛世', start: 713, end: 741, type: '' },
        { title: '黄巢起义', start: 875, end: 884, type: '' },
      ]},
      { label: '著作', borderColor: '#A894B8', bars: [
        { title: '通典',     start: 801, end: 804, type: 'accent' },
        { title: '唐诗总集', start: 730, end: 780, type: 'ghost'  },
      ]},
      { label: '思想', borderColor: '#7F9EB5', bars: [
        { title: '佛教鼎盛', start: 618, end: 845, type: ''       },
        { title: '儒释道汇融', start: 700, end: 907, type: 'accent' },
      ]},
    ]
  },

  /* ════ 清 ════ */
  '清': {
    title: '清', civ: '华夏', range: '1644–1912', startYear: 1644, endYear: 1912,
    capital: '北京',
    intro: '清朝（1644—1912）是中国最后一个封建王朝，共历十二帝二百六十八年，康乾盛世国力鼎盛、疆域辽阔，然闭关锁国错失工业革命，鸦片战争后列强入侵、内忧外患接踵而至，终以辛亥革命告终。',
    next: { title: '中华民国 · 南京', dynasty: '中华民国' },
    lanes: [
      { label: '君纪', borderColor: '#F1A805', bars: [
        { title: '顺治', start: 1644, end: 1661, type: ''       },
        { title: '康熙', start: 1661, end: 1722, type: 'accent' },
        { title: '雍正', start: 1722, end: 1735, type: ''       },
        { title: '乾隆', start: 1735, end: 1796, type: 'accent' },
        { title: '嘉庆', start: 1796, end: 1820, type: ''       },
        { title: '道光', start: 1820, end: 1850, type: ''       },
        { title: '咸丰', start: 1850, end: 1861, type: ''       },
        { title: '光绪', start: 1875, end: 1908, type: ''       },
      ]},
      { label: '士臣', borderColor: '#E0C088', bars: [
        { title: '洪亮吉', birth: 1746, death: 1809, appearStart: 1789, appearEnd: 1809, type: ''       },
        { title: '林则徐', birth: 1785, death: 1850, appearStart: 1839, appearEnd: 1850, type: ''       },
        { title: '曾国藩', birth: 1811, death: 1872, appearStart: 1853, appearEnd: 1872, type: 'accent' },
        { title: '李鸿章', birth: 1823, death: 1901, appearStart: 1870, appearEnd: 1895, type: ''       },
      ]},
      { label: '典制', borderColor: '#92ADA4', bars: [
        { title: '文字狱',   start: 1661, end: 1799, type: ''       },
        { title: '摊丁入亩', start: 1712, end: 1912, type: ''       },
        { title: '洋务运动', start: 1861, end: 1895, type: 'accent' },
      ]},
      { label: '事略', borderColor: '#9ABCC8', bars: [
        { title: '三藩之乱', start: 1673, end: 1681, type: ''       },
        { title: '鸦片战争', start: 1839, end: 1842, type: 'accent', boxKey: 'box-detail', boxTitle: '鸦片战争' },
        { title: '太平天国', start: 1851, end: 1864, type: 'accent' },
        { title: '甲午战争', start: 1894, end: 1895, type: 'marker', boxKey: 'box-detail', boxTitle: '甲午战争' },
      ]},
      { label: '民录', borderColor: '#D4B098', bars: [
        { title: '康乾盛世', start: 1681, end: 1796, type: '' },
        { title: '百日维新', start: 1898, end: 1899, type: '' },
      ]},
      { label: '著作', borderColor: '#A894B8', bars: [
        { title: '四库全书', start: 1773, end: 1782, type: 'accent' },
        { title: '红楼梦',   start: 1754, end: 1763, type: ''       },
      ]},
      { label: '思想', borderColor: '#7F9EB5', bars: [
        { title: '考据学',   start: 1700, end: 1810, type: ''       },
        { title: '经世致用', start: 1840, end: 1898, type: 'accent' },
      ]},
    ]
  },

  /* ════ 明 ════ */
  '明': {
    title: '明', civ: '华夏', range: '1368–1644', startYear: 1368, endYear: 1644,
    capital: '南京/北京',
    intro: '明朝（1368—1644）是继元之后的大一统王朝，共历十六帝二百七十六年，太祖洪武整吏治、永乐迁都北京并遣郑和七下西洋，文化昌盛、版图广阔，然宦官专权、党争内耗日深，终因李自成起义而亡。',
    next: { title: '清 · 北京', dynasty: '清' },
    lanes: [
      { label: '君纪', borderColor: '#F1A805', bars: [
        { title: '洪武', start: 1368, end: 1398, type: 'accent' },
        { title: '建文', start: 1398, end: 1402, type: ''       },
        { title: '永乐', start: 1402, end: 1424, type: 'accent' },
        { title: '仁宗', start: 1424, end: 1425, type: ''       },
        { title: '宣宗', start: 1425, end: 1435, type: ''       },
        { title: '正统', start: 1435, end: 1449, type: ''       },
        { title: '嘉靖', start: 1521, end: 1566, type: ''       },
        { title: '万历', start: 1572, end: 1620, type: ''       },
        { title: '崇祯', start: 1627, end: 1644, type: ''       },
      ]},
      { label: '士臣', borderColor: '#E0C088', bars: [
        { title: '刘伯温', birth: 1311, death: 1375, appearStart: 1360, appearEnd: 1375, type: ''       },
        { title: '海瑞',   birth: 1514, death: 1587, appearStart: 1569, appearEnd: 1587, type: ''       },
        { title: '戚继光', birth: 1528, death: 1588, appearStart: 1567, appearEnd: 1588, type: 'accent' },
        { title: '张居正', birth: 1525, death: 1582, appearStart: 1572, appearEnd: 1582, type: 'accent' },
      ]},
      { label: '典制', borderColor: '#92ADA4', bars: [
        { title: '里甲制',   start: 1368, end: 1644, type: 'ghost'  },
        { title: '内阁制度', start: 1402, end: 1644, type: ''       },
        { title: '一条鞭法', start: 1581, end: 1644, type: 'accent' },
      ]},
      { label: '事略', borderColor: '#9ABCC8', bars: [
        { title: '靖难之役',   start: 1399, end: 1402, type: 'accent' },
        { title: '土木堡之变', start: 1449, end: 1450, type: 'marker', boxKey: 'box-detail', boxTitle: '土木堡之变' },
        { title: '万历援朝',   start: 1592, end: 1598, type: ''       },
      ]},
      { label: '民录', borderColor: '#D4B098', bars: [
        { title: '郑和下西洋', start: 1405, end: 1433, type: 'accent' },
        { title: '李自成起义', start: 1627, end: 1644, type: ''       },
      ]},
      { label: '著作', borderColor: '#A894B8', bars: [
        { title: '永乐大典', start: 1403, end: 1408, type: 'accent' },
        { title: '本草纲目', start: 1578, end: 1580, type: 'marker' },
      ]},
      { label: '思想', borderColor: '#7F9EB5', bars: [
        { title: '阳明心学', start: 1518, end: 1529, type: 'accent' },
        { title: '东林议政', start: 1604, end: 1627, type: ''       },
      ]},
    ]
  },
}

/* ═══════════════════════════════════════════════════
   packBars：贪心区间调度，自动将平铺 bars 分配到行
   保证同一行内所有 bar 时间不重叠
═══════════════════════════════════════════════════ */
/**
 * 连续型泳道打包：单元布局（左虚线 + 胶囊 + 右虚线）
 * 复用士臣泳道的布局逻辑，但胶囊宽度按文字自适应
 */
const CONTINUOUS_CHIP_RPX  = 0    // 0 = 按文字字数动态计算
const CONTINUOUS_SHEET_RPX = 1440
const CONTINUOUS_CHAR_W    = 20   // 每字宽度 rpx（18rpx font + 间距）
const CONTINUOUS_PAD_RPX   = 24   // 胶囊左右 padding
const CONTINUOUS_MIN_CHIP  = 56   // 最小胶囊宽度

function calcChipWidth(title) {
  return Math.max(CONTINUOUS_MIN_CHIP, title.length * CONTINUOUS_CHAR_W + CONTINUOUS_PAD_RPX)
}

function packContinuousBars(rawBars, startYear, span) {
  const fmt = (n) => n.toFixed(1) + 'rpx'
  const sorted = [...rawBars].sort((a, b) => a.start - b.start)
  const rowEnds = []  // 记录每行最后一个胶囊的右边界（年份）
  const result  = []

  // 最小间距：相邻胶囊之间至少 20rpx（约 1-2 个字宽）
  const MIN_GAP_RPX = 20
  const gapYears = (MIN_GAP_RPX / CONTINUOUS_SHEET_RPX) * span

  for (const bar of sorted) {
    const chipW   = calcChipWidth(bar.title)
    // 单元宽度 = 事件跨度，但至少保证胶囊能放下 + 左右各留一点给虚线
    const minUnitRpx = chipW + 16  // 胶囊宽度 + 最小虚线空间
    const minSpanYears = (minUnitRpx / CONTINUOUS_SHEET_RPX) * span
    const effectiveEnd = Math.max(bar.end, bar.start + minSpanYears)

    let assigned = -1
    for (let r = 0; r < rowEnds.length; r++) {
      // 前一行的右边界 + 间距 <= 当前 bar 的左边界
      if (rowEnds[r] + gapYears <= bar.start) {
        assigned = r
        rowEnds[r] = effectiveEnd
        break
      }
    }
    if (assigned === -1) {
      assigned = rowEnds.length
      rowEnds.push(effectiveEnd)
    }

    let unitLeftPct  = (bar.start - startYear) / span * 100
    let unitWidthPct = (effectiveEnd - bar.start) / span * 100
    let unitWidthRpx = (effectiveEnd - bar.start) / span * CONTINUOUS_SHEET_RPX

    // 防止胶囊溢出画布右边界：如果 unit 右边缘超出 100%，向左收缩
    const maxLeftPct = 100 - (chipW / CONTINUOUS_SHEET_RPX * 100)
    if (unitLeftPct > maxLeftPct) {
      unitLeftPct = maxLeftPct
      unitWidthPct = 100 - unitLeftPct
      unitWidthRpx = unitWidthPct / 100 * CONTINUOUS_SHEET_RPX
    }

    // 胶囊居中于单元
    const chipLeftRpx = Math.max(0, (unitWidthRpx - chipW) / 2)
    const lineLeftW   = chipLeftRpx
    const lineRightL  = chipLeftRpx + chipW
    const lineRightW  = Math.max(0, unitWidthRpx - lineRightL)

    result.push({
      title:      bar.title,
      type:       bar.type || '',
      priority:   TYPE_TO_PRIORITY[bar.type || ''] || 'p2',
      boxKey:     bar.boxKey  || '',
      boxTitle:   bar.boxTitle || bar.title,
      chipWidth:  chipW + 'rpx',
      unitLeft:   unitLeftPct.toFixed(2) + '%',
      unitWidth:  unitWidthPct.toFixed(2) + '%',
      chipLeft:   fmt(chipLeftRpx),
      lineLeftW:  fmt(lineLeftW),
      lineRightL: fmt(lineRightL),
      lineRightW: fmt(lineRightW),
      _row: assigned,
    })
  }

  const maxRow = result.reduce((m, b) => Math.max(m, b._row), -1)
  const rows   = Array.from({ length: maxRow + 1 }, () => [])
  for (const bar of result) rows[bar._row].push(bar)
  return rows.map(row =>
    row
      .sort((a, b) => parseFloat(a.unitLeft) - parseFloat(b.unitLeft))
      .map(({ _row, ...bar }, idx) => ({ ...bar, zIndex: 10 + idx }))
  )
}

/**
 * 孤立型泳道打包：纯胶囊，无虚线，宽度自适应文字
 */
function packIsolatedBars(rawBars, startYear, span) {
  const SHEET_RPX = 1440
  const CHAR_W    = 20
  const PAD_RPX   = 24
  const MIN_CHIP  = 56
  const MIN_GAP_RPX = 16  // 胶囊间最小间距

  const sorted = [...rawBars].sort((a, b) => a.start - b.start)
  // rowEnds 记录每行最后一个胶囊的右边界年份
  const rowEnds = []
  const result  = []

  for (const bar of sorted) {
    const chipRpx  = Math.max(MIN_CHIP, bar.title.length * CHAR_W + PAD_RPX)
    const chipPct  = (chipRpx / SHEET_RPX) * 100
    // 胶囊居中于时间段中点，计算胶囊实际左右边界年份
    const mid = (bar.start + bar.end) / 2
    const chipHalfYears = (chipRpx / 2 / SHEET_RPX) * span
    const chipLeftYear  = mid - chipHalfYears
    const chipRightYear = mid + chipHalfYears
    const gapYears = (MIN_GAP_RPX / SHEET_RPX) * span

    let assigned = -1
    for (let r = 0; r < rowEnds.length; r++) {
      if (rowEnds[r] + gapYears <= chipLeftYear) {
        assigned = r
        rowEnds[r] = chipRightYear
        break
      }
    }
    if (assigned === -1) {
      assigned = rowEnds.length
      rowEnds.push(chipRightYear)
    }

    let left = (chipLeftYear - startYear) / span * 100
    left = Math.max(0, Math.min(100 - chipPct, left))

    result.push({
      title:    bar.title,
      left:     left.toFixed(2) + '%',
      width:    chipPct.toFixed(2) + '%',
      type:     bar.type || '',
      priority: TYPE_TO_PRIORITY[bar.type || ''] || 'p2',
      boxKey:   bar.boxKey  || '',
      boxTitle: bar.boxTitle || bar.title,
      _row: assigned,
    })
  }

  const maxRow = result.reduce((m, b) => Math.max(m, b._row), -1)
  const rows   = Array.from({ length: maxRow + 1 }, () => [])
  for (const bar of result) rows[bar._row].push(bar)
  return rows.map(row => row.map(({ _row, ...b }) => b))
}

/* ═══════════════════════════════════════════════════
   士臣专用：birth/death 生平 + appear 出场时段
   布局：出生—左虚线(渐淡)—圆角矩形(120rpx, 出场段居中)—右虚线(渐淡)—死亡
   装箱：整段单元 [birth, death] 不重叠才可同层并列
═══════════════════════════════════════════════════ */
const SHICHEN_APPEAR_MIN = 10
const SHICHEN_APPEAR_MAX = 20
const SHICHEN_CHIP_RPX   = 120
const SHICHEN_SHEET_RPX  = 1440  // 与 .dyn-swim-sheet 宽度一致

function normalizeShichenBar(bar) {
  const birth = bar.birth ?? bar.start
  const death = bar.death ?? bar.end
  let appearStart = bar.appearStart
  let appearEnd   = bar.appearEnd

  if (appearStart == null || appearEnd == null) {
    const life = Math.max(death - birth, 1)
    let span = Math.min(SHICHEN_APPEAR_MAX, Math.max(SHICHEN_APPEAR_MIN, Math.round(life * 0.22)))
    const mid = birth + Math.round(life * 0.48)
    appearStart = Math.max(birth, mid - Math.round(span / 2))
    appearEnd   = Math.min(death, appearStart + span)
    if (appearEnd - appearStart < SHICHEN_APPEAR_MIN) {
      appearEnd = Math.min(death, appearStart + SHICHEN_APPEAR_MIN)
    }
  }

  appearStart = Math.max(birth, Math.min(appearStart, death - 1))
  appearEnd   = Math.max(appearStart + 1, Math.min(appearEnd, death))

  return { ...bar, birth, death, appearStart, appearEnd }
}

function layoutShichenBar(bar, startYear, span) {
  const { birth, death, appearStart, appearEnd } = bar
  const lifeYears = Math.max(death - birth, 1)

  const unitLeftPct  = (birth - startYear) / span * 100
  const unitWidthPct = Math.max(lifeYears / span * 100, 1.2)
  const unitWidthRpx = lifeYears / span * SHICHEN_SHEET_RPX

  const appearMid = (appearStart + appearEnd) / 2
  const chipCenterRpx = ((appearMid - birth) / lifeYears) * unitWidthRpx
  let chipLeftRpx = chipCenterRpx - SHICHEN_CHIP_RPX / 2
  chipLeftRpx = Math.max(0, Math.min(Math.max(0, unitWidthRpx - SHICHEN_CHIP_RPX), chipLeftRpx))

  const lineLeftRpx  = chipLeftRpx
  const lineRightLft = chipLeftRpx + SHICHEN_CHIP_RPX
  const lineRightRpx = Math.max(0, unitWidthRpx - lineRightLft)

  const fmt = (n) => n.toFixed(1) + 'rpx'

  return {
    title:     bar.title,
    type:      bar.type || '',
    boxKey:    bar.boxKey  || '',
    boxTitle:  bar.boxTitle || bar.title,
    unitLeft:  unitLeftPct.toFixed(2) + '%',
    unitWidth: unitWidthPct.toFixed(2) + '%',
    chipLeft:  fmt(chipLeftRpx),
    lineLeftW: fmt(lineLeftRpx),
    lineRightL: fmt(lineRightLft),
    lineRightW: fmt(lineRightRpx),
  }
}

function packShichenBars(rawBars, startYear, span) {
  const normalized = rawBars.map(normalizeShichenBar)
  // 按出生年排序，贪心找第一个能完整放下整段 [birth, death] 的行
  const sorted = [...normalized].sort((a, b) => {
    if (a.birth !== b.birth) return a.birth - b.birth
    return a.death - b.death
  })
  const rowEnds = []
  const result  = []

  for (const bar of sorted) {
    let assigned = -1
    for (let r = 0; r < rowEnds.length; r++) {
      // 前行单元结束 ≤ 本单元出生 → 时间轴上完全空白，可并列
      if (rowEnds[r] <= bar.birth) {
        assigned = r
        rowEnds[r] = bar.death
        break
      }
    }
    if (assigned === -1) {
      assigned = rowEnds.length
      rowEnds.push(bar.death)
    }

    result.push({ ...layoutShichenBar(bar, startYear, span), _row: assigned })
  }

  const maxRow = result.reduce((m, b) => Math.max(m, b._row), -1)
  const rows   = Array.from({ length: maxRow + 1 }, () => [])
  for (const bar of result) rows[bar._row].push(bar)

  // 同行内按出生先后叠放 z-index（后出生者略靠前）
  return rows.map(row =>
    row
      .sort((a, b) => parseFloat(a.unitLeft) - parseFloat(b.unitLeft))
      .map(({ _row, ...bar }, idx) => ({ ...bar, zIndex: 10 + idx }))
  )
}

/**
 * 士臣泳道 · 贪心装箱分行
 * 按整段 [birth, death] 调度：同行仅当时间轴完全空白时可并列，保证单元永不重叠
 */

function getDynastyData(dynastyName) {
  return DYNASTY_DB[dynastyName] || DYNASTY_DB['北宋']
}

function buildSwimData(dynastyName) {
  const d    = getDynastyData(dynastyName)
  const span = d.endYear - d.startYear

  const lanes = d.lanes.map(lane => {
    const allBars = lane.bars
    const total   = allBars.length

    // 士臣泳道：平面紧凑排列，贪心装箱，全量展示（士臣固定为连续型）
    if (lane.label === SHICHEN_LABEL) {
      const collapsedRows = packShichenBars(allBars, d.startYear, span)
      return {
        label:         lane.label,
        borderColor:   lane.borderColor || '#EDEAE6',
        layout:        'shichen',
        continuous:    true,
        collapsedRows,
        hasMore:       false,
        moreCount:     0,
        extraBars:     [],
        moreBarLeft:   '0%',
        moreBarWidth:  '10%',
      }
    }

    const hasMore   = total > MAX_VISIBLE
    const moreCount = total - MAX_VISIBLE

    // 判断泳道类型：连续型 vs 孤立型
    const isContinuous = LANE_CONTINUOUS[lane.label] !== false

    // 泳道内只显示前 MAX_VISIBLE 条
    const visibleBars = hasMore ? allBars.slice(0, MAX_VISIBLE) : allBars

    // 连续型用单元布局（虚线+胶囊），孤立型用纯胶囊布局
    const collapsedRows = isContinuous
      ? packContinuousBars(visibleBars, d.startYear, span)
      : packIsolatedBars(visibleBars, d.startYear, span)

    // 超出部分：保留原始信息供浮层展示
    const extraBars = hasMore
      ? allBars.slice(MAX_VISIBLE).map(bar => ({
          title:     bar.title,
          type:      bar.type || '',
          timeRange: `${bar.start}–${bar.end}`,
        }))
      : []

    // 第10条（最后一条可见 bar）的位置，用于定位「还有N条」胶囊
    let moreBarLeft  = '0%'
    let moreBarWidth = '10%'
    if (hasMore) {
      const last     = allBars[MAX_VISIBLE - 1]
      const rawLeft  = (last.start - d.startYear) / span * 100
      const rawWidth = Math.max((last.end - last.start) / span * 100, 2)
      moreBarLeft  = rawLeft.toFixed(2) + '%'
      moreBarWidth = rawWidth.toFixed(2) + '%'
    }

    return {
      label:        lane.label,
      borderColor:  lane.borderColor || '#EDEAE6',
      layout:       isContinuous ? 'continuous' : 'isolated',
      continuous:   isContinuous,
      collapsedRows,
      hasMore,
      moreCount,
      extraBars,
      moreBarLeft,
      moreBarWidth,
    }
  })

  // 时间轴刻度：相对刻度制，根据朝代跨度动态选择间隔
  // 确保刻度标签不重叠（标签宽度约 40rpx，对应 1440rpx 画布约 2.8%）
  let tickStep
  if (span <= 50)       tickStep = 5
  else if (span <= 100) tickStep = 10
  else if (span <= 200) tickStep = 20
  else if (span <= 500) tickStep = 50
  else                  tickStep = 100

  const firstTick = Math.ceil(d.startYear / tickStep) * tickStep
  const ticks     = []
  for (let y = firstTick; y < d.endYear; y += tickStep) {
    const leftPct = (y - d.startYear) / span * 100
    ticks.push({
      label:     fmtAxisYear(y),
      left:      leftPct.toFixed(3) + '%',
      edgeStart: leftPct < 0.1,
    })
  }

  const endLabel = fmtAxisYear(d.endYear)

  const concurrentItems = getConcurrentItems(d.civ, d.title, d.startYear, d.endYear)

  return { ...d, ticks, endLabel, lanes, concurrentItems }
}

module.exports = { DYNASTY_DB, WORLD_DYNASTIES, getDynastyData, buildSwimData }
