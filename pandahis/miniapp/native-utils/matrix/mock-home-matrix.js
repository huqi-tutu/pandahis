/**
 * 历史图谱 · 首页矩阵数据  v6
 *
 * 核心规则：
 *   1. 时间轴以华夏朝代为全局参考刻度（永远显示，不随文明切换改变）
 *   2. 展开/收起：仅华夏文明，按钮在时间轴朝代名右侧（↓可展 ↑已展）
 *   3. 同一 dynasty 字段的多政权 → 固定 N 列均分，未活跃政权留空占位
 *   4. 战国/十六国/南北朝/五代十国/南明 → 始终合并为一张时代卡片（不收展拆分）
 *
 * 算法：
 *   ① 预建"朝代组"：同一文明下 dynasty 字段相同的条目归为一组（并列列槽）
 *      抽屉收展组：王朝表 dynasty2 / dynasty_zy（与轴标 dynastyKey 对齐）
 *   ② 扫描线（华夏边界 ∪ 选中文明边界）→ 时间切片 → 合并相邻同集切片
 *   ③ 并列时期按固定列槽分区（如三国魏/蜀/吴左中右）；单独存在时 100% 宽
 */

const LOCAL_DYNASTY_RAW = require('./dynasty-data.js')
const LOCAL_EMPEROR_RAW = require('./emperor-data.js')
const { getMatrixHighlights } = require('./matrix-highlights.js')

// ─── 文明 Tab 配置 ───────────────────────────────────────────────
const CIV_TABS = [
  { id: 'huaxia',         name: '华夏',     img: '/配图/文明tab配图/01_华夏.png'   },
  { id: 'chaoxian',       name: '朝鲜',     img: '/配图/文明tab配图/02_朝鲜.png'   },
  { id: 'japan',          name: '日本',     img: '/配图/文明tab配图/03_日本.png'   },
  { id: 'sea',            name: '东南亚',   img: '/配图/文明tab配图/04_东南亚.png' },
  { id: 'centralasia',    name: '中亚',     img: '/配图/文明tab配图/05_中亚.png'   },
  { id: 'northasia',      name: '北亚游牧', img: '/配图/文明tab配图/06_北亚.png'   },
  { id: 'southasia',      name: '南亚',     img: '/配图/文明tab配图/07_南亚.png'   },
  { id: 'westasia',       name: '西亚',     img: '/配图/文明tab配图/08_西亚.png'   },
  { id: 'northafrica',    name: '北非',     img: '/配图/文明tab配图/13_北非.png'   },
  { id: 'southeu',        name: '南欧',     img: '/配图/文明tab配图/09_南欧.png'   },
  { id: 'easteu',         name: '东欧',     img: '/配图/文明tab配图/10_东欧.png'   },
  { id: 'westeu',         name: '西欧',     img: '/配图/文明tab配图/11_西欧.png'   },
  { id: 'northeu',        name: '北欧',     img: '/配图/文明tab配图/12_北欧.png'   },
  { id: 'westafrica',     name: '西非',     img: '/配图/文明tab配图/14_西非.png'   },
  { id: 'eastafrica',     name: '东非',     img: '/配图/文明tab配图/15_东非.png'   },
  { id: 'centralamerica', name: '中美',     img: '/配图/文明tab配图/16_中美.png'   },
  { id: 'northamerica',   name: '北美',     img: '/配图/文明tab配图/17_北美.png'   },
  { id: 'southamerica',   name: '南美',     img: '/配图/文明tab配图/18_南美.png'   },
]

const initialCiv = 'huaxia'
const CIV_ID_TO_NAME = {}
CIV_TABS.forEach(c => { CIV_ID_TO_NAME[c.id] = c.name })

const regimeEra = require('./regime-era-layout.js')

// ─── 朝代色（6 色按起始时间顺序轮流）──────────────────────────────
// 取自 小程序/pages/index 的文明配色（中华红/亚洲橙/欧洲蓝/美洲绿/非洲紫/金）。
// 原方案用于深色底（饱和度高）；home 为白底，故卡片背景取柔和浅色调，
// 边框/填充用 index 原色作点缀，符合低饱和、文艺的设计基调。
const ERA_COLORS = [
  { cardBg: '#F3D9D9', tagBorder: '#D45050', fill: '#E7B4B4', leftBorder: '#D45050' }, // 中华红
  { cardBg: '#F6E4CD', tagBorder: '#D4882A', fill: '#EDC999', leftBorder: '#D4882A' }, // 亚洲橙
  { cardBg: '#DBE5F5', tagBorder: '#4A80D0', fill: '#B6C9EC', leftBorder: '#4A80D0' }, // 欧洲蓝
  { cardBg: '#D6ECDF', tagBorder: '#3A9A60', fill: '#AED9C0', leftBorder: '#3A9A60' }, // 美洲绿
  { cardBg: '#ECDDF4', tagBorder: '#B875D5', fill: '#DABEE9', leftBorder: '#B875D5' }, // 非洲紫
  { cardBg: '#F6EDCD', tagBorder: '#D4AA20', fill: '#EBDA98', leftBorder: '#D4AA20' }, // 金
]

function getEraColor(colorIdx) {
  return ERA_COLORS[colorIdx % ERA_COLORS.length]
}

/** 各文明内按政权起始时间排序，从 0 起轮流使用 ERA_COLORS（不改列表顺序，只改 colorIdx） */
function assignCivilizationColorIndices(civName) {
  const list = DYNASTIES_BY_CIV[civName]
  if (!list || !list.length) return
  const ordered = list.slice().sort((a, b) =>
    a.start - b.start || a.end - b.end || String(a.name).localeCompare(String(b.name), 'zh-CN')
  )
  const colorById = {}
  ordered.forEach((dyn, i) => {
    colorById[dyn.id] = i % ERA_COLORS.length
  })
  list.forEach(dyn => {
    dyn.colorIdx = colorById[dyn.id] != null ? colorById[dyn.id] : 0
  })
}

// ─── 帝王表 dynasty2 → 王朝表 name 映射 ─────────────────────────
const EMP_REGIME_REMAP = {
  '五代·后梁': '后梁', '五代·后唐': '后唐', '五代·后晋': '后晋',
  '五代·后汉': '后汉', '五代·后周': '后周',
  '十国·吴':   '十国', '十国·南平': '十国', '十国·北汉': '十国',
  '十国·后蜀': '十国', '十国·前蜀': '十国', '十国·南唐': '十国',
  '十国·南汉': '十国', '十国·吴越': '十国', '十国·闽':   '十国',
  '南朝':     '南朝·宋',
}

function getEmperorRegimeKey(e) {
  const raw = e.dynasty2 || e.dynasty
  return EMP_REGIME_REMAP[raw] || raw
}

/** legacy 矩阵补丁 id → 新 canonical id（政权ID / 帝王ID） */
let ENTRY_ID_BY_LEGACY = {}

function resolveEntryId(ref) {
  if (!ref) return ref
  return ENTRY_ID_BY_LEGACY[ref] || ref
}

function registerLegacyIds(records) {
  ;(records || []).forEach(r => {
    if (r && r.legacyId) ENTRY_ID_BY_LEGACY[r.legacyId] = r.id
  })
}

function entryIdsMatch(entryId, ref) {
  if (!entryId || !ref) return false
  return entryId === ref || entryId === resolveEntryId(ref)
}

function entryIdInSet(entryId, setOrArr) {
  const items = setOrArr instanceof Set ? [...setOrArr] : setOrArr
  return items.some(ref => entryIdsMatch(entryId, ref))
}

// ─── 年份解析 ─────────────────────────────────────────────────────
function parseYear(str) {
  if (!str) return 0
  const s = String(str).trim().replace('约', '')
  if (s === '至今') return 2025
  const cm = s.match(/^(-?)(\d+)世纪$/)
  if (cm) {
    const neg = cm[1] === '-', c = parseInt(cm[2])
    return neg ? -(c * 100 - 50) : (c - 1) * 100 + 50
  }
  const n = parseInt(s)
  return isNaN(n) ? 0 : n
}

function fmtYear(y) {
  if (y < 0)  return `前${Math.abs(y)}`
  if (y === 0) return '公元0'
  return String(y)
}

/** 时间轴年份：负数用「-」前缀，比「前」更省列宽 */
function fmtTimelineYear(y) {
  if (y < 0)  return `-${Math.abs(y)}`
  if (y === 0) return '公元0'
  return String(y)
}

/** 起止年份展示（保留「约」「至今」，负数统一为「前X」） */
function fmtRange(start, end, startStr, endStr) {
  const approxS = startStr && String(startStr).includes('约')
  const approxE = endStr && String(endStr).includes('约')
  const s = (approxS ? '约' : '') + fmtYear(start)
  let e
  if (endStr === '至今' || endStr === '今') {
    e = '至今'
  } else {
    e = (approxE ? '约' : '') + fmtYear(end)
  }
  return `${s} — ${e}`
}

/** 按同时期政权数选择标签排版：单政权横排 | 多政权名称下左对齐 */
function inferLabelLayout(concurrentCount) {
  return (concurrentCount || 1) <= 1 ? 'inline' : 'stacked'
}

const THREE_KINGDOMS_MIN = {
  '三国·魏': 5,
  '三国·蜀': 2,
  '三国·吴': 4,
}

/** 首页矩阵不展示的帝王（如未正式称帝、追封庙号者） */
const MATRIX_EXCLUDED_EMPEROR_IDS = new Set([
  'zhong_hua_wei_cao_cao', // 曹操：魏武帝为曹丕追封，生前未称帝
  'DW_HX_SANGUO_SANGUOWEI_CAOCAO',
])

function isExcludedEmperor(e) {
  if (!e || !e.id) return true
  if (MATRIX_EXCLUDED_EMPEROR_IDS.has(e.id)) return true
  if (e.legacyId && MATRIX_EXCLUDED_EMPEROR_IDS.has(e.legacyId)) return true
  return false
}

function countEmperorsByRegime(emperorRaw) {
  const counts = {}
  ;(emperorRaw || []).forEach(e => {
    const k = getEmperorRegimeKey(e)
    counts[k] = (counts[k] || 0) + 1
  })
  return counts
}

function isThreeKingdomsComplete(emperorRaw) {
  const counts = countEmperorsByRegime(emperorRaw)
  return Object.entries(THREE_KINGDOMS_MIN).every(([k, min]) => (counts[k] || 0) >= min)
}

function normalizeEmperorTag(raw) {
  if (raw == null || raw === '' || raw === '-') return ''
  return String(raw).trim()
}

/** 本地优先：同 id 以 bundled 数据为准，云数据仅补充本地缺失条目 */
function mergeEmperorRecords(local, incoming) {
  const byId = {}
  ;(incoming || []).forEach(e => { if (e && e.id) byId[e.id] = e })
  ;(local || []).forEach(e => { if (e && e.id) byId[e.id] = e })
  return Object.values(byId)
}

function mergeDynastyRecords(local, incoming) {
  const byId = {}
  ;(incoming || []).forEach(d => { if (d && d.id) byId[d.id] = d })
  ;(local || []).forEach(d => { if (d && d.id) byId[d.id] = d })
  return Object.values(byId)
}

/** 胶囊标签：统一底色 + 无边框（字色由 wxss 统一控制） */
function buildHighlightTagList(labels) {
  const list = (labels || []).slice(0, 2).filter(Boolean)
  if (!list.length) return []
  return list.map(text => ({
    text,
    tagStyle: 'background-color:#B0A89E;border:none;',
  }))
}

/** 画布内容区参考宽度（750 - 时间轴 - inner 左右边距） */
const MATRIX_CANVAS_INNER_RPX = 634

/** 卡片右上角时间字号：按色块全宽自适应，保证完整显示 */
function fitCardTimeFontSize(timeRange, widthPct) {
  const s = String(timeRange || '')
  if (!s) return 16
  let units = 0
  for (const ch of s) {
    units += (ch >= '0' && ch <= '9') ? 0.58 : 1
  }
  const cardW = Math.max(40, (widthPct / 100) * MATRIX_CANVAS_INNER_RPX)
  const avail = cardW - LABEL_CARD_INSET * 3
  for (let fs = 16; fs >= 8; fs--) {
    if (units * fs * 0.62 <= avail) return fs
  }
  return 8
}

// ─── 高度计算 ─────────────────────────────────────────────────────
// 卡片参考（帝王展开等场景仍可用）
const CARD_H_MIN_RPX = 80
const CARD_H_MAX_RPX = 200
const DYN_H_REF_YEARS = 600
const EMP_H_REF_YEARS = 71

// 时间轴行高：按切片实际年数线性映射（保证色块随存续时长变高）
const SLICE_RPX_PER_YEAR = 2.8   // 1 年 ≈ 2.8rpx（375 屏约 1.4px）
const SLICE_H_MIN_RPX    = 108   // 最短切片 +10px
const SLICE_H_MAX_RPX    = 360   // 单段上限 180px，超长时期封顶
const BLOCK_H_GAP_PCT    = 3.2   // 不同色块水平间距（占画布 %，≈20rpx）
const BLOCK_V_GAP_RPX    = 16     // 不同色块垂直间距（8px，同 entry 多段无缝）
/** 画布内层可用宽度（750 设计稿：屏宽 - 时间列 84 - 内边距 12/20） */
const MATRIX_CANVAS_USABLE_RPX = 750 - 84 - 12 - 20
/** 16rpx 水平间距 → 占画布内层 % */
function calcBlockHGapPct() {
  return (BLOCK_V_GAP_RPX / MATRIX_CANVAS_USABLE_RPX) * 100
}
/** solid-seam 填充微扩（与 home-matrix.wxss 一致），用于换算可见间距 */
const SOLID_SEAM_BLEED_V_RPX = 4
const SOLID_SEAM_BLEED_H_RPX = 3
/** 色块几何间距：保证填充微扩后可见仍为 16rpx */
function calcVisualVBoxGapRpx() {
  return BLOCK_V_GAP_RPX + SOLID_SEAM_BLEED_V_RPX * 2
}
function calcVisualHBoxGapPct() {
  return ((BLOCK_V_GAP_RPX + SOLID_SEAM_BLEED_H_RPX * 2) / MATRIX_CANVAS_USABLE_RPX) * 100
}
const BLOCK_MIN_SEG_H    = 52    // 段最小高度 +10px
const COMPRESSED_EMPEROR_SLICE_H_MIN_RPX = 92  // 压缩阶段内并列帝王卡片最低行高 +10px
const HEADER_TOP_INSET = 8      // 标签层与色块顶缘间距（配合 wrap padding）
const LABEL_CARD_INSET = 8      // 名称/时间与色块边缘间距
const TIME_CARD_INSET = LABEL_CARD_INSET
const BLOCK_RADIUS_RPX = 10
/** 时间轴年份最小纵向间距（过密则跳过中间年份，朝代起点始终显示） */
const TIME_YEAR_LABEL_MIN_GAP_RPX = 280

/** 色块上不展示文字标签（保留左侧色条与底色） */
const HIDE_LABEL_ENTRY_IDS = new Set([])

/** 仅隐藏顶栏标签 chip，保留帝王名与在位时间 */
const HIDE_TAG_ENTRY_IDS = new Set([
  'zhong_hua_jin_si_ma_de_wen', // 晋恭帝
])

/** 色块上不展示在位时间 */
const HIDE_TIME_ENTRY_IDS = new Set([
  'zhong_hua_nan_zhao_mo_zhu', // 南诏孝哀帝
])

/** 不规则 L 形仍锚定右下角（默认不规则形用左下角） */
const TIME_CORNER_BR_IRREGULAR = new Set(['zhong_hua_yuan_hu_lie'])

function calcCardH(years, refMaxYears) {
  const y = Math.max(1, Math.min(Number(years) || 1, refMaxYears))
  const span = CARD_H_MAX_RPX - CARD_H_MIN_RPX
  return Math.max(
    CARD_H_MIN_RPX,
    Math.min(CARD_H_MAX_RPX, Math.round(CARD_H_MIN_RPX + (y / refMaxYears) * span))
  )
}

function calcDynH(years) {
  return calcCardH(years, DYN_H_REF_YEARS)
}

function calcEmpH(years) {
  return calcCardH(years, EMP_H_REF_YEARS)
}

/** 抽屉收展组键：王朝表 dynasty2 / dynasty_zy，与 HUAXIA_AXIS_MARKS.dynastyKey 对齐 */
function getDynasty2(d) {
  return d.dynasty2 || d.dynasty_zy || d.dynasty || d.name
}

// ─── 预处理：王朝 / 帝王（支持云数据热更新）────────────────────────
let DYNASTIES_BY_CIV = {}
let DYNASTY_GROUPS = {}
let EMPERORS_BY_DYN = {}
let EMPEROR_LANES_BY_DYN = {}

function rebuildMatrixDataSources(dynastyRaw, emperorRaw) {
  DYNASTIES_BY_CIV = {}
  DYNASTY_GROUPS = {}
  ENTRY_ID_BY_LEGACY = {}
  registerLegacyIds(dynastyRaw)
  registerLegacyIds(emperorRaw)

  ;(dynastyRaw || []).forEach((d, idx) => {
    const civ = d.civilization
    if (!civ) return
    if (!DYNASTIES_BY_CIV[civ]) DYNASTIES_BY_CIV[civ] = []
    DYNASTIES_BY_CIV[civ].push({
      id:              d.id || `dyn_${idx}`,
      legacyId:        d.legacyId || '',
      name:            d.name,
      dynasty:         d.dynasty || d.name,
      dynastyId:       d.dynastyId || '',
      dynasty_zy:      d.dynasty_zy || '',
      dynasty2:        getDynasty2(d),
      civilization:    civ,
      civilizationId:  d.civilizationId || '',
      regimeId:        d.id || '',
      start:           parseYear(d.start),
      end:             parseYear(d.end),
      startStr:        d.start,
      endStr:          d.end,
      colorIdx:        0,
    })
  })

  Object.keys(DYNASTIES_BY_CIV).forEach(civName => {
    assignCivilizationColorIndices(civName)
  })

  Object.keys(DYNASTIES_BY_CIV).forEach(civName => {
    DYNASTY_GROUPS[civName] = {}
    DYNASTIES_BY_CIV[civName].forEach(dyn => {
      const g = dyn.dynasty
      if (!DYNASTY_GROUPS[civName][g]) DYNASTY_GROUPS[civName][g] = []
      DYNASTY_GROUPS[civName][g].push(dyn)
    })
    Object.values(DYNASTY_GROUPS[civName]).forEach(arr =>
      arr.sort((a, b) => a.start - b.start)
    )
  })

  const hx = DYNASTIES_BY_CIV['华夏']
  if (hx && !hx.some(d => d.name === '南明' || d.dynasty === '南明')) {
    const nm = {
      id: 'ZQ_HX_NANMING_NANMING', legacyId: 'HX-NM',
      name: '南明', dynasty: '南明', dynastyId: '', dynasty_zy: '南明',
      dynasty2: '南明', civilization: '华夏', civilizationId: 'HX', regimeId: 'ZQ_HX_NANMING_NANMING',
      start: 1644, end: 1662,
      startStr: '1644', endStr: '1662', colorIdx: 0,
    }
    hx.push(nm)
    if (!DYNASTY_GROUPS['华夏']) DYNASTY_GROUPS['华夏'] = {}
    DYNASTY_GROUPS['华夏']['南明'] = [nm]
    assignCivilizationColorIndices('华夏')
  }

  EMPERORS_BY_DYN = {}
  ;(emperorRaw || []).forEach(e => {
    if (isExcludedEmperor(e)) return
    const dyn = getEmperorRegimeKey(e)
    if (!EMPERORS_BY_DYN[dyn]) EMPERORS_BY_DYN[dyn] = []
    EMPERORS_BY_DYN[dyn].push({
      id:               e.id,
      legacyId:         e.legacyId || '',
      name:             e.name,
      originalName:     e.originalName || '',
      dynasty:          e.dynasty || dyn,
      dynastyId:        e.dynastyId || '',
      dynasty2:         e.dynasty2 || dyn,
      regimeId:         e.regimeId || '',
      civilization:     e.civilization || '',
      civilizationId:   e.civilizationId || '',
      temple:           e.temple || '',
      era:              e.era || '',
      importance:       e.importance || '',
      start:            parseInt(e.start, 10) || 0,
      end:              parseInt(e.end, 10) || 0,
      years:            parseInt(e.years, 10) || 1,
      tag:              normalizeEmperorTag(e.tag),
    })
  })
  Object.values(EMPERORS_BY_DYN).forEach(arr =>
    arr.sort((a, b) => a.start - b.start)
  )

  EMPEROR_LANES_BY_DYN = {}
  Object.keys(EMPERORS_BY_DYN).forEach(dynName => {
    const emps = EMPERORS_BY_DYN[dynName]
    if (!emps.length) return
    const lanes = []
    const byId = {}
    emps.forEach(e => {
      let lane = lanes.findIndex(end => end <= e.start)
      if (lane < 0) {
        lane = lanes.length
        lanes.push(-Infinity)
      }
      lanes[lane] = e.end
      byId[e.id] = lane
    })
    const stackTotal = Math.max(1, lanes.length)
    EMPEROR_LANES_BY_DYN[dynName] = {
      stackTotal,
      byId: Object.fromEntries(
        Object.entries(byId).map(([id, idx]) => [id, { stackIndex: idx, stackTotal }])
      ),
    }
  })

  const hxSpring = DYNASTIES_BY_CIV['华夏'] && DYNASTIES_BY_CIV['华夏'].find(d => d.name === '春秋')
  regimeEra.setRegimeEraColorIdx(hxSpring ? hxSpring.colorIdx : 0)
}

