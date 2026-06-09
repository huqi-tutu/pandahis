// 四大并列文明事件数据
// region: 'asia' | 'europe' | 'americas' | 'africa'
// start/end: 年份（负数为公元前）

const WORLD_EVENTS = [

  // ══════════════════════════════
  //  ② 亚洲文明（排除中华）
  //  印度·西亚·中亚·东南亚
  // ══════════════════════════════
  { id: 'sumer',        region: 'asia', name: '苏美尔城邦',     start: -3500, end: -2000 },
  { id: 'akkad',        region: 'asia', name: '阿卡德帝国',     start: -2334, end: -2154 },
  { id: 'indus',        region: 'asia', name: '印度河文明',     start: -2600, end: -1900 },
  { id: 'ur3',          region: 'asia', name: '乌尔第三王朝',   start: -2112, end: -2004 },
  { id: 'babylon1',     region: 'asia', name: '古巴比伦王国',   start: -1894, end: -1595 },
  { id: 'hittite',      region: 'asia', name: '赫梯帝国',       start: -1680, end: -1178 },
  { id: 'vedic',        region: 'asia', name: '吠陀时代（印度）',start: -1500, end: -600  },
  { id: 'assyria',      region: 'asia', name: '亚述帝国',       start: -900,  end: -612  },
  { id: 'neo_babylon',  region: 'asia', name: '新巴比伦王国',   start: -626,  end: -539  },
  { id: 'mahajanapada', region: 'asia', name: '印度列国时代',   start: -600,  end: -321  },
  { id: 'persia_ach',   region: 'asia', name: '波斯帝国（阿契美尼德）', start: -550, end: -330 },
  { id: 'seleucid',     region: 'asia', name: '塞琉古帝国',     start: -312,  end: -63   },
  { id: 'maurya',       region: 'asia', name: '孔雀王朝（印度）',start: -321,  end: -185  },
  { id: 'parthia',      region: 'asia', name: '帕提亚（安息）', start: -247,  end: 224   },
  { id: 'kushan',       region: 'asia', name: '贵霜帝国',       start: 30,    end: 375   },
  { id: 'sassanid',     region: 'asia', name: '萨珊波斯',       start: 224,   end: 651   },
  { id: 'gupta',        region: 'asia', name: '笈多王朝（印度）',start: 320,   end: 550   },
  { id: 'harsha',       region: 'asia', name: '戒日王朝（印度）',start: 606,   end: 647   },
  { id: 'rashidun',     region: 'asia', name: '正统哈里发国',   start: 632,   end: 661   },
  { id: 'umayyad',      region: 'asia', name: '倭马亚哈里发',   start: 661,   end: 750   },
  { id: 'abbasid',      region: 'asia', name: '阿拔斯哈里发',   start: 750,   end: 1258  },
  { id: 'rajput',       region: 'asia', name: '拉其普特诸邦',   start: 650,   end: 1200  },
  { id: 'seljuk',       region: 'asia', name: '塞尔柱帝国',     start: 1037,  end: 1194  },
  { id: 'crusader_kgd', region: 'asia', name: '耶路撒冷王国',   start: 1099,  end: 1291  },
  { id: 'il_khanate',   region: 'asia', name: '伊儿汗国',       start: 1256,  end: 1335  },
  { id: 'delhi_sultan', region: 'asia', name: '德里苏丹国',     start: 1206,  end: 1526  },
  { id: 'ottoman',      region: 'asia', name: '奥斯曼帝国',     start: 1299,  end: 1922  },
  { id: 'safavid',      region: 'asia', name: '萨非王朝（波斯）',start: 1501,  end: 1736  },
  { id: 'mughal',       region: 'asia', name: '莫卧儿帝国',     start: 1526,  end: 1858  },
  { id: 'brit_india',   region: 'asia', name: '英国统治印度',   start: 1757,  end: 1912  },

  // ══════════════════════════════
  //  ③ 欧洲文明
  // ══════════════════════════════
  { id: 'minoan',        region: 'europe', name: '米诺斯文明',       start: -2700, end: -1100 },
  { id: 'mycenae',       region: 'europe', name: '迈锡尼文明',       start: -1600, end: -1100 },
  { id: 'greek_dark',    region: 'europe', name: '希腊黑暗时代',     start: -1100, end: -800  },
  { id: 'greek_archaic', region: 'europe', name: '希腊古风时代',     start: -800,  end: -479  },
  { id: 'greek_classic', region: 'europe', name: '雅典黄金时代',     start: -479,  end: -323  },
  { id: 'macedon',       region: 'europe', name: '亚历山大帝国',     start: -336,  end: -146  },
  { id: 'roman_rep',     region: 'europe', name: '罗马共和国',       start: -509,  end: -27   },
  { id: 'roman_emp',     region: 'europe', name: '罗马帝国',         start: -27,   end: 284   },
  { id: 'roman_late',    region: 'europe', name: '罗马帝国（晚期）', start: 284,   end: 476   },
  { id: 'byzantine',     region: 'europe', name: '拜占庭帝国',       start: 330,   end: 1453  },
  { id: 'visigoths',     region: 'europe', name: '西哥特王国',       start: 418,   end: 711   },
  { id: 'franks',        region: 'europe', name: '法兰克王国',       start: 481,   end: 987   },
  { id: 'charlemagne',   region: 'europe', name: '查理曼帝国',       start: 800,   end: 843   },
  { id: 'holy_roman',    region: 'europe', name: '神圣罗马帝国',     start: 962,   end: 1806  },
  { id: 'normans',       region: 'europe', name: '诺曼王朝（英国）', start: 1066,  end: 1154  },
  { id: 'crusades',      region: 'europe', name: '十字军东征时代',   start: 1096,  end: 1291  },
  { id: 'magna_carta',   region: 'europe', name: '英格兰王国',       start: 1215,  end: 1500  },
  { id: 'renaissance',   region: 'europe', name: '文艺复兴',         start: 1300,  end: 1600  },
  { id: 'hundred_years', region: 'europe', name: '英法百年战争',     start: 1337,  end: 1453  },
  { id: 'byzantine_fall',region: 'europe', name: '奥斯曼灭拜占庭',  start: 1453,  end: 1453  },
  { id: 'reformation',   region: 'europe', name: '宗教改革',         start: 1517,  end: 1648  },
  { id: 'habsburg',      region: 'europe', name: '哈布斯堡王朝',     start: 1519,  end: 1806  },
  { id: 'thirty_years',  region: 'europe', name: '三十年战争',       start: 1618,  end: 1648  },
  { id: 'louis14',       region: 'europe', name: '路易十四·法国',    start: 1643,  end: 1715  },
  { id: 'industrial',    region: 'europe', name: '工业革命',         start: 1760,  end: 1840  },
  { id: 'french_rev',    region: 'europe', name: '法国大革命',       start: 1789,  end: 1799  },
  { id: 'napoleon',      region: 'europe', name: '拿破仑帝国',       start: 1804,  end: 1815  },
  { id: 'europe_powers', region: 'europe', name: '欧洲列强时代',     start: 1815,  end: 1912  },

  // ══════════════════════════════
  //  ④ 美洲文明
  // ══════════════════════════════
  { id: 'caral',       region: 'americas', name: '卡拉尔文明',      start: -3000, end: -1800 },
  { id: 'olmec',       region: 'americas', name: '奥尔梅克文明',    start: -1500, end: -400  },
  { id: 'chavin',      region: 'americas', name: '查文文化（南美）',start: -900,  end: -200  },
  { id: 'teotihuacan', region: 'americas', name: '特奥蒂瓦坎城',    start: -100,  end: 650   },
  { id: 'hopewell',    region: 'americas', name: '霍普韦尔文化',    start: -100,  end: 500   },
  { id: 'maya_classic',region: 'americas', name: '玛雅古典文明',    start: 250,   end: 900   },
  { id: 'toltec',      region: 'americas', name: '托尔特克文化',    start: 900,   end: 1200  },
  { id: 'cahokia',     region: 'americas', name: '卡霍基亚城邦',    start: 900,   end: 1300  },
  { id: 'aztec',       region: 'americas', name: '阿兹特克帝国',    start: 1300,  end: 1521  },
  { id: 'inca',        region: 'americas', name: '印加帝国',        start: 1438,  end: 1533  },
  { id: 'columbian',   region: 'americas', name: '哥伦布·欧洲殖民',start: 1492,  end: 1820  },
  { id: 'usa',         region: 'americas', name: '美利坚合众国',    start: 1776,  end: 1912  },
  { id: 'latin_indep', region: 'americas', name: '拉美独立运动',    start: 1810,  end: 1825  },

  // ══════════════════════════════
  //  ⑤ 非洲文明
  // ══════════════════════════════
  { id: 'egypt_early',  region: 'africa', name: '古埃及早期王朝',  start: -3100, end: -2686 },
  { id: 'egypt_old',    region: 'africa', name: '古埃及古王国',    start: -2686, end: -2181 },
  { id: 'egypt_mid',    region: 'africa', name: '古埃及中王国',    start: -2055, end: -1650 },
  { id: 'egypt_new',    region: 'africa', name: '古埃及新王国',    start: -1550, end: -1070 },
  { id: 'nubia_kush',   region: 'africa', name: '努比亚·库施王国', start: -2500, end: 350   },
  { id: 'egypt_late',   region: 'africa', name: '古埃及晚期',      start: -1070, end: -332  },
  { id: 'carthage',     region: 'africa', name: '迦太基（腓尼基）',start: -814,  end: -146  },
  { id: 'ptolemaic',    region: 'africa', name: '托勒密埃及',      start: -305,  end: -30   },
  { id: 'roman_egypt',  region: 'africa', name: '罗马省·埃及',    start: -30,   end: 641   },
  { id: 'axum',         region: 'africa', name: '阿克苏姆帝国',    start: 100,   end: 960   },
  { id: 'ghana',        region: 'africa', name: '加纳帝国（西非）',start: 300,   end: 1240  },
  { id: 'swahili',      region: 'africa', name: '斯瓦希里海岸城邦',start: 900,   end: 1500  },
  { id: 'great_zim',    region: 'africa', name: '大津巴布韦',      start: 1100,  end: 1450  },
  { id: 'mali',         region: 'africa', name: '马里帝国（西非）',start: 1235,  end: 1600  },
  { id: 'songhai',      region: 'africa', name: '桑海帝国',        start: 1464,  end: 1591  },
  { id: 'kongo',        region: 'africa', name: '刚果王国',        start: 1390,  end: 1857  },
  { id: 'slave_trade',  region: 'africa', name: '大西洋奴隶贸易',  start: 1500,  end: 1867  },
  { id: 'scramble_af',  region: 'africa', name: '欧洲瓜分非洲',   start: 1880,  end: 1912  },
];

module.exports = { WORLD_EVENTS };
