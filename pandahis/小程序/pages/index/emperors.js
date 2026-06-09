// 中华历史帝王完整数据
// start/end: 年份（负数为公元前），reign: 在位年数

// ── 中华文明色彩规则 ────────────────────────────────────
// 文字：全部统一用 CHINA_TEXT，不做差异化
// 背景：同一红色 CHINA_BASE_RGB，仅透明度（alpha）不同
//   鼎盛大一统朝代  → alpha 高（背景更红、更明显）
//   上古/分裂/异族  → alpha 低（背景极淡）
// ────────────────────────────────────────────────────────
const CHINA_BASE_RGB  = '196,40,40';   // #C42828 的 RGB 分量
const CHINA_TEXT      = '#E8A8A8';     // 统一文字色：温暖浅红，所有朝代一致

// 每个朝代对应背景透明度（越高越明显，越低越淡）
const DYNASTY_BG_ALPHA = {
  '史前':      0.04,
  '三皇五帝':  0.06,
  '夏':        0.07,
  '商':        0.09,
  '西周':      0.07,
  '东周·春秋': 0.08,
  '东周·战国': 0.09,
  '秦':        0.22,  // 一统天下
  '西汉':      0.18,  // 大汉盛世
  '新':        0.05,  // 过渡
  '东汉':      0.16,
  '三国·魏':   0.07,  // 分裂
  '西晋':      0.06,
  '东晋':      0.07,
  '南朝·宋':   0.07,
  '南朝·齐':   0.07,
  '南朝·梁':   0.07,
  '南朝·陈':   0.07,
  '隋':        0.15,  // 再统一
  '唐':        0.22,  // 开元盛世
  '五代':      0.05,  // 乱世
  '北宋':      0.15,
  '南宋':      0.09,  // 偏安
  '元':        0.06,  // 异族
  '明':        0.18,
  '清':        0.08,  // 异族
};