/** 注入云数据：本地 bundled 数据优先，云库仅补充本地缺失条目 */
function loadMatrixData(dynastyRaw, emperorRaw) {
  const dyn = mergeDynastyRecords(LOCAL_DYNASTY_RAW, dynastyRaw || [])
  let emp = mergeEmperorRecords(LOCAL_EMPEROR_RAW, emperorRaw || [])
  if (!isThreeKingdomsComplete(emp)) {
    emp = mergeEmperorRecords(LOCAL_EMPEROR_RAW, [])
  }
  rebuildMatrixDataSources(dyn, emp)
}

rebuildMatrixDataSources(LOCAL_DYNASTY_RAW, LOCAL_EMPEROR_RAW)

// ─── 多政权时代：始终合并为一张时代卡片（收起/展开均不拆分为政权或帝王）──
const MERGED_ERA_GROUPS = new Set([
  '十六国', '南北朝', '五代十国',
])

function isMergedEraGroup(groupName) {
  return MERGED_ERA_GROUPS.has(groupName)
}

/** 时间轴阶段压缩：整段行高缩小（色块与刻度同步，不单缩色块） */
const TIMELINE_COMPRESS_ZONES = [
  { start: -3000, end: -2070, scale: 0.8 }, // 五帝（高度等比缩小 20%）
  { start: -770, end: -221, scale: 0.55 }, // 春秋战国
  { start: 304, end: 439, scale: 0.5 },  // 十六国阶段
  { start: 386, end: 589, scale: 0.5 },  // 南北朝阶段
]

function getTimelineCompressScale(tS, tE) {
  let scale = 1
  TIMELINE_COMPRESS_ZONES.forEach(z => {
    if (tS < z.end && tE > z.start) scale = Math.min(scale, z.scale)
  })
  return scale
}

/** 将同 dynasty 组内所有政权合并为一条展示条目 */
function buildMergedEraEntry(groupName, members) {
  if (!members || members.length === 0) return null
  const start = Math.min(...members.map(m => m.start))
  const end   = Math.max(...members.map(m => m.end))
  const startMember = members.find(m => m.start === start) || members[0]
  const endMember   = members.reduce((a, b) => (b.end > a.end ? b : a), members[0])
  return {
    id:           `merged_${groupName}`,
    isEmperor:    false,
    isMergedEra:  true,
    dynastyName:  groupName,
    dynastyGroup: groupName,
    dynastyDisp:  groupName,
    displayName:  groupName,
    start,
    end,
    years:        end - start,
    colorIdx:     startMember.colorIdx,
    startStr:     startMember.startStr,
    endStr:       endMember.endStr,
  }
}
// 时间轴永远展示这些朝代的开始年份 + 名称，不随选中文明改变
const HUAXIA_AXIS_MARKS = [
  { label: '五帝',     start: -2698, dynastyKey: '五帝' },
  { label: '夏',       start: -2070, dynastyKey: '夏' },
  { label: '商',       start: -1600, dynastyKey: '商' },
  { label: '西周',     start: -1046, dynastyKey: '西周' },
  { label: '春秋',     start: -770,  dynastyKey: '春秋' },
  { label: '战国',     start: -475,  dynastyKey: '战国' },
  { label: '秦',       start: -221,  dynastyKey: '秦' },
  { label: '西汉',     start: -202,  dynastyKey: '西汉' },
  { label: '新',       start: 8,     dynastyKey: '新' },
  { label: '东汉',     start: 25,    dynastyKey: '东汉' },
  { label: '三国',     start: 220,   dynastyKey: '三国' },
  { label: '西晋',     start: 266,   dynastyKey: '西晋' },
  { label: '十六国',   start: 304,   dynastyKey: '十六国' },
  { label: '东晋',     start: 317,   dynastyKey: '东晋' },
  { label: '南北朝',   start: 386,   dynastyKey: '南北朝' },
  { label: '隋',       start: 581,   dynastyKey: '隋' },
  { label: '唐',       start: 618,   dynastyKey: '唐' },
  { label: '五代十国', start: 907,   dynastyKey: '五代十国' },
  { label: '北宋',     start: 960,   dynastyKey: '北宋' },
  { label: '南宋',     start: 1127,  dynastyKey: '南宋' },
  { label: '元',       start: 1271,  dynastyKey: '元' },
  { label: '明',       start: 1368,  dynastyKey: '明' },
  { label: '清',       start: 1636,  dynastyKey: '清' },
  { label: '民国',     start: 1912,  dynastyKey: '民国' },
  { label: '新中国',   start: 1949,  dynastyKey: '新中国' },
]

const HUAXIA_AXIS_BY_START = {}
HUAXIA_AXIS_MARKS.forEach(m => { HUAXIA_AXIS_BY_START[m.start] = m })

function getDrawerMembers(dynKey, civName) {
  const dyns = DYNASTIES_BY_CIV[civName] || []
  return dyns.filter(d => d.dynasty2 === dynKey || d.name === dynKey)
}

/** 春秋时间轴：是否展开春秋/战国各政权色块 */
function isSpringAutumnWarringExpanded(expandedDynasties, civName) {
  if (expandedDynasties['春秋'] || expandedDynasties['战国']) return true
  const names = [...getDrawerMembers('春秋', civName), ...getDrawerMembers('战国', civName)]
  return names.some(d => expandedDynasties[d.name])
}

/** 收起态：春秋+战国合并为一张全宽「春秋战国」色块 */
function buildCollapsedSpringWarringEntry() {
  const hx = DYNASTIES_BY_CIV['华夏'] || []
  const dyn = hx.find(d => d.name === '春秋')
  const start = regimeEra.SPRING_AUTUMN_START
  const end = regimeEra.WARRING_STATES_END
  return {
    id:              'collapsed_春秋战国',
    isEmperor:       false,
    isCollapsedRegimeSummary: true,
    dynastyName:     '春秋战国',
    dynastyGroup:    '春秋战国',
    displayName:     '春秋战国',
    start,
    end,
    years:           end - start,
    colorIdx:        dyn ? dyn.colorIdx : regimeEra.getRegimeEraColorIdx(),
    startStr:        String(start),
    endStr:          String(end),
  }
}

/** 时间轴朝代名是否可点击收展 */
function isTimelineExpandable(hxDynastyKey) {
  if (!hxDynastyKey) return false
  if (isMergedEraGroup(hxDynastyKey)) return false
  if (hxDynastyKey === '春秋') return true
  if (regimeEra.isRegimeOnlyEraGroup(hxDynastyKey)) return false
  return true
}

function isDynastyExpanded(dynKey, expandedDynasties, civName) {
  if (!dynKey) return false
  if (expandedDynasties[dynKey]) return true
  const members = getDrawerMembers(dynKey, civName)
  if (members.length > 1) {
    return members.some(d => expandedDynasties[d.name])
  }
  return !!expandedDynasties[dynKey]
}

function toggleDynastyExpanded(dynKey, expandedDynasties, civName) {
  const next = Object.assign({}, expandedDynasties)

  if (dynKey === '春秋') {
    const willExpand = !isSpringAutumnWarringExpanded(next, civName)
    const names = new Set()
    getDrawerMembers('春秋', civName).forEach(d => names.add(d.name))
    getDrawerMembers('战国', civName).forEach(d => names.add(d.name))
    names.forEach(name => {
      if (willExpand) next[name] = true
      else delete next[name]
    })
    if (willExpand) {
      next['春秋'] = true
      next['战国'] = true
    } else {
      delete next['春秋']
      delete next['战国']
    }
    return next
  }

  const members = getDrawerMembers(dynKey, civName)
  const willExpand = !isDynastyExpanded(dynKey, next, civName)

  if (members.length > 1) {
    members.forEach(d => {
      if (willExpand) next[d.name] = true
      else delete next[d.name]
    })
    if (willExpand) next[dynKey] = true
    else delete next[dynKey]
    return next
  }

  if (willExpand) next[dynKey] = true
  else delete next[dynKey]
  return next
}

// （帝王分组已并入 rebuildMatrixDataSources）

function getEmperorLanePlacement(e) {
  const pack = EMPEROR_LANES_BY_DYN[e.dynastyName]
  if (!pack) return { stackIndex: 0, stackTotal: 1 }
  return pack.byId[e.id] || { stackIndex: 0, stackTotal: pack.stackTotal }
}

/** 并列帝王特殊列宽（key 为排序后的 entry id 对） */
const EMPEROR_PAIR_WIDTHS = {
  'zhong_hua_ming_zhu_qi|zhong_hua_ming_zhu_qizhen': {
    zhong_hua_ming_zhu_qizhen: 1 / 6, // 明英宗（被俘/退位）
    zhong_hua_ming_zhu_qi:     5 / 6, // 明代宗（景泰实际执政）
  },
}

/** 多段色块：段间微重叠，底缘不变 */
function patchInternalSeamOverlap(segs) {
  if (segs.length < 2) return
  segs.sort((a, b) => a.top - b.top)
  for (let i = 1; i < segs.length; i++) {
    segs[i].top -= 2
    segs[i].h += 2
  }
}

/** 不规则多段色块：填充层不透明微扩 + 去掉段内描边，消段内多余线条（不改几何） */
function applyIrregularSolidSeamFix(blocks) {
  const byEntry = {}
  blocks.forEach(b => {
    if (!byEntry[b.entryId]) byEntry[b.entryId] = []
    byEntry[b.entryId].push(b)
  })

  Object.values(byEntry).forEach(segs => {
    if (!isIrregularEntryShape(segs)) return

    const real = segs.filter(s =>
      !s.isLBridge && !s.isSongHalfLBridge && !s.isNanbeiLBridge && !s.isXiaowudiBridge
    )
    real.sort((a, b) => a.top - b.top)

    segs.forEach(s => {
      s.fillSeamFix = true
      s.edgeClass = ''
      s.edgeTop = s.edgeRight = s.edgeBottom = s.edgeLeft = false
    })

    // 同 entry 内竖直接缝：该侧禁止 gap，让 fill 微扩盖住内部白线
    for (let i = 0; i < real.length - 1; i++) {
      const upper = real[i]
      const lower = real[i + 1]
      const joint = upper.top + upper.h
      if (Math.abs(lower.top - joint) <= 4 && hOverlap(upper, lower)) {
        upper.seamGapBottom = false
        lower.seamGapTop = false
      }
    }

    // L 形桥接段：四向均不 gap，仅填色
    segs.filter(s =>
      s.isLBridge || s.isSongHalfLBridge || s.isNanbeiLBridge || s.isXiaowudiBridge
    ).forEach(s => {
      s.seamGapTop = s.seamGapBottom = s.seamGapLeft = s.seamGapRight = false
    })
  })
}

/** 填充层不透明 + 微扩（指定 entry，仅消段间接缝，不改几何外边界） */
const FILL_SEAM_FIX_IDS = new Set([
  'zhong_hua_jin_si_ma_zhong',
  'zhong_hua_song_lizong',
  'zhong_hua_ming_zhu_yijun',   // 万历
  'zhong_hua_ming_zhu_qizhen',  // 明英宗
  'zhong_hua_qing_yi_zhu',      // 咸丰
  'zhong_hua_wei_cao_huan',     // 魏陈留王
  'zhong_hua_jin_si_ma_yan',    // 晋武帝
])

/** 东晋帝王上下承续：固定 16rpx 间距（仅指定 entry 对） */
function pinJinEmperorGap(blocks, upperEntryId, lowerEntryId) {
  const upper = blocks
    .filter(b => entryIdsMatch(b.entryId, upperEntryId) && !b.isLBridge && !b.isNanbeiLBridge)
    .sort((a, b) => a.top - b.top)
    .slice(-1)[0]
  const lower = blocks
    .filter(b => entryIdsMatch(b.entryId, lowerEntryId) && !b.isLBridge && !b.isNanbeiLBridge)
    .sort((a, b) => a.top - b.top)[0]
  if (!upper || !lower) return
  lower.top = upper.top + upper.h + BLOCK_V_GAP_RPX
}

/** 指定 entry 色块几何微调（仅改目标卡片，不动全局布局） */
const ENTRY_BLOCK_PATCHES = {
  /** 唐哀帝：与渤海大諲譔同宽（左列 3/6） */
  zhong_hua_tang_ai_di(segs) {
    segs.forEach(s => {
      s.leftPct = 0
      s.widthPct = 46.8
    })
  },
  /** 五代十国：宽段右缘与辽列右缘对齐 */
  'merged_五代十国'(segs) {
    segs.forEach(s => {
      if (s.widthPct >= 40) s.widthPct = 100 - s.leftPct
    })
  },
  /** 西夏惠宗：左缘与西夏崇宗对齐 */
  zhong_hua_xi_xia_hui(segs) {
    segs.forEach(s => {
      s.leftPct = 51.6
      s.widthPct = 22.6
    })
  },
  /** 晋惠帝 L 形：仅加大段间内部重叠，外边界（底缘/与十六国间距）不变 */
  zhong_hua_jin_si_ma_zhong: patchInternalSeamOverlap,
  /** 万历 / 明英宗 / 咸丰：L 形或多段，段间接缝 */
  zhong_hua_ming_zhu_yijun: patchInternalSeamOverlap,
  zhong_hua_ming_zhu_qizhen: patchInternalSeamOverlap,
  zhong_hua_qing_yi_zhu: patchInternalSeamOverlap,
}

function applyEntryBlockPatches(blocks) {
  const byEntry = {}
  blocks.forEach(b => {
    if (b.isLBridge || b.isSongHalfLBridge) return
    if (!byEntry[b.entryId]) byEntry[b.entryId] = []
    byEntry[b.entryId].push(b)
  })
  Object.entries(ENTRY_BLOCK_PATCHES).forEach(([entryId, patch]) => {
    const segs = byEntry[resolveEntryId(entryId)] || byEntry[entryId]
    if (segs) patch(segs)
  })
  // 宋理宗：下段已覆盖桥接区，去掉冗余桥接块（消除右上角半透明叠色）
  for (let i = blocks.length - 1; i >= 0; i--) {
    if (entryIdsMatch(blocks[i].entryId, 'zhong_hua_song_lizong') && blocks[i].isSongHalfLBridge) {
      blocks.splice(i, 1)
    }
  }
  // 魏陈留王：右段/桥接底缘与左臂对齐，消右下 protrusion
  const weiSegs = blocks.filter(b => entryIdsMatch(b.entryId, 'zhong_hua_wei_cao_huan'))
  const weiLeft = weiSegs.find(b => !b.isLBridge && b.leftPct < 1)
  if (weiLeft) {
    const targetBottom = weiLeft.top + weiLeft.h
    weiSegs.forEach(b => {
      if (b === weiLeft) return
      const excess = b.top + b.h - targetBottom
      if (excess > 0.5) b.h = Math.max(BLOCK_MIN_SEG_H, b.h - excess)
    })
  }
  // 魏陈留王：桥接段与右段合并，消列间距处白色竖线（仅本 entry 有 isLBridge）
  const weiBridgeIdx = blocks.findIndex(b =>
    entryIdsMatch(b.entryId, 'zhong_hua_wei_cao_huan') && b.isLBridge
  )
  if (weiBridgeIdx >= 0) {
    const bridge = blocks[weiBridgeIdx]
    const weiRight = blocks.find(b =>
      entryIdsMatch(b.entryId, 'zhong_hua_wei_cao_huan') && !b.isLBridge && b.leftPct > weiLeft.leftPct + 0.5
    )
    if (weiRight) {
      weiRight.leftPct = bridge.leftPct
      weiRight.widthPct = bridge.widthPct + weiRight.widthPct
      weiRight.top -= 2
      weiRight.h += 2
      blocks.splice(weiBridgeIdx, 1)
    }
  }
  // 魏陈留王：右段向左微扩，与左臂填色重叠，消 L 形内角白色竖线
  const weiRight = weiSegs.find(b => weiLeft && b !== weiLeft && !b.isLBridge)
  if (weiRight) {
    weiRight.leftPct -= 1.5
    weiRight.widthPct += 1.5
  }
  blocks.forEach(b => {
    if (entryIdInSet(b.entryId, FILL_SEAM_FIX_IDS)) b.fillSeamFix = true
  })
  pinJinEmperorGap(blocks, 'zhong_hua_jin_si_ma_ye', 'zhong_hua_jin_si_ma_rui')
  pinJinEmperorGap(blocks, 'zhong_hua_jin_si_ma_rui', 'zhong_hua_jin_si_ma_shao')
  pinJinEmperorGap(blocks, 'zhong_hua_jin_si_ma_shao', 'zhong_hua_jin_si_ma_yan_cheng')
  // 晋武帝：上段加宽至与陈留王右缘齐平 + 右肩 L 桥（仅本 entry）
  const yanSegs = blocks.filter(b =>
    b.entryId === resolveEntryId('zhong_hua_jin_si_ma_yan') && !b.isLBridge
  )
  if (yanSegs.length >= 2 && weiRight) {
    yanSegs.sort((a, b) => a.top - b.top)
    const upper = yanSegs[0]
    const lower = yanSegs[yanSegs.length - 1]
    const targetRight = weiRight.leftPct + weiRight.widthPct
    if (lower.widthPct > upper.widthPct + 5) {
      upper.widthPct = Math.max(upper.widthPct, targetRight - upper.leftPct)
      upper.h += 4
      lower.top -= 2
      lower.h += 2
      const joint = upper.top + upper.h
      const bridgeW = lower.widthPct - upper.widthPct
      if (bridgeW > 0.5 && Math.abs(lower.top - joint) <= 8) {
        blocks.push(Object.assign({}, lower, {
          id:            `${resolveEntryId('zhong_hua_jin_si_ma_yan')}_ybridge_${joint}`,
          entryId:       resolveEntryId('zhong_hua_jin_si_ma_yan'),
          leftPct:       upper.leftPct + upper.widthPct,
          widthPct:      bridgeW,
          top:           joint - 2,
          h:             Math.max(BLOCK_MIN_SEG_H, lower.top - joint + 4),
          isLBridge:     true,
          fillSeamFix:   true,
          radiusStyle:   '0 0 0 0',
          edgeClass:     '',
        }))
      }
    }
  }
}

