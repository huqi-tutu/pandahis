/**
 * 历史图谱 · 朝代详情 Mock 数据
 *
 * 泳道排布原则：
 *   - 每条泳道有一组平铺的 bars（无须手动分行）
 *   - buildSwimData 调用 packBars 自动按贪心区间调度分行，保证同行无重叠
 *   - 每条泳道最多显示 MAX_VISIBLE 条，超出部分折叠
 */

const MAX_VISIBLE = 10   // 每条泳道最多展示条数

/* ═══════════════════════════════════════════════════
   全球文明朝代数据库（用于并发政权计算）
   两个时段重叠条件：d.start < endYear AND d.end > startYear
═══════════════════════════════════════════════════ */
const WORLD_DYNASTIES = [
  // ── 华夏 ──
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
      // 士臣：13条，超过10条用于折叠交互示意
      { label: '士臣', borderColor: '#E0C088', bars: [
        { title: '晏殊',   start: 991,  end: 1055, type: ''       },
        { title: '范仲淹', start: 989,  end: 1052, type: ''       },
        { title: '包拯',   start: 999,  end: 1062, type: ''       },
        { title: '欧阳修', start: 1007, end: 1072, type: ''       },
        { title: '富弼',   start: 1004, end: 1083, type: ''       },
        { title: '韩琦',   start: 1008, end: 1075, type: ''       },
        { title: '司马光', start: 1019, end: 1086, type: ''       },
        { title: '王安石', start: 1021, end: 1086, type: 'accent' },
        { title: '沈括',   start: 1031, end: 1095, type: ''       },
        { title: '苏轼',   start: 1037, end: 1101, type: ''       },
        // ↓ 以下3条折叠示意
        { title: '黄庭坚', start: 1045, end: 1105, type: ''       },
        { title: '秦观',   start: 1049, end: 1100, type: ''       },
        { title: '蔡京',   start: 1047, end: 1126, type: ''       },
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
        { title: '房玄龄', start: 626, end: 648, type: '' },
        { title: '魏征',   start: 626, end: 643, type: '' },
        { title: '李白',   start: 701, end: 762, type: '' },
        { title: '杜甫',   start: 712, end: 770, type: '' },
        { title: '韩愈',   start: 768, end: 824, type: '' },
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
        { title: '洪亮吉', start: 1746, end: 1809, type: ''       },
        { title: '林则徐', start: 1785, end: 1850, type: ''       },
        { title: '曾国藩', start: 1811, end: 1872, type: 'accent' },
        { title: '李鸿章', start: 1823, end: 1901, type: ''       },
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
        { title: '刘伯温', start: 1311, end: 1375, type: ''       },
        { title: '海瑞',   start: 1514, end: 1587, type: ''       },
        { title: '戚继光', start: 1528, end: 1588, type: 'accent' },
        { title: '张居正', start: 1525, end: 1582, type: 'accent' },
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
    ]
  },
}

/* ═══════════════════════════════════════════════════
   packBars：贪心区间调度，自动将平铺 bars 分配到行
   保证同一行内所有 bar 时间不重叠
═══════════════════════════════════════════════════ */
function packBars(rawBars, startYear, span) {
  const MIN_WIDTH_PCT = 2
  const sorted = [...rawBars].sort((a, b) => a.start - b.start)
  const rowEnds = []
  const result  = []

  for (const bar of sorted) {
    let assigned = -1
    for (let r = 0; r < rowEnds.length; r++) {
      if (rowEnds[r] <= bar.start) {
        assigned = r
        rowEnds[r] = bar.end
        break
      }
    }
    if (assigned === -1) {
      assigned = rowEnds.length
      rowEnds.push(bar.end)
    }

    const rawLeft  = (bar.start - startYear) / span * 100
    const rawWidth = Math.max((bar.end - bar.start) / span * 100, MIN_WIDTH_PCT)
    result.push({
      title:    bar.title,
      left:     rawLeft.toFixed(2) + '%',
      width:    rawWidth.toFixed(2) + '%',
      type:     bar.type || '',
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

function getDynastyData(dynastyName) {
  return DYNASTY_DB[dynastyName] || DYNASTY_DB['北宋']
}

function buildSwimData(dynastyName) {
  const d    = getDynastyData(dynastyName)
  const span = d.endYear - d.startYear

  const lanes = d.lanes.map(lane => {
    const allBars   = lane.bars
    const total     = allBars.length
    const hasMore   = total > MAX_VISIBLE
    const moreCount = total - MAX_VISIBLE

    // 泳道内只显示前 MAX_VISIBLE 条（打包后无重叠）
    const visibleBars   = hasMore ? allBars.slice(0, MAX_VISIBLE) : allBars
    const collapsedRows = packBars(visibleBars, d.startYear, span)

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
      collapsedRows,
      hasMore,
      moreCount,
      extraBars,
      moreBarLeft,
      moreBarWidth,
    }
  })

  // 时间轴刻度：仅15年整数
  const tickStep  = 15
  const firstTick = Math.ceil(d.startYear / tickStep) * tickStep
  const ticks     = []
  for (let y = firstTick; y < d.endYear; y += tickStep) {
    const leftPct = (y - d.startYear) / span * 100
    ticks.push({
      label:     String(Math.abs(y)) + (y < 0 ? ' BCE' : ''),
      left:      leftPct.toFixed(3) + '%',
      edgeStart: leftPct < 0.1,
    })
  }

  const endLabel = d.endYear < 0
    ? String(Math.abs(d.endYear)) + ' BCE'
    : String(d.endYear)

  const concurrentItems = getConcurrentItems(d.civ, d.title, d.startYear, d.endYear)

  return { ...d, ticks, endLabel, lanes, concurrentItems }
}

module.exports = { DYNASTY_DB, WORLD_DYNASTIES, getDynastyData, buildSwimData }