// 史前到1912年完整帝王/历史时期列表
const EMPERORS = [
  // ── 史前（对应PRD中前5500年起始）──
  { id: 'prehistoric', name: '史前文明', dynasty: '史前', start: -5500, end: -2697, reign: 2803, note: '新石器时代·龙山文化' },

  // ── 三皇五帝（传说时代）──
  { id: 'huangdi',  name: '黄帝',  dynasty: '三皇五帝', start: -2697, end: -2597, reign: 100 },
  { id: 'zhuanxu',  name: '颛顼',  dynasty: '三皇五帝', start: -2513, end: -2435, reign: 78  },
  { id: 'diku',     name: '帝喾',  dynasty: '三皇五帝', start: -2435, end: -2365, reign: 70  },
  { id: 'yao',      name: '帝尧',  dynasty: '三皇五帝', start: -2357, end: -2257, reign: 100 },
  { id: 'shun',     name: '帝舜',  dynasty: '三皇五帝', start: -2257, end: -2207, reign: 50  },

  // ── 夏朝（前2070—前1600）──
  { id: 'xia_yu',      name: '禹',   dynasty: '夏', start: -2070, end: -2043, reign: 27 },
  { id: 'xia_qi',      name: '启',   dynasty: '夏', start: -2043, end: -2003, reign: 40 },
  { id: 'xia_taikang', name: '太康', dynasty: '夏', start: -2003, end: -1978, reign: 25 },
  { id: 'xia_zhongkang',name:'仲康', dynasty: '夏', start: -1978, end: -1963, reign: 15 },
  { id: 'xia_xiang',   name: '相',   dynasty: '夏', start: -1963, end: -1921, reign: 42 },
  { id: 'xia_shaokang', name:'少康', dynasty: '夏', start: -1921, end: -1900, reign: 21 },
  { id: 'xia_zhu',     name: '杼',   dynasty: '夏', start: -1900, end: -1879, reign: 21 },
  { id: 'xia_huai',    name: '槐',   dynasty: '夏', start: -1879, end: -1848, reign: 31 },
  { id: 'xia_mang',    name: '芒',   dynasty: '夏', start: -1848, end: -1808, reign: 40 },
  { id: 'xia_xie',     name: '泄',   dynasty: '夏', start: -1808, end: -1783, reign: 25 },
  { id: 'xia_bujiang', name: '不降', dynasty: '夏', start: -1783, end: -1724, reign: 59 },
  { id: 'xia_jiong',   name: '扃',   dynasty: '夏', start: -1724, end: -1705, reign: 19 },
  { id: 'xia_jin',     name: '廑',   dynasty: '夏', start: -1705, end: -1695, reign: 10 },
  { id: 'xia_kongjia', name: '孔甲', dynasty: '夏', start: -1695, end: -1665, reign: 30 },
  { id: 'xia_gao',     name: '皋',   dynasty: '夏', start: -1665, end: -1654, reign: 11 },
  { id: 'xia_fa',      name: '发',   dynasty: '夏', start: -1654, end: -1643, reign: 11 },
  { id: 'xia_jie',     name: '桀',   dynasty: '夏', start: -1643, end: -1600, reign: 43 },

  // ── 商朝（前1600—前1046）──
  { id: 'shang_tang',   name: '商汤（成汤）',  dynasty: '商', start: -1600, end: -1588, reign: 12  },
  { id: 'shang_g1',     name: '太丁/外丙/仲壬',dynasty: '商', start: -1588, end: -1558, reign: 30  },
  { id: 'shang_taijia', name: '太甲',          dynasty: '商', start: -1558, end: -1527, reign: 31  },
  { id: 'shang_woding', name: '沃丁/太庚',     dynasty: '商', start: -1527, end: -1483, reign: 44  },
  { id: 'shang_xiaojia',name: '小甲/雍己',     dynasty: '商', start: -1483, end: -1452, reign: 31  },
  { id: 'shang_taiwu',  name: '太戊',          dynasty: '商', start: -1452, end: -1375, reign: 77  },
  { id: 'shang_middle', name: '仲丁至祖乙',    dynasty: '商', start: -1375, end: -1250, reign: 125 },
  { id: 'shang_pangen', name: '盘庚（迁殷）',  dynasty: '商', start: -1250, end: -1192, reign: 58  },
  { id: 'shang_wuding', name: '武丁（妇好时代）',dynasty: '商',start: -1200, end: -1139, reign: 61  },
  { id: 'shang_late',   name: '祖庚至庚丁',    dynasty: '商', start: -1139, end: -1075, reign: 64  },
  { id: 'shang_dixin',  name: '帝辛（纣王）',  dynasty: '商', start: -1075, end: -1046, reign: 29  },

  // ── 西周（前1046—前771）──
  { id: 'zhou_wu',     name: '周武王',  dynasty: '西周', start: -1046, end: -1043, reign: 3  },
  { id: 'zhou_cheng',  name: '周成王',  dynasty: '西周', start: -1043, end: -1021, reign: 22 },
  { id: 'zhou_kang',   name: '周康王',  dynasty: '西周', start: -1021, end: -996,  reign: 25 },
  { id: 'zhou_zhao',   name: '周昭王',  dynasty: '西周', start: -996,  end: -977,  reign: 19 },
  { id: 'zhou_mu',     name: '周穆王',  dynasty: '西周', start: -977,  end: -922,  reign: 55 },
  { id: 'zhou_gong',   name: '周共王',  dynasty: '西周', start: -922,  end: -900,  reign: 22 },
  { id: 'zhou_yi1',    name: '周懿王/孝王',dynasty: '西周',start: -900, end: -878,  reign: 22 },
  { id: 'zhou_li',     name: '周厉王',  dynasty: '西周', start: -878,  end: -841,  reign: 37 },
  { id: 'zhou_gonghe', name: '共和行政',dynasty: '西周', start: -841,  end: -828,  reign: 13 },
  { id: 'zhou_xuan',   name: '周宣王',  dynasty: '西周', start: -828,  end: -782,  reign: 46 },
  { id: 'zhou_you',    name: '周幽王',  dynasty: '西周', start: -782,  end: -771,  reign: 11 },

  // ── 东周·春秋（前771—前476）──
  { id: 'zhou_ping',   name: '周平王',  dynasty: '东周·春秋', start: -771, end: -720, reign: 51 },
  { id: 'zhou_huan',   name: '周桓王',  dynasty: '东周·春秋', start: -720, end: -697, reign: 23 },
  { id: 'zhou_zhuang', name: '周庄/釐王',dynasty:'东周·春秋', start: -697, end: -677, reign: 20 },
  { id: 'zhou_hui',    name: '周惠王',  dynasty: '东周·春秋', start: -677, end: -652, reign: 25 },
  { id: 'zhou_xiang',  name: '周襄王',  dynasty: '东周·春秋', start: -652, end: -619, reign: 33 },
  { id: 'zhou_qk',     name: '周顷/匡王',dynasty:'东周·春秋', start: -619, end: -607, reign: 12 },
  { id: 'zhou_ding',   name: '周定王',  dynasty: '东周·春秋', start: -607, end: -586, reign: 21 },
  { id: 'zhou_jian',   name: '周简王',  dynasty: '东周·春秋', start: -586, end: -572, reign: 14 },
  { id: 'zhou_ling',   name: '周灵王',  dynasty: '东周·春秋', start: -572, end: -545, reign: 27 },
  { id: 'zhou_jing1',  name: '周景王',  dynasty: '东周·春秋', start: -545, end: -520, reign: 25 },
  { id: 'zhou_jing2',  name: '周敬王',  dynasty: '东周·春秋', start: -520, end: -476, reign: 44 },

  // ── 东周·战国（前476—前256）──
  { id: 'zhou_yuan',   name: '周元王',  dynasty: '东周·战国', start: -476, end: -469, reign: 7  },
  { id: 'zhou_zhen',   name: '周贞定王',dynasty: '东周·战国', start: -469, end: -441, reign: 28 },
  { id: 'zhou_aisk',   name: '周哀/思/考王',dynasty:'东周·战国',start:-441, end: -426, reign: 15 },
  { id: 'zhou_weilie', name: '周威烈王',dynasty: '东周·战国', start: -426, end: -402, reign: 24 },
  { id: 'zhou_an',     name: '周安王',  dynasty: '东周·战国', start: -402, end: -376, reign: 26 },
  { id: 'zhou_lie',    name: '周烈王',  dynasty: '东周·战国', start: -376, end: -369, reign: 7  },
  { id: 'zhou_xian',   name: '周显王',  dynasty: '东周·战国', start: -369, end: -321, reign: 48 },
  { id: 'zhou_shen',   name: '周慎靓王',dynasty: '东周·战国', start: -321, end: -315, reign: 6  },
  { id: 'zhou_nan',    name: '周赧王',  dynasty: '东周·战国', start: -315, end: -256, reign: 59 },

  // ── 秦朝（前221—前206）──
  { id: 'qin_shi',  name: '秦始皇',    dynasty: '秦', start: -221, end: -210, reign: 11 },
  { id: 'qin_er',   name: '二世/子婴', dynasty: '秦', start: -210, end: -206, reign: 4  },

  // ── 西汉（前202—公元9）──
  { id: 'han_gaozu', name: '汉高祖（刘邦）',dynasty: '西汉', start: -202, end: -195, reign: 7  },
  { id: 'han_hui',   name: '汉惠帝',        dynasty: '西汉', start: -195, end: -188, reign: 7  },
  { id: 'han_lv',    name: '吕后摄政',      dynasty: '西汉', start: -188, end: -180, reign: 8  },
  { id: 'han_wen',   name: '汉文帝',        dynasty: '西汉', start: -180, end: -157, reign: 23 },
  { id: 'han_jing',  name: '汉景帝',        dynasty: '西汉', start: -157, end: -141, reign: 16 },
  { id: 'han_wu',    name: '汉武帝',        dynasty: '西汉', start: -141, end: -87,  reign: 54 },
  { id: 'han_zhao',  name: '汉昭帝',        dynasty: '西汉', start: -87,  end: -74,  reign: 13 },
  { id: 'han_xuan',  name: '汉宣帝',        dynasty: '西汉', start: -74,  end: -49,  reign: 25 },
  { id: 'han_yuan',  name: '汉元帝',        dynasty: '西汉', start: -49,  end: -33,  reign: 16 },
  { id: 'han_cheng', name: '汉成帝',        dynasty: '西汉', start: -33,  end: -7,   reign: 26 },
  { id: 'han_ai_ping',name:'汉哀帝/平帝',   dynasty: '西汉', start: -7,   end: 6,    reign: 13 },
  { id: 'wang_mang', name: '王莽（新朝）',  dynasty: '新',   start: 9,    end: 23,   reign: 14 },

  // ── 东汉（25—220）──
  { id: 'han_guangwu',name: '汉光武帝',  dynasty: '东汉', start: 25,  end: 57,  reign: 32 },
  { id: 'han_ming',   name: '汉明帝',    dynasty: '东汉', start: 57,  end: 75,  reign: 18 },
  { id: 'han_zhang',  name: '汉章帝',    dynasty: '东汉', start: 75,  end: 88,  reign: 13 },
  { id: 'han_he',     name: '汉和帝',    dynasty: '东汉', start: 88,  end: 106, reign: 18 },
  { id: 'han_an',     name: '汉安/顺帝', dynasty: '东汉', start: 106, end: 144, reign: 38 },
  { id: 'han_huan',   name: '汉桓帝',    dynasty: '东汉', start: 146, end: 168, reign: 22 },
  { id: 'han_ling',   name: '汉灵帝',    dynasty: '东汉', start: 168, end: 189, reign: 21 },
  { id: 'han_xian',   name: '汉献帝',    dynasty: '东汉', start: 189, end: 220, reign: 31 },

  // ── 三国·魏（220—265）──
  { id: 'wei_caopi',  name: '魏文帝（曹丕）',dynasty: '三国·魏', start: 220, end: 226, reign: 6  },
  { id: 'wei_caorui', name: '魏明帝',        dynasty: '三国·魏', start: 226, end: 239, reign: 13 },
  { id: 'wei_late',   name: '魏后三帝',      dynasty: '三国·魏', start: 239, end: 265, reign: 26 },

  // ── 西晋（265—316）──
  { id: 'jin_wu',  name: '晋武帝（司马炎）',dynasty: '西晋', start: 265, end: 290, reign: 25 },
  { id: 'jin_hui', name: '晋惠帝',          dynasty: '西晋', start: 290, end: 307, reign: 17 },
  { id: 'jin_min', name: '晋怀/愍帝',       dynasty: '西晋', start: 307, end: 316, reign: 9  },

  // ── 东晋（317—420）──
  { id: 'jin_yuan',  name: '晋元帝',   dynasty: '东晋', start: 317, end: 323, reign: 6  },
  { id: 'jin_ming',  name: '晋明/成/康帝',dynasty: '东晋',start: 323, end: 361, reign: 38 },
  { id: 'jin_mu',    name: '晋穆/哀帝',dynasty: '东晋', start: 361, end: 373, reign: 12 },
  { id: 'jin_xiao',  name: '晋孝武帝', dynasty: '东晋', start: 373, end: 396, reign: 23 },
  { id: 'jin_an',    name: '晋安/恭帝',dynasty: '东晋', start: 396, end: 420, reign: 24 },

  // ── 南朝·宋（420—479）──
  { id: 'liu_wu',  name: '宋武帝（刘裕）',dynasty: '南朝·宋', start: 420, end: 422, reign: 2  },
  { id: 'liu_wen', name: '宋文帝',        dynasty: '南朝·宋', start: 424, end: 453, reign: 29 },
  { id: 'liu_xiao',name: '宋孝武/明帝',   dynasty: '南朝·宋', start: 453, end: 479, reign: 26 },

  // ── 南朝·齐（479—502）──
  { id: 'qi_gao',  name: '南齐高/武帝',dynasty: '南朝·齐', start: 479, end: 493, reign: 14 },
  { id: 'qi_late', name: '南齐后期',   dynasty: '南朝·齐', start: 493, end: 502, reign: 9  },

  // ── 南朝·梁（502—557）──
  { id: 'liang_wu',  name: '梁武帝（萧衍）',dynasty: '南朝·梁', start: 502, end: 549, reign: 47 },
  { id: 'liang_late',name: '梁简/元/敬帝', dynasty: '南朝·梁', start: 549, end: 557, reign: 8  },

  // ── 南朝·陈（557—589）──
  { id: 'chen_wu',   name: '陈武/文帝',dynasty: '南朝·陈', start: 557, end: 566, reign: 9  },
  { id: 'chen_xuan', name: '陈宣帝',  dynasty: '南朝·陈', start: 569, end: 583, reign: 14 },
  { id: 'chen_hou',  name: '陈后主',  dynasty: '南朝·陈', start: 583, end: 589, reign: 6  },

  // ── 隋朝（581—618）──
  { id: 'sui_wen',  name: '隋文帝（杨坚）',dynasty: '隋', start: 581, end: 604, reign: 23 },
  { id: 'sui_yang', name: '隋炀帝（杨广）',dynasty: '隋', start: 604, end: 618, reign: 14 },

  // ── 唐朝（618—907）──
  { id: 'tang_gaozu',   name: '唐高祖（李渊）', dynasty: '唐', start: 618, end: 626, reign: 8  },
  { id: 'tang_taizong', name: '唐太宗（李世民）',dynasty: '唐', start: 626, end: 649, reign: 23 },
  { id: 'tang_gaozong', name: '唐高宗',          dynasty: '唐', start: 649, end: 683, reign: 34 },
  { id: 'tang_wu_pre',  name: '唐中/睿宗（前）', dynasty: '唐', start: 684, end: 690, reign: 6  },
  { id: 'tang_wuzetian',name: '武则天（周）',     dynasty: '唐', start: 690, end: 705, reign: 15 },
  { id: 'tang_wu_post', name: '唐中/睿宗（后）', dynasty: '唐', start: 705, end: 712, reign: 7  },
  { id: 'tang_xuanzong',name: '唐玄宗（李隆基）',dynasty: '唐', start: 712, end: 756, reign: 44 },
  { id: 'tang_suzong',  name: '唐肃宗',          dynasty: '唐', start: 756, end: 762, reign: 6  },
  { id: 'tang_daizong', name: '唐代宗',          dynasty: '唐', start: 762, end: 779, reign: 17 },
  { id: 'tang_dezong',  name: '唐德宗',          dynasty: '唐', start: 779, end: 805, reign: 26 },
  { id: 'tang_xianzong',name: '唐宪宗',          dynasty: '唐', start: 805, end: 820, reign: 15 },
  { id: 'tang_muzong',  name: '唐穆/敬/文/武宗', dynasty: '唐', start: 820, end: 846, reign: 26 },
  { id: 'tang_xuanzong2',name:'唐宣宗',          dynasty: '唐', start: 846, end: 859, reign: 13 },
  { id: 'tang_yizong',  name: '唐懿宗',          dynasty: '唐', start: 859, end: 873, reign: 14 },
  { id: 'tang_xizong',  name: '唐僖/昭/哀宗',    dynasty: '唐', start: 873, end: 907, reign: 34 },

  // ── 五代十国（907—960）──
  { id: 'wudai_1', name: '后梁/后唐',   dynasty: '五代', start: 907, end: 936, reign: 29 },
  { id: 'wudai_2', name: '后晋/后汉/后周',dynasty: '五代',start: 936, end: 960, reign: 24 },

  // ── 北宋（960—1127）──
  { id: 'song_taizu',   name: '宋太祖（赵匡胤）',dynasty: '北宋', start: 960,  end: 976,  reign: 16 },
  { id: 'song_taizong', name: '宋太宗',          dynasty: '北宋', start: 976,  end: 997,  reign: 21 },
  { id: 'song_zhenzong',name: '宋真宗',          dynasty: '北宋', start: 997,  end: 1022, reign: 25 },
  { id: 'song_renzong', name: '宋仁宗',          dynasty: '北宋', start: 1022, end: 1063, reign: 41 },
  { id: 'song_yingzong',name: '宋英宗',          dynasty: '北宋', start: 1063, end: 1067, reign: 4  },
  { id: 'song_shenzong',name: '宋神宗',          dynasty: '北宋', start: 1067, end: 1085, reign: 18 },
  { id: 'song_zhezong', name: '宋哲宗',          dynasty: '北宋', start: 1085, end: 1100, reign: 15 },
  { id: 'song_huizong', name: '宋徽宗',          dynasty: '北宋', start: 1100, end: 1125, reign: 25 },
  { id: 'song_qinzong', name: '宋钦宗',          dynasty: '北宋', start: 1125, end: 1127, reign: 2  },

  // ── 南宋（1127—1279）──
  { id: 'song_gaozong', name: '宋高宗（南宋立国）',dynasty: '南宋', start: 1127, end: 1162, reign: 35 },
  { id: 'song_xiaozong',name: '宋孝宗',           dynasty: '南宋', start: 1162, end: 1189, reign: 27 },
  { id: 'song_guangzong',name:'宋光宗',            dynasty: '南宋', start: 1189, end: 1194, reign: 5  },
  { id: 'song_ningzong',name: '宋宁宗',            dynasty: '南宋', start: 1194, end: 1224, reign: 30 },
  { id: 'song_lizong',  name: '宋理宗',            dynasty: '南宋', start: 1224, end: 1264, reign: 40 },
  { id: 'song_duzong',  name: '宋度/恭/端帝',      dynasty: '南宋', start: 1264, end: 1279, reign: 15 },

  // ── 元朝（1271—1368）──
  { id: 'yuan_shizu',   name: '元世祖（忽必烈）',dynasty: '元', start: 1271, end: 1294, reign: 23 },
  { id: 'yuan_chengzu', name: '元成宗',          dynasty: '元', start: 1294, end: 1307, reign: 13 },
  { id: 'yuan_mid',     name: '元武/仁/英/泰定帝',dynasty:'元', start: 1307, end: 1328, reign: 21 },
  { id: 'yuan_wenzong', name: '元文/宁宗',       dynasty: '元', start: 1328, end: 1333, reign: 5  },
  { id: 'yuan_shundi',  name: '元顺帝（惠宗）',  dynasty: '元', start: 1333, end: 1368, reign: 35 },

  // ── 明朝（1368—1644）──
  { id: 'ming_taizu',   name: '明太祖（朱元璋）',dynasty: '明', start: 1368, end: 1398, reign: 30 },
  { id: 'ming_huidi',   name: '明惠帝（建文）',  dynasty: '明', start: 1398, end: 1402, reign: 4  },
  { id: 'ming_chengzu', name: '明成祖（朱棣）',  dynasty: '明', start: 1402, end: 1424, reign: 22 },
  { id: 'ming_renzong', name: '明仁/宣宗',       dynasty: '明', start: 1424, end: 1435, reign: 11 },
  { id: 'ming_yingzong',name: '明英/代宗',       dynasty: '明', start: 1435, end: 1464, reign: 29 },
  { id: 'ming_xianzong',name: '明宪宗',          dynasty: '明', start: 1464, end: 1487, reign: 23 },
  { id: 'ming_xiaozong',name: '明孝宗',          dynasty: '明', start: 1487, end: 1505, reign: 18 },
  { id: 'ming_wuzong',  name: '明武宗',          dynasty: '明', start: 1505, end: 1521, reign: 16 },
  { id: 'ming_shizong', name: '明世宗（嘉靖）',  dynasty: '明', start: 1521, end: 1567, reign: 46 },
  { id: 'ming_muzong',  name: '明穆宗',          dynasty: '明', start: 1567, end: 1572, reign: 5  },
  { id: 'ming_shenzong',name: '明神宗（万历）',  dynasty: '明', start: 1572, end: 1620, reign: 48 },
  { id: 'ming_xizong',  name: '明光/熹宗',       dynasty: '明', start: 1620, end: 1627, reign: 7  },
  { id: 'ming_sizong',  name: '明思宗（崇祯）',  dynasty: '明', start: 1627, end: 1644, reign: 17 },

  // ── 清朝（1644—1912）──
  { id: 'qing_shunzhi',  name: '清世祖（顺治）', dynasty: '清', start: 1644, end: 1661, reign: 17 },
  { id: 'qing_kangxi',   name: '清圣祖（康熙）', dynasty: '清', start: 1661, end: 1722, reign: 61 },
  { id: 'qing_yongzheng',name: '清世宗（雍正）', dynasty: '清', start: 1722, end: 1735, reign: 13 },
  { id: 'qing_qianlong', name: '清高宗（乾隆）', dynasty: '清', start: 1735, end: 1796, reign: 61 },
  { id: 'qing_jiaqing',  name: '清仁宗（嘉庆）', dynasty: '清', start: 1796, end: 1820, reign: 24 },
  { id: 'qing_daoguang', name: '清宣宗（道光）', dynasty: '清', start: 1820, end: 1850, reign: 30 },
  { id: 'qing_xianfeng', name: '清文宗（咸丰）', dynasty: '清', start: 1850, end: 1861, reign: 11 },
  { id: 'qing_tongzhi',  name: '清穆宗（同治）', dynasty: '清', start: 1861, end: 1875, reign: 14 },
  { id: 'qing_guangxu',  name: '清德宗（光绪）', dynasty: '清', start: 1875, end: 1908, reign: 33 },
  { id: 'qing_xuantong', name: '清宣统（退位）',  dynasty: '清', start: 1908, end: 1912, reign: 4  },
];

module.exports = { EMPERORS, CHINA_BASE_RGB, CHINA_TEXT, DYNASTY_BG_ALPHA };