/** 按自定义比例分配并列帝王宽度；不匹配则返回 null */
function assignWeightedEmperorPairPlacements(emperors) {
  if (emperors.length !== 2) return null
  const idKey = emperors.map(e => e.id).sort().join('|')
  const legacyKey = emperors.map(e => e.legacyId || e.id).sort().join('|')
  const weights = EMPEROR_PAIR_WIDTHS[idKey] || EMPEROR_PAIR_WIDTHS[legacyKey]
  if (!weights) return null

  const G = BLOCK_H_GAP_PCT
  const usable = 100 - G
  const ordered = [...emperors].sort(
    (a, b) => getEmperorLanePlacement(a).stackIndex - getEmperorLanePlacement(b).stackIndex
  )
  let left = 0
  return ordered.map((e, i) => {
    const widthPct = usable * weights[e.id]
    const pl = makePlacement(e, left, widthPct, i, 2)
    left += widthPct + (i < ordered.length - 1 ? G : 0)
    return pl
  })
}

// ─── slot / block 构造 ───────────────────────────────────────────
function entryToCardFields(e, civId) {
  const era = getEraColor(e.isRegimeOnly ? regimeEra.getRegimeEraColorIdx() : e.colorIdx)
  const timeRange = fmtRange(e.start, e.end, e.startStr, e.endStr)
  const colors = {
    leftBorder: era.leftBorder,
    cardBg:     era.cardBg,
    fillColor:  era.fill,
  }
  if (e.isRegimeOnly) {
    const label = regimeEra.getRegimeDisplayName(e.dynastyName)
    return Object.assign({
      kind: 'dynasty',
      dynasty: label,
      displayName: label,
      timeRange: '',
      civ: civId,
      anchorYear: e.start,
      highlights: [],
      hideTime: true,
    }, colors)
  }
  const highlights = buildHighlightTagList(getMatrixHighlights(e))
  if (e.isEmperor) {
    return Object.assign({
      kind: 'single', person: e.displayName, dynasty: e.dynastyName,
      entityType: 'emperor',
      entityId: e.id,
      regimeId: e.regimeId || '',
      dynastyId: e.dynastyId || '',
      civilizationId: e.civilizationId || '',
      originalName: e.originalName || '',
      timeRange, civ: civId,
      anchorYear: Math.round((e.start + e.end) / 2),
      highlights,
    }, colors)
  }
  return Object.assign({
    kind: 'dynasty', dynasty: e.dynastyName, displayName: e.displayName,
    entityType: 'regime',
    entityId: e.id,
    regimeId: e.regimeId || e.id || '',
    dynastyId: e.dynastyId || '',
    civilizationId: e.civilizationId || '',
    timeRange, civ: civId,
    anchorYear: e.start,
    highlights,
  }, colors)
}

// ─── 并列时期：固定列槽分区 ───────────────────────────────────────
// 从分区起点起画布按 slots 均分；各政权/帝王固定一列，未起始或已结束则留白
const PARALLEL_ZONES = [
  // 200–280 始终三列：左魏/晋、中蜀、右吴（各占 1/3，未立国则留白）
  { start: 200,  end: 280,  slots: ['三国·魏', '三国·蜀', '三国·吴'] },
  // 304–386：晋 2/3 + 十六国 1/3
  { start: 304, end: 386, slots: ['__jin__', '十六国'], weights: [2, 1] },
  // 386–420：南北朝 | 晋 | 十六国 三等分（重合期）
  { start: 386, end: 420, slots: ['南北朝', '__jin__', '十六国'], weights: [1, 1, 1] },
  // 420–439：南北朝 2/3 + 十六国 1/3
  { start: 420, end: 439, slots: ['南北朝', '十六国'], weights: [2, 1] },
  // 581–589：隋文帝左、南北朝右
  { start: 581,  end: 589,  slots: ['隋', '南北朝'], weights: [1, 1] },
  { start: 960,  end: 1127, slots: ['北宋', '辽', '西夏'] },
  // 1100 宋徽宗起：宋·金·西夏·辽 四等分（金 1115 年起占第 2 列）
  { start: 1100, end: 1127, slots: ['北宋', '金', '西夏', '辽'] },
  { start: 1127, end: 1279, slots: ['南宋', '金', '西夏', '元'] },
]

/** 后金(1616)起：明/南明左半，后金/清右半（清接续后金列） */
const HOUJIN_START_YEAR = 1616
const MING_QING_COEXIST_END = 1662
const MING_SEQUENCE_REGIMES = new Set(['明', '南明'])
const QING_SEQUENCE_REGIMES = new Set(['后金', '清'])

/** 六等分并列：左 4/6 唐，中 1/6 渤海，右 1/6 南诏 */
const SIXTH_GRID_ZONES = [
  {
    start: 697, end: 904,
    columns: [
      { key: '__tang__', sixths: 4 },
      { key: '渤海',   sixths: 1 },
      { key: '南诏',   sixths: 1 },
    ],
  },
]

/** 904–979：无宋时左 1/2 唐/渤海/大理、右半五代/辽均分；有宋时宋靠左 1/2，其余均分右半 */
const QUARTER_GRID_ZONES = [
  {
    start: 904, end: 979,
    columns: [
      { key: '__left_seq__', quarters: 3 },
      { key: '北宋',         quarters: 1 },
      { key: '五代十国',       quarters: 1 },
      { key: '辽',           quarters: 1 },
    ],
  },
]

const LEFT_SEQ_REGIMES = new Set(['唐', '渤海', '大理'])
const SONG_REGIMES = new Set(['北宋', '南宋'])

/** 四列均分（左→右）各占 1/4：北宋期末 宋金西夏辽，南宋期 宋金西夏元 */
const FOUR_EQUAL_NORTH_SLOTS = ['北宋', '金', '西夏', '辽']
const FOUR_EQUAL_SOUTH_SLOTS = ['南宋', '金', '西夏', '元']

function isFourEqualSongJinXixiaYuanSlots(slotKeys) {
  if (!slotKeys) return false
  return [FOUR_EQUAL_NORTH_SLOTS, FOUR_EQUAL_SOUTH_SLOTS].some(
    slots => slotKeys.length === slots.length && slots.every((k, i) => slotKeys[i] === k)
  )
}

function matchFourEqualYuanSlot(entry, slotKey) {
  if (SONG_REGIMES.has(slotKey) && isSongEntry(entry)) return true
  return matchSlotKey(entry, slotKey)
}

function matchFourEqualYuanEntry(entry, slotKeys) {
  return slotKeys.some(k => matchFourEqualYuanSlot(entry, k))
}

function isSongEntry(entry) {
  return SONG_REGIMES.has(entry.dynastyName) || SONG_REGIMES.has(entry.dynastyGroup)
}

/** 金亡(1234)后宋占左半；元世祖(1260)起元占右半，象征宋元并存 */
const JIN_FALL_YEAR = 1234
const YUAN_START_YEAR = 1260
const SONG_YUAN_COEXIST_ZONES = [
  { start: JIN_FALL_YEAR, end: YUAN_START_YEAR, yuanHalf: false },
  { start: YUAN_START_YEAR, end: 1279, yuanHalf: true },
]

function findSongYuanCoexistZone(tS) {
  return SONG_YUAN_COEXIST_ZONES.find(z => tS >= z.start && tS < z.end) || null
}

function matchYuanEntry(entry) {
  return entry.dynastyName === '元' || entry.dynastyGroup === '元' ||
    matchSlotKey(entry, '元')
}

function matchDaliEntry(entry) {
  return entry.dynastyName === '大理' || entry.dynastyGroup === '大理'
}

function calcSongYuanHalfGeometry(active, yuanHalf, daliHalf = false) {
  const G = BLOCK_H_GAP_PCT
  const halfW = calcSongHalfWidthPct(2)
  const geoms = []
  if (active.some(isSongEntry)) {
    geoms.push({ key: '__song__', leftPct: 0, widthPct: halfW, colIndex: 0, numCols: 2 })
  }
  if (yuanHalf && active.some(matchYuanEntry)) {
    geoms.push({ key: '元', leftPct: halfW + G, widthPct: halfW, colIndex: 1, numCols: 2 })
  } else if (daliHalf && active.some(matchDaliEntry)) {
    geoms.push({ key: '大理', leftPct: halfW + G, widthPct: halfW, colIndex: 1, numCols: 2 })
  }
  return geoms
}

function matchSongYuanLayoutKey(entry, key) {
  if (key === '__song__') return isSongEntry(entry)
  if (key === '元') return matchYuanEntry(entry)
  if (key === '大理') return matchDaliEntry(entry)
  return false
}

function assignSongYuanPlacements(active, zone, prevPlacements, tS, tE) {
  const prevMap = {}
  if (prevPlacements) prevPlacements.forEach(p => { prevMap[p.id] = p })

  const hasYuanRight = zone.yuanHalf && active.some(matchYuanEntry)
  const hasDaliRight = !hasYuanRight && active.some(matchDaliEntry)

  const layoutActive = active.filter(e =>
    isSongEntry(e) ||
    (hasYuanRight && matchYuanEntry(e)) ||
    (hasDaliRight && matchDaliEntry(e))
  )
  const extraActive = active.filter(e => !layoutActive.includes(e))
  const geoms = calcSongYuanHalfGeometry(layoutActive, hasYuanRight, hasDaliRight)

  const ideal = {}
  layoutActive.forEach(e => {
    const col = geoms.find(g => matchSongYuanLayoutKey(e, g.key))
    if (!col) {
      ideal[e.id] = makePlacement(e, 100 - MINOR_WIDTH, MINOR_WIDTH, -1, 2)
    } else {
      ideal[e.id] = makePlacement(
        e, col.leftPct, col.widthPct, col.colIndex, col.numCols
      )
    }
  })
  extraActive.forEach(e => {
    ideal[e.id] = makePlacement(e, 100 - MINOR_WIDTH, MINOR_WIDTH, -1, 2)
  })

  return active.map(e => {
    const next = ideal[e.id]
    const prev = prevMap[e.id]
    if (prev && e.end !== tE && e.start !== tS) {
      const same =
        Math.abs(prev.leftPct - next.leftPct) < 0.5 &&
        Math.abs(prev.widthPct - next.widthPct) < 0.5
      if (same) return Object.assign({}, prev, { id: e.id })
    }
    return next
  }).sort((a, b) => a.leftPct - b.leftPct)
}

function findMingQingCoexistZone(tS) {
  return tS >= HOUJIN_START_YEAR && tS < MING_QING_COEXIST_END
    ? { start: HOUJIN_START_YEAR, end: MING_QING_COEXIST_END }
    : null
}

function isMingSequenceEntry(entry) {
  return MING_SEQUENCE_REGIMES.has(entry.dynastyName) ||
    MING_SEQUENCE_REGIMES.has(entry.dynastyGroup)
}

function isQingSequenceEntry(entry) {
  return QING_SEQUENCE_REGIMES.has(entry.dynastyName) ||
    QING_SEQUENCE_REGIMES.has(entry.dynastyGroup)
}

function calcMingQingHalfGeometry() {
  const G = BLOCK_H_GAP_PCT
  const halfW = calcSongHalfWidthPct(2)
  return [
    { key: '__ming__', leftPct: 0, widthPct: halfW, colIndex: 0, numCols: 2 },
    { key: '__qing__', leftPct: halfW + G, widthPct: halfW, colIndex: 1, numCols: 2 },
  ]
}

function assignMingQingPlacements(active, prevPlacements, tS, tE) {
  const prevMap = {}
  if (prevPlacements) prevPlacements.forEach(p => { prevMap[p.id] = p })

  const geoms = calcMingQingHalfGeometry()
  const leftGeom = geoms[0]
  const rightGeom = geoms[1]
  const layoutActive = active.filter(e => isMingSequenceEntry(e) || isQingSequenceEntry(e))
  const extraActive = active.filter(e => !layoutActive.includes(e))

  const ideal = {}

  const placeInHalf = (entries, halfGeom) => {
    const emperors = entries.filter(e => e.isEmperor)
    const nonEmperors = entries.filter(e => !e.isEmperor)
    nonEmperors.forEach(e => {
      ideal[e.id] = makePlacement(
        e, halfGeom.leftPct, halfGeom.widthPct, halfGeom.colIndex, halfGeom.numCols
      )
    })
    if (!emperors.length) return
    const dynName = emperors[0].dynastyName
    const sameDyn = emperors.every(e => e.dynastyName === dynName)
    const lanePack = sameDyn ? EMPEROR_LANES_BY_DYN[dynName] : null
    const laneCount = lanePack && lanePack.stackTotal > 1 ? lanePack.stackTotal : 1
    if (laneCount <= 1 || emperors.length !== entries.length || emperors.length <= 1) {
      emperors.forEach(e => {
        ideal[e.id] = makePlacement(
          e, halfGeom.leftPct, halfGeom.widthPct, halfGeom.colIndex, halfGeom.numCols
        )
      })
      return
    }
    const usable = halfGeom.widthPct
    const G = BLOCK_H_GAP_PCT * (laneCount - 1) / laneCount
    const colW = (usable - (laneCount - 1) * G) / laneCount
    emperors.forEach(e => {
      const { stackIndex } = getEmperorLanePlacement(e)
      const leftPct = halfGeom.leftPct + stackIndex * (colW + G)
      ideal[e.id] = makePlacement(
        e, leftPct, colW, halfGeom.colIndex, halfGeom.numCols
      )
    })
  }

  placeInHalf(layoutActive.filter(isMingSequenceEntry), leftGeom)
  placeInHalf(layoutActive.filter(isQingSequenceEntry), rightGeom)

  extraActive.forEach(e => {
    ideal[e.id] = makePlacement(e, 100 - MINOR_WIDTH, MINOR_WIDTH, -1, 2)
  })

  return active.map(e => {
    const next = ideal[e.id]
    const prev = prevMap[e.id]
    if (prev && e.end !== tE && e.start !== tS) {
      const same =
        Math.abs(prev.leftPct - next.leftPct) < 0.5 &&
        Math.abs(prev.widthPct - next.widthPct) < 0.5
      if (same) return Object.assign({}, prev, { id: e.id })
    }
    return next
  }).sort((a, b) => a.leftPct - b.leftPct)
}

/** 灭国后：征服者 L 形占左列 + 中列（不与被灭政权交叉） */
const CONQUEST_FILLS = [
  {
    zoneStart: 220, zoneEnd: 280,
    slots: ['三国·魏', '三国·蜀', '三国·吴'],
    fillSlot: '三国·蜀',
    conquerorDynasty: '三国·魏',
    conquestYear: 263,
  },
]

const MINOR_WIDTH = 36   // 未纳入分区的并行条目：右侧窄列

function makePlacement(e, leftPct, widthPct, colIndex, numCols) {
  return {
    id: e.id,
    leftPct:  Math.max(0, Math.min(100, leftPct)),
    widthPct: Math.max(8, Math.min(100, widthPct)),
    colIndex: colIndex != null ? colIndex : 0,
    numCols:  numCols != null ? numCols : 1,
  }
}

/** 304–439 左列：晋朝帝王（西晋/东晋）与南北朝 */
const LEFT_MAIN_REGIMES = new Set(['西晋', '东晋', '南北朝'])
const JIN_DYNASTY_NAMES = new Set(['西晋', '东晋'])
const NANBEI_ENTRY_ID = 'merged_南北朝'

function matchJinSlot(entry) {
  if (!entry.isEmperor) return false
  return JIN_DYNASTY_NAMES.has(entry.dynastyName) ||
    JIN_DYNASTY_NAMES.has(entry.dynastyGroup)
}

function matchLeftMainSlot(entry) {
  return LEFT_MAIN_REGIMES.has(entry.dynastyName) ||
    LEFT_MAIN_REGIMES.has(entry.dynastyGroup) ||
    LEFT_MAIN_REGIMES.has(entry.displayName)
}

/** 列槽别名：新王朝 occupying 原列位（如西晋接魏左列） */
const SLOT_COLUMN_ALIASES = {
  '三国·魏': ['西晋'],
}

function matchSlotKey(entry, slotKey) {
  if (slotKey === '__jin__') return matchJinSlot(entry)
  if (slotKey === '__left_main__') return matchLeftMainSlot(entry)
  if (entry.dynastyName === slotKey ||
    entry.dynastyGroup === slotKey ||
    entry.displayName === slotKey) {
    return true
  }
  const aliases = SLOT_COLUMN_ALIASES[slotKey]
  return !!(aliases && aliases.some(a =>
    entry.dynastyName === a || entry.dynastyGroup === a || entry.displayName === a
  ))
}

/** N 列均分几何（含列间距） */
function calcColumnGeometry(numCols) {
  const G = BLOCK_H_GAP_PCT
  const widthPct = (100 - (numCols - 1) * G) / numCols
  return { widthPct, G }
}

function slotLeftPct(index, widthPct, G) {
  return index * (widthPct + G)
}

function findSixthGridZone(tS) {
  return SIXTH_GRID_ZONES.find(z => tS >= z.start && tS < z.end) || null
}

function calcSixthGridGeometry(columns, active) {
  const G = BLOCK_H_GAP_PCT
  const hasActive = (key) => active.some(e => matchSixthGridKey(e, key))

  const tangCol = columns.find(c => c.key === '__tang__')
  const sideCols = columns.filter(c => c.key !== '__tang__')
  const activeSideCols = sideCols.filter(c => hasActive(c.key))

  const effectiveCols = []
  if (tangCol && hasActive('__tang__')) {
    let tangSixths = tangCol.sixths
    sideCols.forEach(side => {
      if (!hasActive(side.key)) tangSixths += side.sixths
    })
    effectiveCols.push({ key: '__tang__', sixths: tangSixths })
  }
  activeSideCols.forEach(c => effectiveCols.push(c))

  if (!effectiveCols.length) {
    const G = BLOCK_H_GAP_PCT
    const usable = 100 - (columns.length - 1) * G
    const unit = usable / 6
    let left = 0
    return columns.map((col, i) => {
      const widthPct = unit * col.sixths
      const geom = { key: col.key, leftPct: left, widthPct, colIndex: i, numCols: 6 }
      left += widthPct + (i < columns.length - 1 ? G : 0)
      return geom
    })
  }

  const usable = 100 - (effectiveCols.length - 1) * G
  const unit = usable / 6
  let left = 0
  return effectiveCols.map((col, i) => {
    const widthPct = unit * col.sixths
    const geom = { key: col.key, leftPct: left, widthPct, colIndex: i, numCols: 6 }
    left += widthPct + (i < effectiveCols.length - 1 ? G : 0)
    return geom
  })
}

function matchSixthGridKey(entry, key) {
  if (key === '__tang__') {
    return entry.dynastyName === '唐' || entry.dynastyGroup === '唐' ||
      entry.displayName === '唐'
  }
  return matchSlotKey(entry, key)
}

function activeForSixthGridLayout(active) {
  const hasTangEmperor = active.some(e =>
    e.isEmperor && matchSixthGridKey(e, '__tang__')
  )
  if (!hasTangEmperor) return active

  // 唐帝王展开时：并列渤海/南诏的折叠政权卡不占列，唐色块左起拉通
  return active.filter(e => {
    if (e.isEmperor) return true
    if (matchSixthGridKey(e, '__tang__')) return true
    if (matchSixthGridKey(e, '渤海') || matchSixthGridKey(e, '南诏')) return false
    return true
  })
}

function assignSixthGridPlacements(active, zone, prevPlacements, tS, tE) {
  const prevMap = {}
  if (prevPlacements) prevPlacements.forEach(p => { prevMap[p.id] = p })

  const geoms = calcSixthGridGeometry(zone.columns, active)
  const ideal = {}
  active.forEach(e => {
    const col = geoms.find(g => matchSixthGridKey(e, g.key))
    if (!col) {
      ideal[e.id] = makePlacement(e, 100 - MINOR_WIDTH, MINOR_WIDTH, -1, 6)
    } else {
      ideal[e.id] = makePlacement(
        e, col.leftPct, col.widthPct, col.colIndex, col.numCols
      )
    }
  })

  return active.map(e => {
    const next = ideal[e.id]
    const prev = prevMap[e.id]
    if (prev && e.end !== tE && e.start !== tS) {
      const same =
        Math.abs(prev.leftPct - next.leftPct) < 0.5 &&
        Math.abs(prev.widthPct - next.widthPct) < 0.5
      if (same) return Object.assign({}, prev, { id: e.id })
    }
    return next
  }).sort((a, b) => a.leftPct - b.leftPct)
}

function findQuarterGridZone(tS) {
  return QUARTER_GRID_ZONES.find(z => tS >= z.start && tS < z.end) || null
}

/** 宋 1/2 | 中间列 1/4（西夏/五代/金）| 辽 1/4 靠右；总份数 6 = 3 + 1.5 + 1.5 */
const MIDDLE_COLUMN_KEYS = ['西夏', '五代十国', '金']

function matchLiaoEntry(entry) {
  return matchSlotKey(entry, '辽') || matchQuarterGridKey(entry, '辽')
}

function matchMiddleColumnEntry(entry) {
  return MIDDLE_COLUMN_KEYS.some(k => matchSlotKey(entry, k) || matchQuarterGridKey(entry, k))
}

function calcSongLiaoFixedGeometry(active, reserveEmptySlots = false) {
  const G = BLOCK_H_GAP_PCT
  const SONG_U = 3
  const MID_U = 1.5
  const LIAO_U = 1.5
  const TOTAL_U = 6

  const hasSong = active.some(isSongEntry)
  const hasLiao = active.some(matchLiaoEntry)
  const hasMiddle = active.some(matchMiddleColumnEntry)
  const keepThreeCols = reserveEmptySlots && hasSong

  const cols = []
  if (hasSong) cols.push({ key: '__song__', units: SONG_U })
  // 有中间政权，或宋辽并存时保留中槽，确保辽固定在最右 1/4
  // 并列分区内某年辽/中槽暂无帝王时仍保留列结构，避免宋宽忽宽忽窄
  if (hasMiddle || (hasSong && hasLiao) || keepThreeCols) {
    cols.push({ key: '__middle__', units: MID_U })
  }
  if (hasLiao || keepThreeCols) cols.push({ key: '辽', units: LIAO_U })

  if (!cols.length) return []

  const usable = 100 - (cols.length - 1) * G
  const unit = usable / TOTAL_U
  let left = 0
  return cols.map((col, i) => {
    const widthPct = unit * col.units
    const geom = { key: col.key, leftPct: left, widthPct, colIndex: i, numCols: cols.length }
    left += widthPct + (i < cols.length - 1 ? G : 0)
    return geom
  })
}

/** 宋靠左 1/2，其余活跃列均分右侧 1/2（无辽并列时使用） */
function calcSongLeftHalfGeometry(active, otherKeys) {
  const G = BLOCK_H_GAP_PCT
  const SONG_Q = 3
  const REST_Q = 3

  const hasOther = (key) => active.some(e => matchSlotKey(e, key) || matchQuarterGridKey(e, key))
  const activeOthers = otherKeys.filter(hasOther)

  const effectiveCols = []
  if (active.some(isSongEntry)) {
    effectiveCols.push({ key: '__song__', quarters: SONG_Q })
  }
  const otherQEach = activeOthers.length > 0 ? REST_Q / activeOthers.length : 0
  activeOthers.forEach(k => effectiveCols.push({ key: k, quarters: otherQEach }))

  if (!effectiveCols.length) return []

  const totalQuarters = SONG_Q + (activeOthers.length > 0 ? REST_Q : 0)
  const usable = 100 - (effectiveCols.length - 1) * G
  const unit = usable / totalQuarters
  let left = 0
  return effectiveCols.map((col, i) => {
    const widthPct = unit * col.quarters
    const geom = { key: col.key, leftPct: left, widthPct, colIndex: i, numCols: effectiveCols.length }
    left += widthPct + (i < effectiveCols.length - 1 ? G : 0)
    return geom
  })
}

function matchSongLiaoLayoutKey(entry, key) {
  if (key === '__song__') return isSongEntry(entry)
  if (key === '__middle__') return matchMiddleColumnEntry(entry)
  if (key === '辽') return matchLiaoEntry(entry)
  return matchSlotKey(entry, key) || matchQuarterGridKey(entry, key)
}

function shouldUseSongLiaoFixedLayout(active, slotKeys) {
  if (isFourEqualSongJinXixiaYuanSlots(slotKeys)) return false
  if (!active.some(isSongEntry)) return false
  if (slotKeys && slotKeys.includes('辽')) return true
  return active.some(matchLiaoEntry)
}

function calcQuarterGridGeometry(columns, active) {
  const G = BLOCK_H_GAP_PCT
  const hasActive = (key) => active.some(e => matchQuarterGridKey(e, key))

  // 北宋已起：宋 1/2 | 中 1/4（五代十国等）| 辽 1/4
  if (active.some(isSongEntry)) {
    return calcSongLiaoFixedGeometry(active, true)
  }

  const leftCol = columns.find(c => c.key === '__left_seq__')
  const rightCols = columns.filter(c => c.key !== '__left_seq__')
  const activeRightCols = rightCols.filter(c => hasActive(c.key))

  const LEFT_Q = 3
  const RIGHT_Q_TOTAL = 3
  const rightQEach = activeRightCols.length > 0 ? RIGHT_Q_TOTAL / activeRightCols.length : 0

  const effectiveCols = []
  if (leftCol) {
    effectiveCols.push({ key: '__left_seq__', quarters: LEFT_Q })
  }
  activeRightCols.forEach(c => {
    effectiveCols.push({ key: c.key, quarters: rightQEach })
  })

  if (!effectiveCols.length) return []

  const totalQuarters = effectiveCols.reduce((s, c) => s + c.quarters, 0)
  const usable = 100 - (effectiveCols.length - 1) * G
  const unit = usable / totalQuarters
  let left = 0
  return effectiveCols.map((col, i) => {
    const widthPct = unit * col.quarters
    const geom = { key: col.key, leftPct: left, widthPct, colIndex: i, numCols: effectiveCols.length }
    left += widthPct + (i < effectiveCols.length - 1 ? G : 0)
    return geom
  })
}

function matchQuarterGridKey(entry, key) {
  if (key === '__left_seq__') {
    return LEFT_SEQ_REGIMES.has(entry.dynastyName) ||
      LEFT_SEQ_REGIMES.has(entry.dynastyGroup) ||
      LEFT_SEQ_REGIMES.has(entry.displayName)
  }
  if (key === '北宋') {
    return isSongEntry(entry)
  }
  return matchSlotKey(entry, key)
}

function assignQuarterGridPlacements(active, zone, prevPlacements, tS, tE) {
  const prevMap = {}
  if (prevPlacements) prevPlacements.forEach(p => { prevMap[p.id] = p })

  const geoms = calcQuarterGridGeometry(zone.columns, active)
  const ideal = {}
  active.forEach(e => {
    const col = geoms.find(g => matchSongLiaoLayoutKey(e, g.key))
    if (!col) {
      ideal[e.id] = makePlacement(e, 100 - MINOR_WIDTH, MINOR_WIDTH, -1, 4)
    } else {
      ideal[e.id] = makePlacement(
        e, col.leftPct, col.widthPct, col.colIndex, col.numCols
      )
    }
  })

  return active.map(e => {
    const next = ideal[e.id]
    const prev = prevMap[e.id]
    if (prev && e.end !== tE && e.start !== tS) {
      const same =
        Math.abs(prev.leftPct - next.leftPct) < 0.5 &&
        Math.abs(prev.widthPct - next.widthPct) < 0.5
      if (same) return Object.assign({}, prev, { id: e.id })
    }
    return next
  }).sort((a, b) => a.leftPct - b.leftPct)
}

/** 当前时刻命中的并列分区（含加权列） */
function findParallelZone(tS) {
  const zoneMatches = PARALLEL_ZONES.filter(z => tS >= z.start && tS < z.end)
  if (!zoneMatches.length) return null
  zoneMatches.sort((a, b) => b.slots.length - a.slots.length || b.start - a.start)
  return zoneMatches[0]
}

/** 按权重分配列宽（如 2:1 → 左 2/3 右 1/3） */
function calcWeightedColumnGeometry(weights) {
  const G = BLOCK_H_GAP_PCT
  const n = weights.length
  const totalUnits = weights.reduce((s, w) => s + w, 0)
  const usable = 100 - (n - 1) * G
  const unit = usable / totalUnits
  let left = 0
  return weights.map((w, i) => {
    const widthPct = unit * w
    const geom = { leftPct: left, widthPct, colIndex: i, numCols: n }
    left += widthPct + (i < n - 1 ? G : 0)
    return geom
  })
}

function assignWeightedZonePlacements(active, zone, prevPlacements, tS, tE) {
  const prevMap = {}
  if (prevPlacements) prevPlacements.forEach(p => { prevMap[p.id] = p })

  const geoms = calcWeightedColumnGeometry(zone.weights)
  const slotKeys = zone.slots
  const ideal = {}
  active.forEach(e => {
    const idx = slotKeys.findIndex(k => matchSlotKey(e, k))
    if (idx < 0) {
      ideal[e.id] = makePlacement(e, 100 - MINOR_WIDTH, MINOR_WIDTH, -1, slotKeys.length)
    } else {
      const col = geoms[idx]
      ideal[e.id] = makePlacement(e, col.leftPct, col.widthPct, col.colIndex, col.numCols)
    }
  })

  return active.map(e => {
    const next = ideal[e.id]
    const prev = prevMap[e.id]
    if (prev && e.end !== tE && e.start !== tS) {
      const same =
        Math.abs(prev.leftPct - next.leftPct) < 0.5 &&
        Math.abs(prev.widthPct - next.widthPct) < 0.5
      if (same) return Object.assign({}, prev, { id: e.id })
    }
    return next
  }).sort((a, b) => a.leftPct - b.leftPct)
}

/** 当前时刻应使用的固定列槽表（显式分区 > 同 dynasty 组自动分区） */
function findColumnLayout(tS, civName, active) {
  const zone = findParallelZone(tS)
  if (zone) return zone.slots

  const groupNames = [...new Set(active.map(e => e.dynastyGroup).filter(Boolean))]
  for (const g of groupNames) {
    if (isMergedEraGroup(g)) continue
    const members = DYNASTY_GROUPS[civName]?.[g]
    if (!members || members.length < 2) continue
    const gStart = Math.min(...members.map(m => m.start))
    const gEnd   = Math.max(...members.map(m => m.end))
    if (tS >= gStart && tS < gEnd) {
      return members.map(m => m.name)
    }
  }
  return null
}

/** 同时期政权数：并列列槽数 > 自动分组政权数 > 1 */
function countConcurrentRegimes(tS, civName, active) {
  const slotKeys = findColumnLayout(tS, civName, active)
  if (slotKeys && slotKeys.length > 1) return slotKeys.length
  const groups = new Set(
    (active || []).map(e => e.dynastyName || e.dynastyGroup).filter(Boolean)
  )
  return Math.max(1, groups.size)
}

/** 固定列槽分配：每 entry 始终在同一列，列内上下堆叠 */
function assignFixedColumnPlacements(active, slotKeys, prevPlacements, tS, tE) {
  const prevMap = {}
  if (prevPlacements) prevPlacements.forEach(p => { prevMap[p.id] = p })

  const hasSongSlot = slotKeys.some(k => SONG_REGIMES.has(k))
  const useFourEqual = isFourEqualSongJinXixiaYuanSlots(slotKeys)
  const useSongLiaoFixed = !useFourEqual && shouldUseSongLiaoFixedLayout(active, slotKeys)
  const useSongLeftHalf = !useFourEqual && hasSongSlot && active.some(isSongEntry) && !useSongLiaoFixed

  const ideal = {}
  if (useSongLiaoFixed) {
    const geoms = calcSongLiaoFixedGeometry(active, true)
    active.forEach(e => {
      const col = geoms.find(g => matchSongLiaoLayoutKey(e, g.key))
      if (!col) {
        ideal[e.id] = makePlacement(e, 100 - MINOR_WIDTH, MINOR_WIDTH, -1, geoms.length || slotKeys.length)
      } else {
        ideal[e.id] = makePlacement(
          e, col.leftPct, col.widthPct, col.colIndex, col.numCols
        )
      }
    })
  } else if (useSongLeftHalf) {
    const otherKeys = slotKeys.filter(k => !SONG_REGIMES.has(k))
    const geoms = calcSongLeftHalfGeometry(active, otherKeys)
    active.forEach(e => {
      const col = geoms.find(g => matchSongLiaoLayoutKey(e, g.key))
      if (!col) {
        ideal[e.id] = makePlacement(e, 100 - MINOR_WIDTH, MINOR_WIDTH, -1, geoms.length || slotKeys.length)
      } else {
        ideal[e.id] = makePlacement(
          e, col.leftPct, col.widthPct, col.colIndex, col.numCols
        )
      }
    })
  } else {
    const numCols = slotKeys.length
    const { widthPct, G } = calcColumnGeometry(numCols)
    active.forEach(e => {
      const idx = useFourEqual
        ? slotKeys.findIndex(k => matchFourEqualYuanSlot(e, k))
        : slotKeys.findIndex(k => matchSlotKey(e, k))
      if (idx < 0) {
        ideal[e.id] = makePlacement(e, 100 - MINOR_WIDTH, MINOR_WIDTH, -1, numCols)
      } else {
        ideal[e.id] = makePlacement(
          e, slotLeftPct(idx, widthPct, G), widthPct, idx, numCols
        )
      }
    })
  }

  return active.map(e => {
    const next = ideal[e.id]
    const prev = prevMap[e.id]
    if (prev && e.end !== tE && e.start !== tS) {
      const same =
        Math.abs(prev.leftPct - next.leftPct) < 0.5 &&
        Math.abs(prev.widthPct - next.widthPct) < 0.5
      if (same) return Object.assign({}, prev, { id: e.id })
    }
    return next
  }).sort((a, b) => a.leftPct - b.leftPct)
}

/**
 * 列位分配：
 * - 并列时期 → 固定 N 列槽（未活跃槽留白）
 * - 单独存在 → 100% 宽
 * - 其余少量并行 → 按政权起始年排序均分
 */
function assignPlacements(active, prevPlacements, tS, tE, civName) {
  if (!active.length) return []

  if (active.some(e => e.isCollapsedRegimeSummary)) {
    return active.filter(e => e.isCollapsedRegimeSummary).map(e =>
      makePlacement(e, 0, 100, 0, 1)
    )
  }

  const regimeOnly = active.filter(e => e.isRegimeOnly)
  if (regimeOnly.length > 0 && regimeOnly.length === active.length) {
    if (regimeEra.isSpringAutumnSlice(tS) || regimeEra.isWarringStatesSlice(tS)) {
      return regimeEra.assignRegimeEraPlacements(
        regimeOnly, makePlacement, tS, BLOCK_H_GAP_PCT
      )
    }
  }

  const mingQingZone = findMingQingCoexistZone(tS)
  if (mingQingZone && active.some(e => isMingSequenceEntry(e) || isQingSequenceEntry(e))) {
    return assignMingQingPlacements(active, prevPlacements, tS, tE)
  }

  const quarterZone = findQuarterGridZone(tS)
  if (quarterZone) {
    const allInZone = active.every(e =>
      quarterZone.columns.some(c => matchQuarterGridKey(e, c.key))
    )
    if (allInZone) {
      return assignQuarterGridPlacements(active, quarterZone, prevPlacements, tS, tE)
    }
  }

  const sixthZone = findSixthGridZone(tS)
  if (sixthZone) {
    const layoutActive = activeForSixthGridLayout(active)
    const allInZone = layoutActive.length > 0 && layoutActive.every(e =>
      sixthZone.columns.some(c => matchSixthGridKey(e, c.key))
    )
    if (allInZone) {
      return assignSixthGridPlacements(layoutActive, sixthZone, prevPlacements, tS, tE)
    }
  }

  const parallelZone = findParallelZone(tS)
  if (parallelZone && parallelZone.weights) {
    const zoneActive = active.filter(e => parallelZone.slots.some(k => matchSlotKey(e, k)))
    const extraActive = active.filter(e => !parallelZone.slots.some(k => matchSlotKey(e, k)))
    if (zoneActive.length > 0) {
      const slotPlacements = assignWeightedZonePlacements(
        zoneActive, parallelZone, prevPlacements, tS, tE
      )
      const extraPlacements = extraActive.map(e =>
        makePlacement(e, 100 - MINOR_WIDTH, MINOR_WIDTH, -1, parallelZone.slots.length)
      )
      return [...slotPlacements, ...extraPlacements].sort((a, b) => a.leftPct - b.leftPct)
    }
  }

  const slotKeys = findColumnLayout(tS, civName, active)

  const songYuanZone = findSongYuanCoexistZone(tS)
  if (songYuanZone && active.some(e =>
    isSongEntry(e) ||
    (songYuanZone.yuanHalf && matchYuanEntry(e)) ||
    matchDaliEntry(e)
  )) {
    return assignSongYuanPlacements(active, songYuanZone, prevPlacements, tS, tE)
  }

  if (slotKeys && slotKeys.length >= 2) {
    const slotActive  = active.filter(e => slotKeys.some(k => matchSlotKey(e, k)))
    const extraActive = active.filter(e => !slotKeys.some(k => matchSlotKey(e, k)))

    if (isFourEqualSongJinXixiaYuanSlots(slotKeys)) {
      const feSlotActive = slotActive.filter(e => matchFourEqualYuanEntry(e, slotKeys))
      const feExtraActive = [
        ...extraActive,
        ...slotActive.filter(e => !matchFourEqualYuanEntry(e, slotKeys)),
      ]
      const slotPlacements = feSlotActive.length
        ? assignFixedColumnPlacements(feSlotActive, slotKeys, prevPlacements, tS, tE)
        : []
      const extraPlacements = feExtraActive.map(e =>
        makePlacement(e, 100 - MINOR_WIDTH, MINOR_WIDTH, -1, slotKeys.length)
      )
      return [...slotPlacements, ...extraPlacements].sort((a, b) => a.leftPct - b.leftPct)
    }

    // 并列时期（如三国）：槽内政权固定 1/N 列，其余并行政权收窄靠右
    if (slotActive.length > 0) {
      const slotPlacements = assignFixedColumnPlacements(slotActive, slotKeys, prevPlacements, tS, tE)
      const extraPlacements = extraActive.map(e =>
        makePlacement(e, 100 - MINOR_WIDTH, MINOR_WIDTH, -1, slotKeys.length)
      )
      return [...slotPlacements, ...extraPlacements].sort((a, b) => a.leftPct - b.leftPct)
    }
  }

  if (active.length === 1) {
    const e = active[0]
    const mqZone = findMingQingCoexistZone(tS)
    if (mqZone && (isMingSequenceEntry(e) || isQingSequenceEntry(e))) {
      const geoms = calcMingQingHalfGeometry()
      const col = isMingSequenceEntry(e) ? geoms[0] : geoms[1]
      return [makePlacement(e, col.leftPct, col.widthPct, col.colIndex, col.numCols)]
    }
    return [makePlacement(e, 0, 100, 0, 1)]
  }

  const dynKeys = [...new Set(active.map(e => e.dynastyName))].sort((a, b) => {
    const rank = (name) => {
      if (name === '西晋' || name === '东晋' || name === '北宋' || name === '南宋') return 0
      if (name === '隋' || name === '三国·魏') return 0
      if (name === '南北朝') return 1
      return 2
    }
    const ra = rank(a), rb = rank(b)
    if (ra !== rb) return ra - rb
    const ea = active.find(e => e.dynastyName === a)
    const eb = active.find(e => e.dynastyName === b)
    return (ea?.start || 0) - (eb?.start || 0)
  })
  if (dynKeys.length >= 2) {
    return assignFixedColumnPlacements(active, dynKeys, prevPlacements, tS, tE)
  }

  // 同朝代多帝王：固定泳道 → 水平分列，避免纵向子行跨行合并重叠
  const emperors = active.filter(e => e.isEmperor)
  if (emperors.length > 0 && emperors.length === active.length) {
    const lanePack = EMPEROR_LANES_BY_DYN[emperors[0].dynastyName]
    const laneCount = lanePack ? lanePack.stackTotal : 1
    if (laneCount <= 1) {
      return emperors.map(e => makePlacement(e, 0, 100, 0, 1))
    }
    const weighted = assignWeightedEmperorPairPlacements(emperors)
    if (weighted) return weighted.sort((a, b) => a.leftPct - b.leftPct)
    const { widthPct, G } = calcColumnGeometry(laneCount)
    return emperors.map(e => {
      const { stackIndex } = getEmperorLanePlacement(e)
      return makePlacement(
        e,
        slotLeftPct(stackIndex, widthPct, G),
        widthPct,
        stackIndex,
        laneCount
      )
    }).sort((a, b) => a.leftPct - b.leftPct)
  }

  return active.map(e => makePlacement(e, 0, 100, 0, 1))
}

/** 行高 = 该时间片年数 × 线性比例，带上下限；特定历史阶段整段压缩 */
function calcSliceH(tS, tE, active) {
  const years = Math.max(1, tE - tS)
  const linear = Math.round(years * SLICE_RPX_PER_YEAR)
  let h = Math.max(SLICE_H_MIN_RPX, Math.min(SLICE_H_MAX_RPX, linear))
  const scale = getTimelineCompressScale(tS, tE)
  if (scale < 1) {
    h = Math.max(BLOCK_MIN_SEG_H, Math.round(h * scale))
    if (active && active.some(e => e.isEmperor)) {
      h = Math.max(COMPRESSED_EMPEROR_SLICE_H_MIN_RPX, h)
    }
  }
  return h
}

function placementKey(placements) {
  return placements
    .map(p => `${p.id}@${p.leftPct.toFixed(1)}/${p.widthPct.toFixed(1)}`)
    .sort()
    .join('|')
}

/** 水平区间是否重叠（百分比坐标） */
function hOverlap(a, b) {
  return a.leftPct < b.leftPct + b.widthPct - 0.01 &&
    b.leftPct < a.leftPct + a.widthPct - 0.01
}

/** 不同 entry 的色块之间留间距；同一 entry 多段（不规则形）保持无缝 */
function applyInterBlockGaps(blocks) {
  const V = BLOCK_V_GAP_RPX
  const insets = blocks.map(() => ({ top: 0, bottom: 0 }))

  const sameEntryAbove = (b) => blocks.some(c =>
    c !== b && c.entryId === b.entryId && Math.abs(c.top + c.h - b.top) < 2
  )
  const sameEntryBelow = (b) => blocks.some(c =>
    c !== b && c.entryId === b.entryId && Math.abs(b.top + b.h - c.top) < 2
  )

  blocks.forEach((b, bi) => {
    blocks.forEach((a, ai) => {
      if (ai === bi || a.entryId === b.entryId) return
      // 上下紧邻且水平区间重叠 → 不同 entry 留统一垂直间距（含全宽段接 1/3 列）
      if (Math.abs(a.top + a.h - b.top) < 2 && hOverlap(a, b)) {
        const aHasLBelow = sameEntryBelow(a)
        const bHasLAbove = sameEntryAbove(b)
        const lowerArm = aHasLBelow
          ? blocks.find(c => c !== a && c.entryId === a.entryId &&
            Math.abs(a.top + a.h - c.top) < 2 && hOverlap(a, c))
          : null
        // L 形下臂与外块同行并列（如晋惠帝+十六国）→ 仅水平间距，不加垂直 8rpx
        const parallelAtTransition = lowerArm && Math.abs(lowerArm.top - b.top) < 2
        if (parallelAtTransition) {
          // L 形转角：右侧/并列外块仍保留顶缘间距（如晋惠帝+十六国、咸丰+天王）
          insets[bi].top = Math.max(insets[bi].top, V)
          return
        }

        if (aHasLBelow && bHasLAbove) {
          insets[bi].top = Math.max(insets[bi].top, V / 2)
          insets[ai].bottom = Math.max(insets[ai].bottom, V / 2)
        } else if (aHasLBelow) {
          // 上块与同 entry 下段无缝，间距由下方外块 top 承担
          insets[bi].top = Math.max(insets[bi].top, V)
        } else if (bHasLAbove) {
          // 下块与同 entry 上段无缝，间距由上方外块 bottom 承担
          insets[ai].bottom = Math.max(insets[ai].bottom, V)
        } else {
          insets[bi].top = V / 2
          insets[ai].bottom = Math.max(insets[ai].bottom, V / 2)
        }
      }
    })
  })

  blocks.forEach((b, i) => {
    const { top, bottom } = insets[i]
    if (!top && !bottom) return
    b.top += top
    b.h = Math.max(BLOCK_MIN_SEG_H, b.h - top - bottom)
  })
}

/** 同 entry 竖直接缝微重叠，消除 L 形内角 subpixel 白线 */
function stitchSameEntryVerticalSeams(blocks) {
  const STITCH = 2
  const byEntry = {}
  blocks.forEach(b => {
    if (!byEntry[b.entryId]) byEntry[b.entryId] = []
    byEntry[b.entryId].push(b)
  })
  Object.values(byEntry).forEach(segs => {
    segs.sort((a, b) => a.top - b.top)
    for (let i = 0; i < segs.length - 1; i++) {
      const upper = segs[i]
      const lower = segs[i + 1]
      if (!hOverlap(upper, lower)) continue
      const joint = upper.top + upper.h
      if (Math.abs(lower.top - joint) > 2) continue
      if (upper.widthPct > lower.widthPct + 1) {
        // 上宽下窄（如晋惠帝→并列左臂）：下段微上提，消内角白线
        lower.top = joint - STITCH
        lower.h += STITCH
      } else if (lower.widthPct > upper.widthPct + 1) {
        // 上窄下宽（如晋 L 形→全宽）：上段微下延，不占用与外块间距
        upper.h += STITCH
      } else {
        lower.top = joint - STITCH
        lower.h += STITCH
      }
    }
  })
}

/** 两色块是否交叉（不同 entry，纵横向均重叠） */
function verticallyOverlaps(a, b) {
  return a.top < b.top + b.h - 0.5 && a.top + a.h > b.top + 0.5
}

function blocksCross(a, b) {
  if (a.entryId === b.entryId) return false
  // 同列宋帝上下承续（间距微调后可能纵向重叠）不算交叉
  if (SONG_REGIMES.has(a.dynasty) && SONG_REGIMES.has(b.dynasty) &&
      Math.abs(a.leftPct - b.leftPct) < 1 &&
      Math.abs(a.widthPct - b.widthPct) < 1) {
    return false
  }
  return verticallyOverlaps(a, b) && hOverlap(a, b)
}

/** 宋列目标宽度（画布 1/2） */
function calcSongHalfWidthPct(colCount = 3) {
  const G = BLOCK_H_GAP_PCT
  const usable = 100 - (colCount - 1) * G
  return usable / 2
}

function maxLeftColumnWidth(block) {
  if (SONG_REGIMES.has(block.dynasty)) return calcSongHalfWidthPct() + 0.5
  if (JIN_DYNASTY_NAMES.has(block.dynasty)) {
    return calcWeightedColumnGeometry([2, 1])[0].widthPct + 0.5
  }
  if (block.entryId === NANBEI_ENTRY_ID) {
    const twoThirds = calcWeightedColumnGeometry([2, 1])[0].widthPct
    const middleThird = calcWeightedColumnGeometry([1, 1, 1])[1].widthPct
    return Math.max(twoThirds, middleThird) + 0.5
  }
  const { widthPct } = calcColumnGeometry(3)
  return widthPct + 0.5
}

/** 硬性规则：不同帝王/政权色块不得交叉；非宋左列过宽还原为标准 1/3，宋列保持 1/2 */
function enforceNoBlockCrossing(blocks) {
  const { widthPct, G } = calcColumnGeometry(3)
  const leftLeft = slotLeftPct(0, widthPct, G)
  const songHalfW = calcSongHalfWidthPct()

  let changed = true
  while (changed) {
    changed = false
    for (let i = 0; i < blocks.length; i++) {
      for (let j = i + 1; j < blocks.length; j++) {
        if (!blocksCross(blocks[i], blocks[j])) continue
        ;[blocks[i], blocks[j]].forEach(b => {
          // 独 occupy 全宽（280 年后晋统一等）不参与左列 clamp
          if (b.widthPct >= 95) return
          const maxLeftW = maxLeftColumnWidth(b)
          if (b.leftPct <= leftLeft + 0.5 && b.widthPct > maxLeftW) {
            b.leftPct = leftLeft
            b.widthPct = SONG_REGIMES.has(b.dynasty) ? songHalfW : widthPct
            changed = true
          }
        })
      }
    }
  }
}

/**
 * 灭国 L 形：左列保持标准 1/3，中列填充标准中槽；
 * 同 entry 在列间距处补桥接段，不与被灭政权交叉。
 */
function finalizeConquerorLShape(blocks) {
  const slotKeys = ['三国·魏', '三国·蜀', '三国·吴']
  const { widthPct, G } = calcColumnGeometry(slotKeys.length)
  const leftLeft = slotLeftPct(0, widthPct, G)
  const leftRight = leftLeft + widthPct
  const midLeft = slotLeftPct(1, widthPct, G)
  const bridgeW = midLeft - leftRight

  const byEntry = {}
  blocks.forEach(b => {
    if (!byEntry[b.entryId]) byEntry[b.entryId] = []
    byEntry[b.entryId].push(b)
  })

  const bridges = []

  Object.values(byEntry).forEach(segs => {
    const fills = segs.filter(s => s.isConquestFill && !s.isLBridge)
    if (!fills.length) return

    fills.forEach(f => {
      f.leftPct = midLeft
      f.widthPct = widthPct
    })

    // 仅 L 形左臂（标准 1/3 宽）；全宽段（280 年后吴亡、晋独存）不还原
    segs.filter(s =>
      !s.isConquestFill && !s.isLBridge &&
      s.widthPct < 95 &&
      s.leftPct < midLeft
    ).forEach(left => {
      left.leftPct = leftLeft
      left.widthPct = widthPct
    })

    if (bridgeW > 0.1) {
      fills.forEach(f => {
        const hasLeftArm = segs.some(s =>
          !s.isConquestFill && !s.isLBridge &&
          s.widthPct < 95 &&
          s.leftPct <= leftLeft + 0.5 &&
          verticallyOverlaps(s, f)
        )
        if (!hasLeftArm) return
        bridges.push(Object.assign({}, f, {
          id:            `${f.entryId}_lbridge_${f.top}`,
          leftPct:       leftRight,
          widthPct:      bridgeW,
          isConquestFill: true,
          isLBridge:     true,
        }))
      })
    }
  })

  blocks.push(...bridges)
}

/** 南北朝：左列阶梯加宽（1/3→2/3→全宽）及与隋并列，段间右侧 L 桥接 */
function finalizeNanbeiLShape(blocks) {
  const segs = blocks.filter(b =>
    b.entryId === NANBEI_ENTRY_ID && !b.isLBridge && !b.isNanbeiLBridge
  )
  if (segs.length < 2) return

  segs.sort((a, b) => a.top - b.top)
  const bridges = []

  for (let i = 0; i < segs.length - 1; i++) {
    const upper = segs[i]
    const lower = segs[i + 1]
    const joint = upper.top + upper.h
    if (Math.abs(lower.top - joint) > 4) continue

    // 同左缘、下段更宽：右侧横臂（左 1/3→2/3→全宽）
    if (Math.abs(upper.leftPct - lower.leftPct) < 2 &&
        lower.widthPct > upper.widthPct + 2) {
      const bridgeLeft = upper.leftPct + upper.widthPct
      const bridgeW = lower.widthPct - upper.widthPct
      if (bridgeW > 0.5) {
        bridges.push(Object.assign({}, lower, {
          id:            `${NANBEI_ENTRY_ID}_nb_bridge_${joint}`,
          leftPct:       bridgeLeft,
          widthPct:      bridgeW,
          top:           joint - 2,
          h:             Math.max(BLOCK_MIN_SEG_H, lower.top - joint + 4),
          isNanbeiLBridge: true,
        }))
      }
      continue
    }

    // 全宽 → 右半（581 隋左、南北朝右）：精确相接，避免全宽+半宽双层
    if (upper.widthPct >= 95 && lower.widthPct < upper.widthPct - 8 &&
        lower.leftPct > upper.leftPct + 40) {
      if (lower.top < joint - 0.5) {
        upper.h = Math.max(BLOCK_MIN_SEG_H, lower.top - upper.top)
      }
    }
  }

  blocks.push(...bridges)
}

/** 金亡后宋由 1/4 扩至左半：窄上宽下补横向桥接成 L 形 */
function finalizeSongHalfLShape(blocks) {
  const halfW = calcSongHalfWidthPct(2)
  const byEntry = {}
  blocks.forEach(b => {
    if (!SONG_REGIMES.has(b.dynasty)) return
    if (b.isSongHalfLBridge) return
    if (!byEntry[b.entryId]) byEntry[b.entryId] = []
    byEntry[b.entryId].push(b)
  })

  const bridges = []
  Object.values(byEntry).forEach(segs => {
    segs.sort((a, b) => a.top - b.top)
    for (let i = 0; i < segs.length - 1; i++) {
      const upper = segs[i]
      const lower = segs[i + 1]
      if (upper.widthPct >= halfW - 1) continue
      if (lower.widthPct <= upper.widthPct + 1) continue
      // 仅「1/4 → 左半」显著扩宽时补 L 桥；并列布局微差（如 47%→50%）不生成
      if (lower.widthPct - upper.widthPct < 8) continue
      if (Math.abs(upper.leftPct - lower.leftPct) > 1) continue
      const joint = upper.top + upper.h
      if (Math.abs(lower.top - joint) > 4) continue
      const bridgeLeft = upper.leftPct + upper.widthPct
      const bridgeW = lower.widthPct - upper.widthPct
      if (bridgeW <= 0.5) continue
      bridges.push(Object.assign({}, lower, {
        id:            `${lower.entryId}_shlbridge_${joint}`,
        leftPct:       bridgeLeft,
        widthPct:      bridgeW,
        top:           joint - 2,
        h:             Math.max(BLOCK_MIN_SEG_H, lower.top - joint + 4),
        isSongHalfLBridge: true,
      }))
    }
  })
  blocks.push(...bridges)
}

/**
 * 列布局切换（如 1100 年三列→四列）时，同帝王可能被切成上下两段且 left/width 微差。
 * 薄过渡段并入下段；较厚段则对齐下段列宽，消除顶部错位。
 */
function finalizeColumnTransition(blocks) {
  const THIN = SLICE_H_MIN_RPX + 8
  const MAX_LEFT_D = 3
  const MAX_WIDTH_D = 2
  const STITCH = 2
  const toRemove = new Set()

  const byEntry = {}
  blocks.forEach(b => {
    if (b.isLBridge || b.isSongHalfLBridge || b.isNanbeiLBridge || b.isXiaowudiBridge) return
    if (!byEntry[b.entryId]) byEntry[b.entryId] = []
    byEntry[b.entryId].push(b)
  })

  Object.values(byEntry).forEach(segs => {
    segs.sort((a, b) => a.top - b.top)
    for (let i = 0; i < segs.length - 1; i++) {
      const upper = segs[i]
      const lower = segs[i + 1]
      if (toRemove.has(upper.id)) continue
      if (!sameEntryStacked(upper, lower)) continue

      const leftDelta = Math.abs(upper.leftPct - lower.leftPct)
      const widthDelta = Math.abs(upper.widthPct - lower.widthPct)
      // 大幅扩宽 L 形（如宋 1/4→左半、南北朝段间）交给专用桥接
      if (lower.widthPct - upper.widthPct >= 8) continue
      if (upper.entryId === NANBEI_ENTRY_ID || lower.entryId === NANBEI_ENTRY_ID) continue
      if (entryIdsMatch(upper.entryId, XIAOWUDI_ENTRY_ID) || entryIdsMatch(lower.entryId, XIAOWUDI_ENTRY_ID)) continue
      if (leftDelta >= MAX_LEFT_D || widthDelta >= MAX_WIDTH_D) continue

      if (upper.h <= THIN) {
        lower.top = upper.top
        lower.h = Math.max(BLOCK_MIN_SEG_H, upper.h + lower.h - STITCH)
        toRemove.add(upper.id)
      } else {
        upper.leftPct = lower.leftPct
        upper.widthPct = lower.widthPct
      }
    }
  })

  if (!toRemove.size) return blocks
  return blocks.filter(b => !toRemove.has(b.id))
}

/** 列布局切换后左缘微差（≤3%）→ 统一对齐，消除五代十国等卡片左边线台阶 */
function alignEntrySmallLeftJog(blocks) {
  const MAX_JOG = 3
  const byEntry = {}
  blocks.forEach(b => {
    if (b.isLBridge || b.isSongHalfLBridge || b.isNanbeiLBridge || b.isXiaowudiBridge) return
    if (!byEntry[b.entryId]) byEntry[b.entryId] = []
    byEntry[b.entryId].push(b)
  })
  Object.values(byEntry).forEach(segs => {
    if (segs.length < 2) return
    const minLeft = Math.min(...segs.map(s => s.leftPct))
    const maxLeft = Math.max(...segs.map(s => s.leftPct))
    if (maxLeft - minLeft < 0.01 || maxLeft - minLeft > MAX_JOG) return
    segs.forEach(s => { s.leftPct = minLeft })
  })
}

/** 兼容旧函数名（避免开发者工具缓存旧编译产物报错） */
function stitchSameEntryAdjacentColumns(blocks) {
  finalizeConquerorLShape(blocks)
  finalizeSongHalfLShape(blocks)
  finalizeNanbeiLShape(blocks)
  enforceNoBlockCrossing(blocks)
}

/** 同一 entry 多段：相邻列槽（含列间距）是否纵向重叠 */
function sameEntryColNeighbor(seg, other, side) {
  const segRight = seg.leftPct + seg.widthPct
  const segBottom = seg.top + seg.h
  const tol = BLOCK_H_GAP_PCT + 1.5
  const vOverlap = other.top < segBottom - 0.02 && other.top + other.h > seg.top + 0.02
  if (!vOverlap) return false
  if (side === 'right') {
    return other.leftPct >= segRight - 0.02 && other.leftPct <= segRight + tol
  }
  const otherRight = other.leftPct + other.widthPct
  return seg.leftPct >= otherRight - 0.02 && seg.leftPct <= otherRight + tol
}

/** 同 entry 上下段是否在同一接缝（允许 stitch 微重叠） */
function sameEntryStacked(upper, lower) {
  const STITCH_TOL = 4
  const joint = upper.top + upper.h
  const gap = lower.top - joint
  return gap >= -STITCH_TOL && gap <= 0.5 && hOverlap(upper, lower)
}

/** L 形 / 拼接块：判断四角是否为外轮廓（convex 角才圆角） */
function externalCornerFlags(seg, segs) {
  const others = segs.filter(s =>
    s !== seg && !s.isLBridge && !s.isSongHalfLBridge && !s.isNanbeiLBridge && !s.isXiaowudiBridge
  )
  const left = seg.leftPct
  const right = seg.leftPct + seg.widthPct
  const top = seg.top
  const bottom = seg.top + seg.h

  const occupiesNW = others.some(s => {
    const sr = s.leftPct + s.widthPct
    const sb = s.top + s.h
    return sr > left + 0.02 && s.leftPct < left + 0.02 &&
      sb > top - 0.02 && s.top < top + 0.02
  })
  const occupiesNE = others.some(s => {
    const sb = s.top + s.h
    return s.leftPct < right - 0.02 && s.leftPct + s.widthPct > right - 0.02 &&
      sb > top - 0.02 && s.top < top + 0.02
  })
  const occupiesSW = others.some(s => {
    const sr = s.leftPct + s.widthPct
    return sr > left + 0.02 && s.leftPct < left + 0.02 &&
      s.top + s.h > bottom - 0.02 && s.top < bottom + 0.02
  })
  const occupiesSE = others.some(s =>
    s.leftPct < right - 0.02 && s.leftPct + s.widthPct > right - 0.02 &&
    s.top + s.h > bottom - 0.02 && s.top < bottom + 0.02
  )

  const above = others.some(s => sameEntryStacked(s, seg))
  const below = others.some(s => sameEntryStacked(seg, s))
  const leftN = others.some(s => sameEntryColNeighbor(seg, s, 'left'))
  const rightN = others.some(s => sameEntryColNeighbor(seg, s, 'right'))

  return {
    rTL: !above && !leftN && !occupiesNW,
    rTR: !above && !rightN && !occupiesNE,
    rBL: !below && !leftN && !occupiesSW,
    rBR: !below && !rightN && !occupiesSE,
    above, below, leftN, rightN,
  }
}

/** 多段 entry 是否为不规则形（L 形等；同列同宽竖叠仍视为规则矩形） */
function isIrregularEntryShape(segs) {
  const real = segs.filter(s =>
    !s.isLBridge && !s.isSongHalfLBridge && !s.isNanbeiLBridge && !s.isXiaowudiBridge
  )
  if (real.length <= 1) return false
  const lefts = new Set(real.map(s => s.leftPct.toFixed(2)))
  const rights = new Set(real.map(s => (s.leftPct + s.widthPct).toFixed(2)))
  return !(lefts.size === 1 && rights.size === 1)
}

const XIAOWUDI_ENTRY_ID = 'zhong_hua_jin_si_ma_yao'

/** 晋孝武帝：上宽下窄右肩，消右侧偏下凸起（仅本 entry） */
function applyXiaowudiBlockPatch(blocks) {
  const segs = blocks.filter(b =>
    entryIdsMatch(b.entryId, XIAOWUDI_ENTRY_ID) && !b.isLBridge && !b.isNanbeiLBridge && !b.isXiaowudiBridge
  )
  if (segs.length < 2) return
  segs.sort((a, b) => a.top - b.top)
  const upper = segs[0]
  const lower = segs[1]
  if (lower.leftPct <= upper.leftPct + 1) return
  if (lower.widthPct >= upper.widthPct) return

  patchInternalSeamOverlap(segs)
  upper.h += 3
  lower.h += 1
  const upperRight = upper.leftPct + upper.widthPct
  if (lower.leftPct + lower.widthPct > upperRight + 0.2) {
    lower.widthPct = upperRight - lower.leftPct
  }
  upper.fillSeamFix = true
  lower.fillSeamFix = true
}

const JIN_SHILIU_GAP_ENTRY_IDS = [
  XIAOWUDI_ENTRY_ID,
  'zhong_hua_jin_si_ma_de_zong',
  'zhong_hua_jin_si_ma_de_wen',
]

/** 晋孝武帝/安帝/恭帝：右缘对齐十六国列，留 16rpx */
function applyJinShiliuGapPatch(blocks) {
  const shiliuLeft = Math.min(
    ...blocks.filter(b => b.entryId === 'merged_十六国').map(b => b.leftPct),
    100
  )
  if (shiliuLeft >= 100) return
  const targetRight = shiliuLeft - calcBlockHGapPct()

  JIN_SHILIU_GAP_ENTRY_IDS.forEach(id => {
    blocks.filter(b =>
      entryIdsMatch(b.entryId, id) && !b.isLBridge && !b.isXiaowudiBridge
    ).forEach(b => {
      const segRight = b.leftPct + b.widthPct
      if (segRight > shiliuLeft + 2 || segRight < shiliuLeft - 18) return
      if (Math.abs(segRight - targetRight) <= 0.05) return
      b.widthPct = Math.max(8, targetRight - b.leftPct)
    })
  })
}

/** 晋孝武帝/安帝/恭帝：恢复外缘圆角（避免 patch 后直角） */
function applyJinEmperorCornerPatch(blocks) {
  const R = BLOCK_RADIUS_RPX
  JIN_SHILIU_GAP_ENTRY_IDS.forEach(id => {
    const segs = blocks
      .filter(b => entryIdsMatch(b.entryId, id) && !b.isLBridge && !b.isXiaowudiBridge)
      .sort((a, b) => a.top - b.top)
    if (!segs.length) return

    if (segs.length === 1) {
      const s = segs[0]
      s.rTL = s.rTR = s.rBR = s.rBL = true
      s.radiusStyle = `${R}rpx ${R}rpx ${R}rpx ${R}rpx`
      return
    }

    const upper = segs[0]
    const lower = segs[segs.length - 1]
    const isStep = lower.leftPct > upper.leftPct + 1 && lower.widthPct < upper.widthPct

    if (isStep) {
      upper.rTL = true
      upper.rTR = true
      upper.rBR = false
      upper.rBL = false
      lower.rTL = false
      lower.rTR = true
      lower.rBR = true
      lower.rBL = false
      upper.radiusStyle = `${R}rpx ${R}rpx 0rpx 0rpx`
      lower.radiusStyle = `0rpx ${R}rpx ${R}rpx 0rpx`
    }
  })
}

/** 十六国底缘 patch 后：南北朝 439/581 缝合并补肩桥（仅 merged_南北朝） */
function applyNanbeiPostShiliuSeamFix(blocks) {
  const V = BLOCK_V_GAP_RPX
  const STITCH = 2
  const real = blocks
    .filter(b => b.entryId === NANBEI_ENTRY_ID && !b.isNanbeiLBridge && !b.isLBridge)
    .sort((a, b) => a.top - b.top)

  const clearSeam = (b) => {
    b.fillSeamFix = true
    b.edgeClass = ''
    b.edgeTop = b.edgeRight = b.edgeBottom = b.edgeLeft = false
  }

  for (let i = 0; i < real.length - 1; i++) {
    const upper = real[i]
    const lower = real[i + 1]
    if (Math.abs(upper.leftPct - lower.leftPct) > 1) continue
    const gap = lower.top - (upper.top + upper.h)
    const is439ShiliuGap = upper.widthPct < 70 && lower.widthPct > 95 && gap >= V - 1
    if (gap > 0.5 && gap <= V + 4 && !is439ShiliuGap) upper.h += gap
    let joint = upper.top + upper.h
    if (Math.abs(lower.top - joint) > V + 4) continue
    if (lower.widthPct > upper.widthPct + 1) {
      upper.h += STITCH
    } else if (upper.widthPct > lower.widthPct + 1) {
      lower.top = joint - STITCH
      lower.h += STITCH
    } else {
      lower.top = joint - STITCH
      lower.h += STITCH
    }
    upper.rBR = false
    lower.rTL = false
    clearSeam(upper)
    clearSeam(lower)
  }

  const twoThirds = real.find(s => s.widthPct > 60 && s.widthPct < 70 && s.top > 14400)
  const fullSeg = real.find(s => s.widthPct > 95 && twoThirds && s.top >= twoThirds.top)
  if (twoThirds && fullSeg) {
    const bridgeLeft = twoThirds.leftPct + twoThirds.widthPct
    const bridgeW = fullSeg.widthPct - twoThirds.widthPct
    const bridgeTop = fullSeg.top
    let br = blocks.find(b =>
      b.entryId === NANBEI_ENTRY_ID && b.isNanbeiLBridge &&
      Math.abs(b.leftPct - bridgeLeft) < 2 && b.top > twoThirds.top - 4
    )
    if (br && bridgeW > 0.5) {
      br.top = bridgeTop
      br.h = STITCH * 2
      br.widthPct = bridgeW
      clearSeam(br)
    } else if (bridgeW > 0.5) {
      blocks.push(Object.assign({}, fullSeg, {
        id:              `${NANBEI_ENTRY_ID}_nb_bridge_${bridgeTop}`,
        entryId:         NANBEI_ENTRY_ID,
        leftPct:         bridgeLeft,
        widthPct:        bridgeW,
        top:             bridgeTop,
        h:               STITCH * 2,
        isNanbeiLBridge: true,
        fillSeamFix:     true,
        radiusStyle:     '0 0 0 0',
        edgeClass:       '',
      }))
    }
    twoThirds.rBR = false
    fullSeg.rTL = false
    clearSeam(twoThirds)
    clearSeam(fullSeg)
  }

  blocks.filter(b => b.entryId === NANBEI_ENTRY_ID && b.isNanbeiLBridge).forEach(clearSeam)

  const R = BLOCK_RADIUS_RPX
  real.forEach(s => {
    s.radiusStyle = `${s.rTL ? R : 0}rpx ${s.rTR ? R : 0}rpx ${s.rBR ? R : 0}rpx ${s.rBL ? R : 0}rpx`
  })
}

/** 南北朝全宽→右半（581 隋左）+ 并列顶缘齐平（仅南北朝/隋文帝） */
function applyNanbeiFullToHalfTransitionFix(blocks) {
  const V = BLOCK_V_GAP_RPX
  const STITCH = 2
  const real = blocks
    .filter(b => b.entryId === NANBEI_ENTRY_ID && !b.isNanbeiLBridge && !b.isLBridge)
    .sort((a, b) => a.top - b.top)

  const clearSeam = (b) => {
    b.fillSeamFix = true
    b.edgeClass = ''
    b.edgeTop = b.edgeRight = b.edgeBottom = b.edgeLeft = false
  }

  for (let i = 0; i < real.length - 1; i++) {
    const upper = real[i]
    const lower = real[i + 1]
    const joint = upper.top + upper.h
    const isFullToRightHalf =
      upper.widthPct >= 95 && lower.widthPct < 55 && lower.leftPct > 40
    if (!isFullToRightHalf) continue
    if (lower.top < joint - 0.5) {
      upper.h = Math.max(BLOCK_MIN_SEG_H, lower.top - upper.top)
    }
    // 581 全宽→右半：垂直间距由 enforceNanbeiSui581VerticalGaps 统一处理，此处不 STITCH
  }

  const half581 = real.find(s =>
    s.widthPct < 55 && s.leftPct > 40 && s.top > 14600
  )
  const suiSegs = blocks
    .filter(b => entryIdsMatch(b.entryId, SUI_WENDI_ENTRY_ID))
    .sort((a, b) => a.top - b.top)
  if (!suiSegs.length) return

  const suiPar = suiSegs.find(s => s.leftPct < 5 && s.widthPct < 55)
  // 581 并列：隋文帝（左）顶缘与南北朝右半齐平
  if (half581 && suiPar) {
    const rowTop = half581.top
    const delta = rowTop - suiPar.top
    if (Math.abs(delta) > 0.5) {
      suiSegs.forEach(s => { if (s.top >= suiPar.top - 1) s.top += delta })
    }
  }

  const R = BLOCK_RADIUS_RPX
  const leftSegs = real.filter(s => s.leftPct <= 0.5)
  if (leftSegs.length) {
    const topLeft = leftSegs.reduce((a, b) => (a.top <= b.top ? a : b))
    const botLeft = leftSegs.reduce((a, b) =>
      (a.top + a.h >= b.top + b.h ? a : b)
    )
    leftSegs.forEach(s => {
      s.rTL = s === topLeft
      s.rBL = s === botLeft
    })
  }
  real.forEach(s => {
    s.radiusStyle = `${s.rTL ? R : 0}rpx ${s.rTR ? R : 0}rpx ${s.rBR ? R : 0}rpx ${s.rBL ? R : 0}rpx`
  })
}

/** 强制十六国底缘 +16rpx 至南北朝全宽顶；左列 2/3 下延无缝（仅十六国/南北朝） */
function enforceShiliuNanbei439Layout(blocks) {
  const V = BLOCK_V_GAP_RPX
  const STITCH = 2
  const R = BLOCK_RADIUS_RPX
  const shiliuSegs = blocks.filter(b => b.entryId === 'merged_十六国')
  if (!shiliuSegs.length) return

  const lastShiliu = shiliuSegs.reduce((a, b) =>
    (a.top + a.h >= b.top + b.h ? a : b)
  )
  const real = blocks
    .filter(b => b.entryId === NANBEI_ENTRY_ID && !b.isNanbeiLBridge && !b.isLBridge)
    .sort((a, b) => a.top - b.top)
  const twoThirds = real.find(s =>
    s.widthPct > 60 && s.widthPct < 70 && Math.abs(s.top - lastShiliu.top) < 8
  )
  const fullNb = real.find(s => s.widthPct > 95 && s.top >= lastShiliu.top - 8)
  if (!twoThirds || !fullNb) return

  const shiliuLeft = lastShiliu.leftPct

  // 全宽顶与十六国底之间精确 16rpx：不足则上收十六国末段
  let gap = fullNb.top - (lastShiliu.top + lastShiliu.h)
  if (gap < V - 0.5) {
    lastShiliu.h = Math.max(BLOCK_MIN_SEG_H, lastShiliu.h - (V - gap))
  }
  const sBot = lastShiliu.top + lastShiliu.h
  fullNb.top = sBot + V

  // 并列行底缘齐平（2/3 过渡段除外，稍后下延）
  shiliuSegs.forEach(s => {
    const rowBot = s.top + s.h
    blocks.filter(b =>
      b.entryId === NANBEI_ENTRY_ID && !b.isNanbeiLBridge &&
      b !== twoThirds &&
      Math.abs(b.top - s.top) < 4 &&
      b.leftPct < s.leftPct - 2 &&
      b.leftPct + b.widthPct <= s.leftPct + 2 &&
      b.top + b.h > rowBot + 0.5
    ).forEach(n => { n.h = Math.max(BLOCK_MIN_SEG_H, rowBot - n.top) })
  })

  // 左列 2/3 向下延至全宽顶（左列无缝；十六国列下方保留 16rpx 留白）
  twoThirds.h = Math.max(BLOCK_MIN_SEG_H, fullNb.top - twoThirds.top)

  // 移除十六国列下方留白区内的一切肩桥
  for (let i = blocks.length - 1; i >= 0; i--) {
    const b = blocks[i]
    if (b.entryId !== NANBEI_ENTRY_ID || !b.isNanbeiLBridge) continue
    if (b.leftPct + b.widthPct <= shiliuLeft + 0.5) continue
    if (b.top < fullNb.top - 0.5) blocks.splice(i, 1)
  }

  const bridgeLeft = twoThirds.leftPct + twoThirds.widthPct
  const bridgeW = fullNb.widthPct - twoThirds.widthPct
  const bridgeTop = fullNb.top
  const bridgeH = STITCH * 2
  if (bridgeW > 0.5) {
    const shoulderBridges = blocks.filter(b =>
      b.entryId === NANBEI_ENTRY_ID && b.isNanbeiLBridge &&
      b.leftPct + b.widthPct > shiliuLeft + 0.5 &&
      b.top >= fullNb.top - 1
    )
    shoulderBridges.slice(1).forEach(b => {
      const idx = blocks.indexOf(b)
      if (idx >= 0) blocks.splice(idx, 1)
    })
    const br = shoulderBridges[0]
    if (br) {
      br.top = bridgeTop
      br.leftPct = bridgeLeft
      br.widthPct = bridgeW
      br.h = bridgeH
    } else {
      blocks.push(Object.assign({}, fullNb, {
        id:              `${NANBEI_ENTRY_ID}_nb_bridge_${bridgeTop}`,
        entryId:         NANBEI_ENTRY_ID,
        leftPct:         bridgeLeft,
        widthPct:        bridgeW,
        top:             bridgeTop,
        h:               bridgeH,
        isNanbeiLBridge: true,
        fillSeamFix:     true,
        radiusStyle:     '0 0 0 0',
        edgeClass:       '',
      }))
    }
  }

  const clearSeam = (b) => {
    b.fillSeamFix = true
    b.edgeClass = ''
    b.edgeTop = b.edgeRight = b.edgeBottom = b.edgeLeft = false
  }

  // 439：2/3→全宽微重叠，消水平白线（全宽顶相对十六国仍 +16rpx）
  twoThirds.h += STITCH
  twoThirds.rBR = false
  fullNb.rTL = false

  blocks.filter(b =>
    b.entryId === NANBEI_ENTRY_ID && b.isNanbeiLBridge &&
    b.leftPct + b.widthPct > shiliuLeft + 0.5
  ).forEach(br => {
    br.top = fullNb.top - STITCH
    br.h = STITCH * 4
    clearSeam(br)
  })

  ;[twoThirds, fullNb].forEach(s => {
    clearSeam(s)
    s.rBR = s.rTL = false
  })
  twoThirds.rTR = true
  fullNb.rBL = fullNb.rBR = true
  blocks.filter(b => b.entryId === NANBEI_ENTRY_ID && b.isNanbeiLBridge).forEach(clearSeam)
  ;[twoThirds, fullNb].forEach(s => {
    s.radiusStyle = `${s.rTL ? R : 0}rpx ${s.rTR ? R : 0}rpx ${s.rBR ? R : 0}rpx ${s.rBL ? R : 0}rpx`
  })
}

const SUI_WENDI_ENTRY_ID = 'zhong_hua_sui_wen_di'
const SUI_YANGDI_ENTRY_ID = 'zhong_hua_sui_yang_di'

/** 隋文帝/炀帝：消右上白线 + 文帝与炀帝垂直 16rpx（仅隋文帝、隋炀帝） */
function enforceSuiLayout(blocks) {
  const V = BLOCK_V_GAP_RPX
  const STITCH = 2
  const R = BLOCK_RADIUS_RPX
  const wendi = blocks
    .filter(b => entryIdsMatch(b.entryId, SUI_WENDI_ENTRY_ID))
    .sort((a, b) => a.top - b.top)
  const yangdi = blocks.find(b => entryIdsMatch(b.entryId, SUI_YANGDI_ENTRY_ID))
  if (!wendi.length) return

  const clearSeam = (b) => {
    b.fillSeamFix = true
    b.edgeClass = ''
    b.edgeTop = b.edgeRight = b.edgeBottom = b.edgeLeft = false
  }

  const half581 = blocks.find(b =>
    b.entryId === NANBEI_ENTRY_ID && !b.isNanbeiLBridge &&
    b.widthPct < 55 && b.leftPct > 40 && b.top > 14600
  )
  const wendiPar = wendi.find(s => s.leftPct < 5 && s.widthPct < 55)
  const wendiFull = wendi.find(s => s.widthPct > 90)

  if (half581 && wendiPar && Math.abs(wendiPar.top - half581.top) > 0.5) {
    const delta = half581.top - wendiPar.top
    wendi.forEach(s => { if (s.top >= wendiPar.top - 1) s.top += delta })
  }

  const nbFullAbove = blocks.find(b =>
    b.entryId === NANBEI_ENTRY_ID && !b.isNanbeiLBridge &&
    b.widthPct > 95 && wendiPar && b.top + b.h <= wendiPar.top + BLOCK_V_GAP_RPX + 8
  )

  if (wendiPar) {
    clearSeam(wendiPar)
    // 581 并列顶与南北朝全宽底留 16rpx：顶缘不上扩 STITCH，避免侵占留白
    if (!nbFullAbove) {
      wendiPar.top -= STITCH
      wendiPar.h += STITCH
    }
    wendiPar.rTL = wendiPar.rTR = wendiPar.rBL = wendiPar.rBR = false
  }

  if (wendiPar && wendiFull) {
    clearSeam(wendiFull)
    const parBot = wendiPar.top + wendiPar.h
    wendiFull.top = parBot - STITCH
    wendiFull.h = Math.max(BLOCK_MIN_SEG_H, wendiFull.h + STITCH)
    wendiPar.rBR = false
    wendiFull.rTL = false
    wendiFull.rBL = wendiFull.rBR = true
  } else if (wendiFull) {
    clearSeam(wendiFull)
    wendiFull.rBL = wendiFull.rBR = true
  }

  if (wendiFull && yangdi) {
    clearSeam(yangdi)
    const fullBot = wendiFull.top + wendiFull.h
    yangdi.top = fullBot + V
    yangdi.rTL = yangdi.rTR = yangdi.rBL = yangdi.rBR = true
  }

  wendi.forEach(s => {
    s.radiusStyle = `${s.rTL ? R : 0}rpx ${s.rTR ? R : 0}rpx ${s.rBR ? R : 0}rpx ${s.rBL ? R : 0}rpx`
  })
  if (yangdi) {
    yangdi.radiusStyle = `${yangdi.rTL ? R : 0}rpx ${yangdi.rTR ? R : 0}rpx ${yangdi.rBR ? R : 0}rpx ${yangdi.rBL ? R : 0}rpx`
  }
}

/** 581 南北朝全宽/右半与隋文帝：左列对隋 16rpx；右列内无缝（仅这两段） */
function enforceNanbeiSui581VerticalGaps(blocks) {
  const V = BLOCK_V_GAP_RPX
  const STITCH = 2
  const hGap = calcBlockHGapPct()
  const R = BLOCK_RADIUS_RPX
  const nbReal = blocks
    .filter(b => b.entryId === NANBEI_ENTRY_ID && !b.isNanbeiLBridge && !b.isLBridge)
    .sort((a, b) => a.top - b.top)
  const wendi = blocks
    .filter(b => entryIdsMatch(b.entryId, SUI_WENDI_ENTRY_ID))
    .sort((a, b) => a.top - b.top)
  const wendiPar = wendi.find(s => s.leftPct < 5 && s.widthPct < 55 && s.top > 14600)
  const wendiFull = wendi.find(s => s.widthPct > 90)
  const nbHalf = nbReal.find(s => s.widthPct < 55 && s.leftPct > 40 && s.top > 14600)
  if (!wendiPar || !nbHalf) return

  const fullNb = nbReal.find(s => s.widthPct > 95 && s.top < nbHalf.top)
  const parTop = wendiPar.top
  const markGapEdge = (b, edges) => {
    b.seamGapTop = edges.top || false
    b.seamGapBottom = edges.bottom || false
    b.seamGapLeft = edges.left || false
    b.seamGapRight = edges.right || false
  }
  const clearSeam = (b) => {
    b.fillSeamFix = true
    b.edgeClass = ''
    b.edgeTop = b.edgeRight = b.edgeBottom = b.edgeLeft = false
  }

  for (let i = blocks.length - 1; i >= 0; i--) {
    const b = blocks[i]
    if (b.entryId === NANBEI_ENTRY_ID && b.isNanbei581VBridge) blocks.splice(i, 1)
  }

  const suiTargetRight = nbHalf.leftPct - hGap
  wendiPar.widthPct = Math.max(8, suiTargetRight - wendiPar.leftPct)
  const nbTargetLeft = wendiPar.leftPct + wendiPar.widthPct + hGap
  const nbRight = nbHalf.leftPct + nbHalf.widthPct
  nbHalf.leftPct = nbTargetLeft
  nbHalf.widthPct = Math.max(8, nbRight - nbTargetLeft)

  const parH = wendiFull
    ? Math.max(BLOCK_MIN_SEG_H, wendiFull.top - V - parTop)
    : nbHalf.h
  let stitchedHalfTop = false

  if (fullNb) {
    const leftGapBox = V + SOLID_SEAM_BLEED_V_RPX
    fullNb.h = Math.max(BLOCK_MIN_SEG_H, parTop - leftGapBox - fullNb.top)
    clearSeam(fullNb)
    markGapEdge(fullNb, { bottom: false })
    fullNb.rBR = false

    const fullBot = fullNb.top + fullNb.h
    nbHalf.top = fullBot - STITCH
    nbHalf.h = Math.max(
      BLOCK_MIN_SEG_H,
      wendiFull ? wendiFull.top - V - nbHalf.top : parTop + parH - nbHalf.top + STITCH
    )
    nbHalf.rTL = false
    stitchedHalfTop = true
  } else {
    nbHalf.top = parTop
    nbHalf.h = parH
  }

  clearSeam(nbHalf)
  markGapEdge(nbHalf, { left: true, bottom: !!wendiFull, top: false })
  clearSeam(wendiPar)
  markGapEdge(wendiPar, { top: true, right: true })
  if (wendiFull) {
    clearSeam(wendiFull)
    markGapEdge(wendiFull, { top: true })
  }

  wendiPar.rTR = true
  if (!stitchedHalfTop) nbHalf.rTL = true
  nbHalf.rTR = true
  const widerBelow = nbReal.some(o =>
    o.top >= nbHalf.top + nbHalf.h - 4 &&
    Math.abs(o.leftPct - nbHalf.leftPct) < 2 &&
    o.widthPct > nbHalf.widthPct + 5
  )
  if (!widerBelow) nbHalf.rBL = true
  wendiPar.radiusStyle = `${wendiPar.rTL ? R : 0}rpx ${wendiPar.rTR ? R : 0}rpx ${wendiPar.rBR ? R : 0}rpx ${wendiPar.rBL ? R : 0}rpx`
  nbHalf.radiusStyle = `${nbHalf.rTL ? R : 0}rpx ${nbHalf.rTR ? R : 0}rpx ${nbHalf.rBR ? R : 0}rpx ${nbHalf.rBL ? R : 0}rpx`
  if (fullNb) {
    fullNb.radiusStyle = `${fullNb.rTL ? R : 0}rpx ${fullNb.rTR ? R : 0}rpx ${fullNb.rBR ? R : 0}rpx ${fullNb.rBL ? R : 0}rpx`
  }
}

/** 439 南北朝 / 589 隋文帝：仅用填充层微扩盖住间距白线，不改色块几何 */
function applyNanbei439Sui589WhiteLineFix(blocks) {
  const V = BLOCK_V_GAP_RPX

  const setFillBleed = (b, top, bottom) => {
    if (!b) return
    b.fillSeamFix = true
    if (top > 0) {
      b.seamGapTop = false
      b._fillBleedTop = Math.max(b._fillBleedTop || 0, Math.ceil(top))
    }
    if (bottom > 0) {
      b.seamGapBottom = false
      b._fillBleedBottom = Math.max(b._fillBleedBottom || 0, Math.ceil(bottom))
    }
    const parts = []
    if (b._fillBleedTop) parts.push(`top: -${b._fillBleedTop}rpx`)
    if (b._fillBleedBottom) parts.push(`bottom: -${b._fillBleedBottom}rpx`)
    if (parts.length) b.fillStyleExtra = parts.join('; ') + ';'
  }

  const shiliuSegs = blocks.filter(b => b.entryId === 'merged_十六国')
  if (shiliuSegs.length) {
    const lastShiliu = shiliuSegs.reduce((a, b) =>
      (a.top + a.h >= b.top + b.h ? a : b)
    )
    const shiliuBot = lastShiliu.top + lastShiliu.h
    const fullNb439 = blocks.find(b =>
      b.entryId === NANBEI_ENTRY_ID && !b.isNanbeiLBridge &&
      b.widthPct > 95 && b.top >= shiliuBot - 2 && b.top <= shiliuBot + V + 4
    )
    if (fullNb439) {
      const gap = fullNb439.top - (lastShiliu.top + lastShiliu.h)
      if (gap > 0.5 && gap <= V + 4) {
        setFillBleed(fullNb439, gap, 0)
      }
      const twoThirds = blocks.find(b =>
        b.entryId === NANBEI_ENTRY_ID && !b.isNanbeiLBridge &&
        b.widthPct > 60 && b.widthPct < 70 &&
        Math.abs(b.top - lastShiliu.top) < 8
      )
      if (twoThirds) {
        const jointGap = fullNb439.top - (twoThirds.top + twoThirds.h)
        if (jointGap > 0.5) {
          setFillBleed(fullNb439, Math.max(gap > 0 ? gap : 0, jointGap), 0)
        }
        twoThirds.fillSeamFix = true
        twoThirds.seamGapBottom = false
      }
    }
  }

  const nbReal = blocks.filter(b =>
    b.entryId === NANBEI_ENTRY_ID && !b.isNanbeiLBridge && !b.isLBridge
  )
  const wendiPar = blocks.find(b =>
    entryIdsMatch(b.entryId, SUI_WENDI_ENTRY_ID) && b.leftPct < 5 && b.widthPct < 55 && b.top > 14600
  )
  const fullNb581 = nbReal.find(b =>
    b.widthPct > 95 && wendiPar &&
    wendiPar.top >= b.top + b.h - 2 &&
    wendiPar.top <= b.top + b.h + V + 8
  )
  if (fullNb581 && wendiPar) {
    const gap = wendiPar.top - (fullNb581.top + fullNb581.h)
    if (gap > 0.5) {
      setFillBleed(wendiPar, gap, 0)
      setFillBleed(fullNb581, 0, gap)
    }
  }
}

/** 十六国列底缘与下方南北朝：垂直留 16rpx（439 止点等） */
function applyShiliuNanbeiBottomGapPatch(blocks) {
  const V = BLOCK_V_GAP_RPX
  const shiliuSegs = blocks.filter(b => b.entryId === 'merged_十六国')
  if (!shiliuSegs.length) return

  const lastShiliu = shiliuSegs.reduce((a, b) =>
    (a.top + a.h >= b.top + b.h ? a : b)
  )
  const shiliuBot = lastShiliu.top + lastShiliu.h

  // 与十六国同行并列的南北朝（左列+右列，中间 16rpx）：底缘齐平
  shiliuSegs.forEach(s => {
    const sBot = s.top + s.h
    const sRight = s.leftPct
    blocks.filter(b =>
      b.entryId === NANBEI_ENTRY_ID &&
      !b.isNanbeiLBridge &&
      Math.abs(b.top - s.top) < 4 &&
      b.leftPct < sRight - 2 &&
      b.leftPct + b.widthPct <= sRight + 2 &&
      b.top + b.h > sBot + 0.5
    ).forEach(n => {
      n.h = Math.max(BLOCK_MIN_SEG_H, sBot - n.top)
    })
  })

  const nanbeiBelow = blocks.filter(b =>
    b.entryId === NANBEI_ENTRY_ID &&
    !b.isNanbeiLBridge &&
    b.top >= shiliuBot - 4 &&
    b.top <= shiliuBot + 24 &&
    hOverlap(lastShiliu, b)
  )
  if (!nanbeiBelow.length) return

  const shiftFrom = Math.min(...nanbeiBelow.map(b => b.top))
  const gap = shiftFrom - shiliuBot
  if (gap >= V - 0.5) return

  const delta = V - gap
  blocks.forEach(b => {
    if (b.entryId !== NANBEI_ENTRY_ID) return
    if (b.top >= shiftFrom - 1) b.top += delta
  })
}

/** 南北朝：左缘圆角 / 右肩阶梯无凸起 / 与十六国列间距（仅 merged_南北朝） */
function applyNanbeiBlockPatches(blocks) {
  // 移除侵入隋列的右桥（历史残留或误生成）
  for (let i = blocks.length - 1; i >= 0; i--) {
    const b = blocks[i]
    if (b.entryId !== NANBEI_ENTRY_ID || !b.isNanbeiLBridge) continue
    if (b.leftPct < 45) continue
    blocks.splice(i, 1)
  }

  const segs = blocks.filter(b => b.entryId === NANBEI_ENTRY_ID)
  if (!segs.length) return

  const real = segs.filter(s => !s.isNanbeiLBridge && !s.isLBridge)
  const minLeft = Math.min(...real.map(s => s.leftPct))
  const shiliuLeft = Math.min(
    ...blocks.filter(b => b.entryId === 'merged_十六国').map(b => b.leftPct),
    100
  )
  const R = BLOCK_RADIUS_RPX

  real.forEach(s => {
    const segRight = s.leftPct + s.widthPct
    const onLeft = s.leftPct <= minLeft + 0.5
    const widerBelow = real.some(o =>
      o.top >= s.top + s.h - 4 &&
      Math.abs(o.leftPct - s.leftPct) < 2 &&
      o.widthPct > s.widthPct + 5
    )
    // 左列阶梯：下接更宽段时仅右下直角（右上仍可与十六国相邻圆角）
    if (onLeft && widerBelow) {
      s.rBR = false
    }
    // 420–439 左 2/3 与十六国并列：交界处精确留 16rpx（全宽段 439+ 不调整）
    const hGap = calcBlockHGapPct()
    const targetRight = shiliuLeft - hGap
    if (onLeft && s.widthPct < 90 && shiliuLeft < 100 &&
        segRight > shiliuLeft - 8 && segRight <= shiliuLeft + 1) {
      if (Math.abs(segRight - targetRight) > 0.05) {
        s.widthPct = Math.max(8, targetRight - s.leftPct)
      }
      s.rTR = true
      if (!widerBelow) s.rBR = true
    }
    s.radiusStyle = `${s.rTL ? R : 0}rpx ${s.rTR ? R : 0}rpx ${s.rBR ? R : 0}rpx ${s.rBL ? R : 0}rpx`
  })

  const targetRight = shiliuLeft - calcBlockHGapPct()
  segs.filter(s => s.isNanbeiLBridge).forEach(br => {
    const r = br.leftPct + br.widthPct
    if (r <= shiliuLeft + 1 && r > shiliuLeft - 8 && Math.abs(r - targetRight) > 0.05) {
      br.widthPct = Math.max(1, targetRight - br.leftPct)
    }
  })

  const leftSegs = real.filter(s => s.leftPct <= minLeft + 0.5)
  if (leftSegs.length) {
    const topLeft = leftSegs.reduce((a, b) => (a.top <= b.top ? a : b))
    const botLeft = leftSegs.reduce((a, b) =>
      (a.top + a.h >= b.top + b.h ? a : b)
    )
    leftSegs.forEach(s => {
      s.rTL = s === topLeft
      s.rBL = s === botLeft
      s.radiusStyle = `${s.rTL ? R : 0}rpx ${s.rTR ? R : 0}rpx ${s.rBR ? R : 0}rpx ${s.rBL ? R : 0}rpx`
    })
  }

  segs.filter(s => s.isNanbeiLBridge).forEach(s => {
    s.radiusStyle = '0 0 0 0'
    s.fillSeamFix = true
  })

  // 581–589 隋左、南北朝右：交界精确留 16rpx
  const hGap = calcBlockHGapPct()
  const suiPar581 = blocks.find(b =>
    entryIdsMatch(b.entryId, SUI_WENDI_ENTRY_ID) && b.leftPct < 5 && b.widthPct < 55 && b.top > 14600
  )
  const nbHalf581 = real.find(s =>
    s.leftPct > 40 && s.widthPct < 55 && s.top > 14600
  )
  if (suiPar581 && nbHalf581) {
    const suiTargetRight = nbHalf581.leftPct - hGap
    if (Math.abs(suiPar581.leftPct + suiPar581.widthPct - suiTargetRight) > 0.05) {
      suiPar581.widthPct = Math.max(8, suiTargetRight - suiPar581.leftPct)
    }
    const nbTargetLeft = suiPar581.leftPct + suiPar581.widthPct + hGap
    const nbRight = nbHalf581.leftPct + nbHalf581.widthPct
    if (Math.abs(nbHalf581.leftPct - nbTargetLeft) > 0.05) {
      nbHalf581.leftPct = nbTargetLeft
      nbHalf581.widthPct = Math.max(8, nbRight - nbTargetLeft)
    }
    const widerBelow = real.some(o =>
      o.top >= nbHalf581.top + nbHalf581.h - 4 &&
      Math.abs(o.leftPct - nbHalf581.leftPct) < 2 &&
      o.widthPct > nbHalf581.widthPct + 5
    )
    suiPar581.rTR = true
    nbHalf581.rTL = true
    if (!widerBelow) nbHalf581.rBL = true
    suiPar581.radiusStyle = `${suiPar581.rTL ? R : 0}rpx ${suiPar581.rTR ? R : 0}rpx ${suiPar581.rBR ? R : 0}rpx ${suiPar581.rBL ? R : 0}rpx`
    nbHalf581.radiusStyle = `${nbHalf581.rTL ? R : 0}rpx ${nbHalf581.rTR ? R : 0}rpx ${nbHalf581.rBR ? R : 0}rpx ${nbHalf581.rBL ? R : 0}rpx`
  }
}

/** 时间锚定段：规则形取底行最右段，不规则形取底行最左段 */
function getTimeAnchorSeg(segs, irregular) {
  const real = segs.filter(s =>
    !s.isLBridge && !s.isSongHalfLBridge && !s.isNanbeiLBridge && !s.isXiaowudiBridge
  )
  if (!real.length) return segs[0]
  const EPS = 0.02
  const maxBottom = Math.max(...real.map(s => s.top + s.h))
  const bottomSegs = real.filter(s => Math.abs(s.top + s.h - maxBottom) < 2)
  if (!irregular) {
    return bottomSegs.reduce((a, b) =>
      (a.leftPct + a.widthPct) >= (b.leftPct + b.widthPct) ? a : b
    )
  }
  const minLeft = Math.min(...real.map(s => s.leftPct))
  const leftBottom = bottomSegs.filter(s => Math.abs(s.leftPct - minLeft) < EPS)
  if (leftBottom.length) {
    return leftBottom.reduce((a, b) => ((a.top + a.h) >= (b.top + b.h) ? a : b))
  }
  return bottomSegs.reduce((a, b) => (a.leftPct <= b.leftPct ? a : b))
}

/** 为同一 entry 的多段计算外轮廓边框，并生成统一标签/色条层 */
function finalizeEntryShape(segs) {
  if (!segs.length) return null
  const EPS = 0.02
  const minLeft = Math.min(...segs.map(s => s.leftPct))
  const maxRight = Math.max(...segs.map(s => s.leftPct + s.widthPct))
  const entryTop = Math.min(...segs.map(s => s.top))
  const entryBottom = Math.max(...segs.map(s => s.top + s.h))

  segs.forEach(seg => {
    // 桥接填充段：仅填色，不画边线、不圆角
    if (seg.isSongHalfLBridge || seg.isLBridge || seg.isNanbeiLBridge || seg.isXiaowudiBridge) {
      seg.edgeTop = seg.edgeRight = seg.edgeBottom = seg.edgeLeft = false
      seg.edgeClass = ''
      seg.radiusStyle = '0 0 0 0'
      return
    }

    const segRight = seg.leftPct + seg.widthPct
    const onLeft  = seg.leftPct <= minLeft + EPS
    const onRight = segRight >= maxRight - EPS
    const corners = externalCornerFlags(seg, segs)

    seg.edgeTop    = !corners.above
    seg.edgeRight  = onRight && !corners.rightN
    seg.edgeBottom = !corners.below
    seg.edgeLeft   = false
    seg.rTL = corners.rTL
    seg.rTR = corners.rTR
    seg.rBL = corners.rBL
    seg.rBR = corners.rBR

    const edges = []
    if (seg.edgeTop) edges.push('eb-t')
    if (seg.edgeRight) edges.push('eb-r')
    if (seg.edgeBottom) edges.push('eb-b')
    seg.edgeClass = edges.join(' ')
    const R = BLOCK_RADIUS_RPX
    seg.radiusStyle = `${seg.rTL ? R : 0}rpx ${seg.rTR ? R : 0}rpx ${seg.rBR ? R : 0}rpx ${seg.rBL ? R : 0}rpx`
  })

  const topSeg = segs[0]
  const hideLabels = entryIdInSet(topSeg.entryId, HIDE_LABEL_ENTRY_IDS)
  const hideTags = entryIdInSet(topSeg.entryId, HIDE_TAG_ENTRY_IDS)
  const hideTime = entryIdInSet(topSeg.entryId, HIDE_TIME_ENTRY_IDS) || !!topSeg.hideTime
  const headerLeftPct = topSeg.leftPct
  const headerWidthPct = topSeg.widthPct
  const headerTop = entryTop + HEADER_TOP_INSET
  const concurrentCount = topSeg.concurrentCount || 1
  const labelLayout = hideLabels ? 'default' : inferLabelLayout(concurrentCount)
  const labelMode = hideLabels ? 'hidden' : labelLayout

  const irregular = isIrregularEntryShape(segs)
  const timeAnchor = getTimeAnchorSeg(segs, irregular)
  const timeCorner = (irregular && !entryIdInSet(topSeg.entryId, TIME_CORNER_BR_IRREGULAR)) ? 'bl' : 'br'
  const timeFontRpx = fitCardTimeFontSize(timeAnchor.timeRange, timeAnchor.widthPct)

  const barSegs = segs.filter(s => Math.abs(s.leftPct - topSeg.leftPct) < EPS)
  let barTop = Math.min(...barSegs.map(s => s.top))
  let barBottom = Math.max(...barSegs.map(s => s.top + s.h))
  if (barTop <= entryTop + EPS) barTop += HEADER_TOP_INSET
  if (barBottom >= entryBottom - EPS) barBottom -= HEADER_TOP_INSET
  const barH = Math.max(20, barBottom - barTop)

  return {
    id:              `${topSeg.entryId}_chrome`,
    entryId:         topSeg.entryId,
    kind:            topSeg.kind,
    person:          topSeg.person,
    displayName:     topSeg.displayName,
    dynasty:         topSeg.dynasty,
    timeRange:       topSeg.timeRange,
    leftBorder:      topSeg.leftBorder,
    fillColor:       topSeg.fillColor,
    highlights:      topSeg.highlights || [],
    hideLabels,
    hideTags,
    hideTime,
    labelLayout,
    labelMode,
    barTop,
    barH,
    barLeftPct:      topSeg.leftPct,
    headerTop,
    headerLeftPct,
    headerWidthPct,
    timeCorner,
    timeWrapTop:     timeAnchor.top,
    timeWrapH:       timeAnchor.h,
    timeLeftPct:     timeAnchor.leftPct,
    timeWidthPct:    timeAnchor.widthPct,
    timeFontRpx,
  }
}

/** 灭国列槽填充：蜀亡后由当时魏帝（曹奂）占中列 */
function applyConquestColumnFills(rows, displayEntries, byEntry, civId) {
  CONQUEST_FILLS.forEach(rule => {
    const slotKeys = rule.slots
    const colIdx = slotKeys.indexOf(rule.fillSlot)
    if (colIdx < 0) return

    const conqueror = displayEntries.find(e =>
      (e.dynastyName === rule.conquerorDynasty || e.dynastyGroup === rule.conquerorDynasty) &&
      e.start <= rule.conquestYear && e.end > rule.conquestYear
    )
    if (!conqueror) return

    const { widthPct, G } = calcColumnGeometry(slotKeys.length)
    const fillLeft = slotLeftPct(colIdx, widthPct, G)
    const layoutKey = `${fillLeft.toFixed(1)}|${widthPct.toFixed(1)}|conquest`

    let seg = null
    const flush = () => {
      if (!seg) return
      if (!byEntry[conqueror.id]) byEntry[conqueror.id] = []
      byEntry[conqueror.id].push(Object.assign(
        finishBlockSeg(seg, conqueror, civId),
        { isConquestFill: true }
      ))
      seg = null
    }

    rows.forEach(row => {
      if (row.tS < rule.zoneStart || row.tS >= rule.zoneEnd) return
      if (row.tS < rule.conquestYear || row.tS >= conqueror.end) {
        flush()
        return
      }

      const slotOccupied = row.placements.some(p => {
        const e = displayEntries.find(x => x.id === p.id)
        return e && matchSlotKey(e, rule.fillSlot) && p.id !== conqueror.id
      })
      if (slotOccupied) {
        flush()
        return
      }

      const conquerorPresent = row.placements.some(p => p.id === conqueror.id)
      if (!conquerorPresent) {
        flush()
        return
      }

      if (!seg) {
        seg = {
          layoutKey,
          leftPct: fillLeft,
          widthPct,
          top: row.y,
          h: row.h,
          concurrentCount: row.concurrentRegimeCount || 1,
        }
      } else {
        seg.h += row.h
      }
    })
    flush()
  })
}

/** 从行网格生成政权块（同一政权跨列变化 → 多段拼接成不规则形） */
function buildBlocksFromRows(rows, displayEntries, civId) {
  const blocks = []
  const overlays = []
  const byEntry = {}

  displayEntries.forEach(entry => {
    if (regimeEra.entryOverlapsRegimeEra(entry)) return
    let seg = null
    rows.forEach(row => {
      const pl = row.placements.find(p => p.id === entry.id)
      if (!pl) {
        if (seg) {
          if (!byEntry[entry.id]) byEntry[entry.id] = []
          byEntry[entry.id].push(finishBlockSeg(seg, entry, civId))
          seg = null
        }
        return
      }
      const lk = `${pl.leftPct.toFixed(1)}|${pl.widthPct.toFixed(1)}`
      if (!seg || seg.layoutKey !== lk) {
        if (seg) {
          if (!byEntry[entry.id]) byEntry[entry.id] = []
          byEntry[entry.id].push(finishBlockSeg(seg, entry, civId))
        }
        seg = {
          layoutKey: lk,
          leftPct: pl.leftPct,
          widthPct: pl.widthPct,
          top: row.y,
          h: row.h,
          concurrentCount: row.concurrentRegimeCount || 1,
        }
      } else {
        seg.h += row.h
      }
    })
    if (seg) {
      if (!byEntry[entry.id]) byEntry[entry.id] = []
      byEntry[entry.id].push(finishBlockSeg(seg, entry, civId))
    }
  })

  regimeEra.buildRegimeEraBlocks(rows, displayEntries, civId, {
    entryToCardFields,
    BLOCK_MIN_SEG_H,
    BLOCK_H_GAP_PCT,
    BLOCK_V_GAP_RPX,
  }).forEach(b => {
    if (!byEntry[b.entryId]) byEntry[b.entryId] = []
    byEntry[b.entryId].push(b)
  })

  applyConquestColumnFills(rows, displayEntries, byEntry, civId)

  Object.keys(byEntry).forEach(entryId => {
    const segs = byEntry[entryId].sort((a, b) => a.top - b.top)
    segs.forEach(s => blocks.push(s))
  })

  applyInterBlockGaps(blocks)
  stitchSameEntryVerticalSeams(blocks)
  blocks.splice(0, blocks.length, ...finalizeColumnTransition(blocks))
  alignEntrySmallLeftJog(blocks)
  stitchSameEntryAdjacentColumns(blocks)
  applyEntryBlockPatches(blocks)

  Object.keys(byEntry).forEach(entryId => {
    const segs = blocks.filter(b => b.entryId === entryId).sort((a, b) => a.top - b.top)
    const chrome = finalizeEntryShape(segs)
    if (chrome) overlays.push(chrome)
  })

  applyNanbeiBlockPatches(blocks)
  applyXiaowudiBlockPatch(blocks)
  applyJinShiliuGapPatch(blocks)
  applyJinEmperorCornerPatch(blocks)
  applyShiliuNanbeiBottomGapPatch(blocks)
  applyNanbeiPostShiliuSeamFix(blocks)
  applyNanbeiFullToHalfTransitionFix(blocks)
  enforceShiliuNanbei439Layout(blocks)
  enforceSuiLayout(blocks)
  enforceNanbeiSui581VerticalGaps(blocks)
  applyNanbei439Sui589WhiteLineFix(blocks)
  applyIrregularSolidSeamFix(blocks)

  blocks.sort((a, b) => a.top - b.top || a.leftPct - b.leftPct)
  overlays.sort((a, b) => a.top - b.top || a.leftPct - b.leftPct)
  return { blocks, overlays }
}

function finishBlockSeg(seg, entry, civId) {
  const fields = entryToCardFields(entry, civId)
  return Object.assign({
    id:              `${entry.id}_${seg.top}`,
    entryId:         entry.id,
    legacyId:        entry.legacyId || '',
    top:             seg.top,
    h:               seg.h,
    leftPct:         seg.leftPct,
    widthPct:        seg.widthPct,
    concurrentCount: seg.concurrentCount || 1,
  }, fields)
}

/** 构建显示条目列表 */
function buildDisplayEntries(civId, expandedDynasties, civName, isHuaxia) {
  const civDyns = DYNASTIES_BY_CIV[civName] || []
  const displayEntries = []
  const mergedDone = new Set()

  civDyns.forEach(dyn => {
    if (dyn.name === '战国') return
    if (regimeEra.isExcludedRegimeDynasty(dyn)) return

    if (regimeEra.isRegimeOnlyDynasty(dyn)) {
      if (isHuaxia && !isSpringAutumnWarringExpanded(expandedDynasties, civName)) return
      displayEntries.push(regimeEra.buildRegimeOnlyEntry(dyn, parseYear))
      return
    }

    if (isMergedEraGroup(dyn.dynasty)) {
      if (mergedDone.has(dyn.dynasty)) return
      mergedDone.add(dyn.dynasty)
      const members = DYNASTY_GROUPS[civName][dyn.dynasty] || [dyn]
      const merged = buildMergedEraEntry(dyn.dynasty, members)
      if (merged) displayEntries.push(merged)
      return
    }

    const isExpanded = isHuaxia && (
      !!expandedDynasties[dyn.name] ||
      !!expandedDynasties[dyn.dynasty2] ||
      isDynastyExpanded(dyn.dynasty2, expandedDynasties, civName)
    )
    const emps = isExpanded ? (EMPERORS_BY_DYN[dyn.name] || []) : []

    if (isExpanded && emps.length > 0) {
      emps.forEach(emp => {
        displayEntries.push({
          id: emp.id, legacyId: emp.legacyId || '', isEmperor: true,
          dynastyName: dyn.name, dynastyGroup: dyn.dynasty,
          dynastyId: emp.dynastyId || dyn.dynastyId || '',
          regimeId: emp.regimeId || dyn.regimeId || dyn.id || '',
          civilizationId: emp.civilizationId || dyn.civilizationId || '',
          originalName: emp.originalName || '',
          displayName: emp.name,
          start: emp.start, end: emp.end, years: emp.years,
          colorIdx: dyn.colorIdx,
          tag: emp.tag || '',
        })
      })
    } else {
      displayEntries.push({
        id: dyn.id, legacyId: dyn.legacyId || '', isEmperor: false,
        dynastyName: dyn.name, dynastyGroup: dyn.dynasty,
        dynastyId: dyn.dynastyId || '',
        regimeId: dyn.regimeId || dyn.id || '',
        civilizationId: dyn.civilizationId || '',
        displayName: dyn.dynasty === dyn.name ? dyn.dynasty : dyn.name,
        start: dyn.start, end: dyn.end,
        years: dyn.end - dyn.start,
        colorIdx: dyn.colorIdx,
        startStr: dyn.startStr, endStr: dyn.endStr,
      })
    }
  })

  if (isHuaxia && !isSpringAutumnWarringExpanded(expandedDynasties, civName)) {
    displayEntries.push(buildCollapsedSpringWarringEntry())
  }

  return displayEntries
}

// ─── buildRows ────────────────────────────────────────────────────
function buildRows(civId, expandedDynasties) {
  expandedDynasties = expandedDynasties || {}
  const civName  = CIV_ID_TO_NAME[civId] || civId
  const isHuaxia = civId === 'huaxia'
  const civDyns  = DYNASTIES_BY_CIV[civName] || []
  const hxDyns   = DYNASTIES_BY_CIV['华夏']  || []

  const empty = { rows: [], blocks: [], overlays: [], totalH: 0 }
  if (civDyns.length === 0) return empty

  const displayEntries = buildDisplayEntries(civId, expandedDynasties, civName, isHuaxia)

  const timeSet = new Set()
  HUAXIA_AXIS_MARKS.forEach(m => timeSet.add(m.start))
  hxDyns.forEach(d => timeSet.add(d.end))
  displayEntries.forEach(e => { timeSet.add(e.start); timeSet.add(e.end) })
  const times = [...timeSet].sort((a, b) => a - b)

  const rawSlices = []
  for (let i = 0; i < times.length - 1; i++) {
    const tS = times[i]
    const tE = times[i + 1]
    if (tE <= tS) continue
    const active = displayEntries.filter(e => e.start <= tS && e.end > tS)
    const filtered = regimeEra.filterActiveForEra(active, tS)
    if (filtered.length === 0) continue
    const hxMark = HUAXIA_AXIS_BY_START[tS]
    rawSlices.push({
      tS, tE, active: filtered,
      hxLabel:      hxMark ? hxMark.label : '',
      hxDynastyKey: hxMark ? hxMark.dynastyKey : '',
    })
  }

  let prevPlacements = null
  const sliceRows = []
  rawSlices.forEach((sl, idx) => {
    const placements = assignPlacements(sl.active, prevPlacements, sl.tS, sl.tE, civName)
    prevPlacements = placements
    sliceRows.push(Object.assign({}, sl, {
      placements,
      pKey: placementKey(placements),
      idx,
    }))
  })

  // 合并布局相同的相邻时间片（减少碎段；遇华夏轴标注起点则不合并）
  const mergedSlices = []
  sliceRows.forEach(sl => {
    const last = mergedSlices[mergedSlices.length - 1]
    if (last && last.tE === sl.tS && !sl.hxLabel &&
        (last.pKey === sl.pKey || regimeEra.canMergeRegimeEraRow(last, sl))) {
      last.tE = sl.tE
      return
    }
    mergedSlices.push(Object.assign({}, sl))
  })

  let y = 0
  const rows = mergedSlices.map((sl, idx) => {
    const h = calcSliceH(sl.tS, sl.tE, sl.active)
    const expandable = isHuaxia && !!sl.hxLabel && isTimelineExpandable(sl.hxDynastyKey)
    const dynastyKey = sl.hxDynastyKey
    const expanded   = expandable && (
      dynastyKey === '春秋'
        ? isSpringAutumnWarringExpanded(expandedDynasties, civName)
        : isDynastyExpanded(dynastyKey, expandedDynasties, civName)
    )

    const row = {
      key:         `row_${sl.tS}_${idx}`,
      y,
      h,
      year:        fmtTimelineYear(sl.tS),
      hxLabel:     sl.hxLabel,
      expandable,
      expanded,
      dynastyKey,
      placements:  sl.placements,
      concurrentRegimeCount: countConcurrentRegimes(sl.tS, civName, sl.active),
      tS:          sl.tS,
      tE:          sl.tE,
    }
    y += h
    return row
  })

  let lastYearLabelY = -Infinity
  rows.forEach(row => {
    const forceYear = !!row.hxLabel || row.y <= 0
    row.showYear = forceYear || (row.y - lastYearLabelY >= TIME_YEAR_LABEL_MIN_GAP_RPX)
    if (row.showYear) lastYearLabelY = row.y
  })

  const { blocks, overlays } = buildBlocksFromRows(rows, displayEntries, civId)
  return { rows, blocks, overlays, totalH: y }
}

/**
 * 返回指定文明的"全部展开"状态对象（仅对有帝王数据的朝代展开）
 * @param {string} civId
 */
function buildAllExpanded(civId) {
  const civName = CIV_ID_TO_NAME[civId] || civId
  const dyns    = DYNASTIES_BY_CIV[civName] || []
  const result  = {}
  dyns.forEach(d => {
    if (isMergedEraGroup(d.dynasty)) return
    if (regimeEra.isRegimeOnlyDynasty(d)) return
    if (EMPERORS_BY_DYN[d.name] && EMPERORS_BY_DYN[d.name].length > 0) {
      result[d.name] = true
    }
  })
  HUAXIA_AXIS_MARKS.forEach(m => {
    if (isMergedEraGroup(m.dynastyKey)) return
    if (regimeEra.isRegimeOnlyEraGroup(m.dynastyKey)) return
    const members = getDrawerMembers(m.dynastyKey, civName)
    if (members.length > 0 && members.some(d => result[d.name])) {
      result[m.dynastyKey] = true
    }
  })
  return result
}

module.exports = {
  CIV_TABS,
  initialCiv,
  buildRows,
  buildAllExpanded,
  toggleDynastyExpanded,
  loadMatrixData,
}
