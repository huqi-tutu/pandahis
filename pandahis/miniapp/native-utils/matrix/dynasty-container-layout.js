/**
 * 乱世朝代 · 矩阵「一级容器 + 二级帝王卡」通用布局
 *
 * 规范与接入步骤见：.cursor/skills/dynasty-container-matrix/SKILL.md
 * 试点：三国（220–265 一级容器，魏/蜀/吴三列二级卡）
 *
 * 外层：与普通一级色块相同——buildBlocksFromRows + 时间轴切片
 * 内层：多列堆叠二级卡，高度不与坐标轴关联
 */

const CONTAINER_RADIUS_RPX = 16
const CONTAINER_INSET_PCT = 3.2
const CONTAINER_COL_GAP_PCT = 1.6
const SUB_CARD_H_RPX = 120
const SUB_CARD_H_NANBEI_RPX = 80
const SUB_CARD_GAP_RPX = 8
/** 辽/金容器内：与左通道帝王卡一致的垂直间距 */
const FIT_CONTAINER_SUB_CARD_GAP_RPX = 16
/** 辽/金容器内边距（略小于默认，把空间留给二级卡） */
const FIT_CONTAINER_SUB_CARD_PAD_RPX = 16
/** 辽/金：堆叠区占满可用内高（不扩容器、不溢出） */
const FIT_CONTAINER_STACK_FILL_RATIO = 1
/** 辽/金矮卡：缩小名称与卡顶间距，把空间留给在位时间 */
const FIT_COMPACT_HEADER_INSET_RPX = 2
/** 二级卡与外层容器之间的内边距（顶/底/侧视觉留白） */
const SUB_CARD_PAD_RPX = 24
/** 补偿 buildBlocks 垂直间距对容器底缘的占用，保证底内边距生效 */
const CONTAINER_BLOCK_GAP_RESERVE_RPX = 16
/** 展开容器顶部的朝代名 + 时间行 */
const CONTAINER_DYNASTY_HEADER_H_RPX = 56
const CONTAINER_DYNASTY_HEADER_IDS = new Set(['春秋', '战国', '三国', '南北朝', '五代十国', '辽', '金', '元', '清'])
/** 收起态朝代卡展示标签；展开态容器顶栏仅保留名称+时间 */

/** 五代十国首行：后梁/后唐/后晋/后汉/后周 竖排政权名 */
const WUDAI_FIVE_REGIME_KEYS = new Set(['后梁', '后唐', '后晋', '后汉', '后周'])

const songLiaoJin = require('./song-liao-jin-layout.js')
const mingQing = require('./ming-qing-layout.js')
const { getMatrixHighlights, buildHighlightTagList } = require('./matrix-highlights.js')

/** 容器内相对坐标（0–100%）→ 画布绝对 left/width 百分比 */
function toCanvasSubCardGeom(containerBlock, innerLeftPct, innerWidthPct) {
  const scale = containerBlock.widthPct / 100
  return {
    leftPct: containerBlock.leftPct + innerLeftPct * scale,
    widthPct: innerWidthPct * scale,
  }
}

function containerDynastyHeaderReserve(containerId) {
  if (!CONTAINER_DYNASTY_HEADER_IDS.has(containerId)) return 0
  return CONTAINER_DYNASTY_HEADER_H_RPX
}

function usesContainerDynastyHeader(containerId) {
  return CONTAINER_DYNASTY_HEADER_IDS.has(containerId)
}

function resolveContainerHeaderTimeRange(containerId, layout, displayEntries, fmtRange) {
  const entries = (displayEntries || []).filter(e => e.containerId === containerId)
  if (containerId === '三国' && entries.length && typeof fmtRange === 'function') {
    const start = Math.min(...entries.map(e => e.start))
    const end = Math.max(...entries.map(e => e.end))
    const startEntry = entries.reduce((a, b) => (a.start <= b.start ? a : b))
    const endEntry = entries.reduce((a, b) => (a.end >= b.end ? a : b))
    return fmtRange(
      start,
      end,
      startEntry.startStr || String(start),
      endEntry.endStr || String(end)
    )
  }
  const timelineEnd = getContainerTimelineEnd(layout)
  return fmtRange(layout.start, timelineEnd, String(layout.start), String(timelineEnd))
}

function isContainerSubRegimeLabel(containerId, emp, fields) {
  if (emp.isRegimeOnly) return true
  if (containerId === '南北朝') return fields.kind === 'dynasty' && !emp.isEmperor
  if (containerId === '五代十国') return fields.kind === 'dynasty' && !emp.isEmperor
  return false
}

/** 二级卡片：中性亚麻纸感 — 不带色相，仅微调明度 */
/** 方案A（春秋）：暖白中性 — 比纯白降低 2-3 档明度 */
const SUB_CARD_BG_A =
  'linear-gradient(180deg, #FAF8F5 0%, #F2F0EC 100%)'
/** 方案B（战国）：冷白中性 — 比纯白降低 2-3 档明度 */
const SUB_CARD_BG_B =
  'linear-gradient(180deg, #F5F6F8 0%, #EDEEF0 100%)'
/** 三国等其余容器：中间中性 */
const SUB_CARD_BG_NEUTRAL =
  'linear-gradient(180deg, #F8F7F5 0%, #F0EFED 100%)'
const SUB_CARD_STROKE = 'box-shadow: inset 0 0 0 1rpx rgba(255,255,255,.65)'

const REGIME_TO_DYNASTY_KEY = {
  '三国·魏': '三国',
  '三国·蜀': '三国',
  '三国·吴': '三国',
  '春秋':   '春秋',
  '齐':     '春秋',
  '楚':     '春秋',
  '燕':     '春秋',
  '晋':     '春秋',
  '宋':     '春秋',
  '韩':     '战国',
  '赵':     '战国',
  '魏':     '战国',
  '后梁':   '五代十国',
  '后唐':   '五代十国',
  '后晋':   '五代十国',
  '后汉':   '五代十国',
  '后周':   '五代十国',
  '辽':     '辽',
  '金':     '金',
  '元':     '元',
}

/** timelineEnd：大卡片在时间轴上的结束年（与轴标衔接，避免与西晋等重叠） */
const DYNASTY_CONTAINER_LAYOUTS = {
  三国: {
    dynastyKey: '三国',
    start: 220,
    timelineEnd: 266,
    columns: [
      { key: '三国·魏' },
      { key: '三国·蜀' },
      { key: '三国·吴' },
    ],
  },
  春秋: {
    dynastyKey: '春秋',
    start: -770,
    timelineEnd: -476,
    columns: [
      { key: '东周' },
      { key: '齐' },
      { key: '秦' },
      { key: '楚' },
      { key: '宋' },
      { key: '晋' },
    ],
  },
  战国: {
    dynastyKey: '战国',
    start: -475,
    timelineEnd: -221,
    columns: [
      { key: '东周' },
      { key: '齐' },
      { key: '秦' },
      { key: '楚' },
      { key: '燕' },
      { key: '韩' },
      { key: '赵' },
      { key: '魏' },
    ],
  },
  南北朝: {
    dynastyKey: '南北朝',
    start: 420,
    timelineEnd: 589,
    rows: [
      { columns: [
        { key: '北魏' },
        { key: '东魏' },
        { key: '西魏' },
        { key: '北齐' },
        { key: '北周' },
      ]},
      { columns: [
        { key: '南朝·宋' },
        { key: '南朝·齐' },
        { key: '南朝·梁' },
        { key: '南朝·陈' },
      ]},
    ],
  },
  五代十国: {
    dynastyKey: '五代十国',
    start: 907,
    timelineEnd: 960,
    rows: [
      { columns: [
        { key: '后梁' },
        { key: '后唐' },
        { key: '后晋' },
        { key: '后汉' },
        { key: '后周' },
      ]},
      { columns: [
        { key: '十国·吴' },
        { key: '十国·前蜀' },
        { key: '十国·吴越' },
        { key: '十国·闽' },
        { key: '十国·南汉' },
        { key: '十国·南平' },
        { key: '十国·后蜀' },
        { key: '十国·南唐' },
        { key: '十国·北汉' },
      ]},
    ],
  },
  辽: {
    dynastyKey: '辽',
    start: 907,
    timelineEnd: 1127,
    columns: [{ key: '辽' }],
  },
  金: {
    dynastyKey: '金',
    start: 1115,
    timelineEnd: 1234,
    columns: [{ key: '金' }],
  },
  元: {
    dynastyKey: '元',
    start: 1260,
    timelineEnd: 1368,
    columns: [{ key: '元' }],
    fullWidth: true,
  },
  清: {
    dynastyKey: '清',
    start: 1626,
    timelineEnd: 1912,
    columns: [{ key: '清' }],
    fullWidth: true,
  },
}

function getContainerTimelineEnd(layout) {
  return layout.timelineEnd != null ? layout.timelineEnd : layout.end
}

function buildHuaxiaDynastyColorMap(axisMarks, eraColorCount) {
  const map = {}
  const marks = axisMarks || []
  marks.forEach((m, i) => {
    map[m.dynastyKey] = i % eraColorCount
  })

  const colorAtLabel = label => {
    const idx = marks.findIndex(m => m.label === label)
    return idx >= 0 && eraColorCount > 0 ? idx % eraColorCount : null
  }

  // 两晋轴标合并收展，但西晋/东晋仍按各自轴位 % 6 取色
  const xijinColor = colorAtLabel('西晋')
  const dongjinColor = colorAtLabel('东晋')
  if (xijinColor != null) map['西晋'] = xijinColor
  if (dongjinColor != null) {
    map['东晋'] = dongjinColor
    map['十六国'] = dongjinColor
  }

  // 北宋/辽、南宋/金：并行政权同色；元明清保持 forEach 中的轴位色
  const beisongColor = colorAtLabel('北宋')
  const nansongColor = colorAtLabel('南宋')
  if (beisongColor != null) {
    map['北宋'] = beisongColor
    map['辽'] = beisongColor
  }
  if (nansongColor != null) {
    map['南宋'] = nansongColor
    map['金'] = nansongColor
  }

  return map
}

function resolveHuaxiaDynastyKey(dyn, colorMap) {
  if (!dyn) return ''
  if (dyn.name === '十六国' || dyn.dynasty === '十六国') {
    return colorMap['东晋'] != null ? '东晋' : '十六国'
  }
  if (dyn.id === 'ZQ_HX_CHUNQIU_QINZHUHOU') return '春秋'
  if (REGIME_TO_DYNASTY_KEY[dyn.name]) return REGIME_TO_DYNASTY_KEY[dyn.name]
  const candidates = [dyn.dynasty2, dyn.dynasty_zy, dyn.dynasty, dyn.name]
  for (const k of candidates) {
    if (k && colorMap[k] != null) return k
  }
  return dyn.name || ''
}

function assignHuaxiaDynastyColorIndices(civName, dynastiesByCiv, axisMarks, eraColorCount) {
  const colorMap = buildHuaxiaDynastyColorMap(axisMarks, eraColorCount)
  const list = dynastiesByCiv[civName] || []
  list.forEach(dyn => {
    const key = resolveHuaxiaDynastyKey(dyn, colorMap)
    dyn.dynastyColorKey = key
    dyn.colorIdx = colorMap[key] != null ? colorMap[key] : 0
  })
  return colorMap
}

function getHuaxiaDynastyColorIdx(dyn, colorMap) {
  const key = resolveHuaxiaDynastyKey(dyn, colorMap)
  return colorMap[key] != null ? colorMap[key] : 0
}

const REGIME_CONTAINER_IDS = new Set(['春秋', '战国', '五代十国'])

function isRegimeContainerExpanded(containerId, expandedDynasties) {
  if (containerId === '五代十国') {
    return songLiaoJin.isWudaiExpanded(expandedDynasties)
  }
  return !!(expandedDynasties && expandedDynasties[containerId])
}

function isDynastyContainerActive(containerId, expandedDynasties) {
  const layout = DYNASTY_CONTAINER_LAYOUTS[containerId]
  if (!layout) return false
  if (!expandedDynasties) return false
  if (containerId === '辽') {
    return songLiaoJin.isLiaoContainerActive(expandedDynasties)
  }
  if (containerId === '金') {
    return songLiaoJin.isJinContainerActive(expandedDynasties)
  }
  if (containerId === '元') {
    return songLiaoJin.isYuanContainerActive(expandedDynasties)
  }
  if (containerId === '清') {
    return mingQing.isQingContainerActive(expandedDynasties)
  }
  if (REGIME_CONTAINER_IDS.has(containerId)) {
    return isRegimeContainerExpanded(containerId, expandedDynasties)
  }
  if (expandedDynasties[containerId]) return true
  if (layout.columns) return layout.columns.some(col => !!expandedDynasties[col.key])
  if (layout.rows) {
    return layout.rows.some(row =>
      row.columns.some(col => !!expandedDynasties[col.key])
    )
  }
  return false
}

function filterEntriesForTimeSlices(displayEntries, expandedDynasties) {
  return (displayEntries || []).filter(e => {
    if (!e.containerId) return true
    if (REGIME_CONTAINER_IDS.has(e.containerId)) return false
    if (!isDynastyContainerActive(e.containerId, expandedDynasties)) return true
    return false
  })
}

function getEmperorReignYears(emp) {
  const span = (emp.end - emp.start) || emp.years || 1
  return Math.max(1, span)
}

/** 最密列：每张固定 SUB_CARD_H_RPX，得到列总高 */
function calcUniformColumnStackHeight(cardCount) {
  if (!cardCount) return 0
  return cardCount * SUB_CARD_H_RPX + Math.max(0, cardCount - 1) * SUB_CARD_GAP_RPX
}

function calcColumnStackHeight(cardCount) {
  return calcUniformColumnStackHeight(cardCount)
}

/**
 * 同一容器内各列对齐到 targetStackH。
 * 最密列（张数=maxCount）：每张 120rpx；
 * 其余列：在 targetStackH 内按在位时长等比分配各卡高度。
 */
function calcColumnCardHeights(emperors, targetStackH, isDenseColumn, minCardH = SUB_CARD_H_RPX, gapRpx = SUB_CARD_GAP_RPX) {
  const n = emperors.length
  if (!n || targetStackH <= 0) return []

  const gapTotal = Math.max(0, n - 1) * gapRpx
  const cardArea = targetStackH - gapTotal
  if (n === 1) return [{ emp: emperors[0], h: Math.max(minCardH, cardArea) }]

  if (isDenseColumn) {
    const uniform = Math.floor(cardArea / n)
    return emperors.map(emp => ({ emp, h: Math.max(minCardH, uniform) }))
  }

  const weights = emperors.map(getEmperorReignYears)
  const totalWeight = weights.reduce((a, b) => a + b, 0)
  const minTotal = n * minCardH
  let heights

  if (minTotal >= cardArea) {
    heights = weights.map(w => Math.floor(cardArea * w / totalWeight))
  } else {
    const extra = cardArea - minTotal
    heights = weights.map(w =>
      Math.floor(minCardH + extra * w / totalWeight)
    )
  }

  let used = heights.reduce((a, b) => a + b, 0)
  for (let i = 0; used < cardArea; i += 1) {
    heights[i % n] += 1
    used += 1
  }
  while (used > cardArea) {
    const idx = heights.findIndex(h => h > minCardH)
    if (idx < 0) break
    heights[idx] -= 1
    used -= 1
  }

  heights = heights.map(h => Math.max(minCardH, h))
  return emperors.map((emp, idx) => ({ emp, h: heights[idx] }))
}

/** 清容器：按在位时长等比分配，支持每张卡不同最小高度，严格不超出 stackH */
function calcQingStackCardHeights(emperors, stackH, gapRpx, minForEmp) {
  const n = emperors.length
  if (!n || stackH <= 0) return []

  const gapTotal = Math.max(0, n - 1) * gapRpx
  const cardArea = Math.max(0, stackH - gapTotal)
  if (n === 1) {
    const minH = minForEmp(emperors[0])
    return [{ emp: emperors[0], h: Math.min(cardArea, Math.max(minH, cardArea)) }]
  }

  const weights = emperors.map(getEmperorReignYears)
  const totalWeight = weights.reduce((a, b) => a + b, 0)
  const mins = emperors.map(minForEmp)
  const minTotal = mins.reduce((a, b) => a + b, 0)
  let heights

  if (minTotal >= cardArea) {
    heights = weights.map((w, i) => Math.floor(cardArea * w / totalWeight))
  } else {
    const extra = cardArea - minTotal
    heights = weights.map((w, i) =>
      Math.floor(mins[i] + extra * w / totalWeight)
    )
  }

  let used = heights.reduce((a, b) => a + b, 0)
  for (let i = 0; used < cardArea; i += 1) {
    heights[i % n] += 1
    used += 1
  }
  while (used > cardArea) {
    const idx = heights.findIndex((h, i) => h > mins[i])
    if (idx < 0) break
    heights[idx] -= 1
    used -= 1
  }

  heights = heights.map((h, i) => Math.max(mins[i], h))
  used = heights.reduce((a, b) => a + b, 0)
  while (used > cardArea) {
    const idx = heights.findIndex((h, i) => h > mins[i])
    if (idx < 0) break
    heights[idx] -= 1
    used -= 1
  }

  return emperors.map((emp, idx) => ({ emp, h: heights[idx] }))
}

/** 单列容器：在可用高度内等分各帝王卡（辽/金） */
function isFitToContainerId(containerId) {
  return containerId === '辽' || containerId === '金'
}

function isYuanContainerId(containerId) {
  return containerId === '元'
}

function isQingContainerId(containerId) {
  return containerId === '清'
}

const YUAN_CONTAINER_START = 1260
const YUAN_CONTAINER_END = 1368
const YUAN_SHIZU_REIGN_END = 1294
/** 元容器二级帝王卡最低高度（保证庙号+时间完整展示） */
const YUAN_EMPEROR_MIN_CARD_H_RPX = 96
const YUAN_SHIZU_MIN_CARD_H_RPX = 120
/** 元二级卡：高于容器底色(3)、低于南宋末帝(5) */
const YUAN_SUB_CARD_Z_INDEX = 4
const YUAN_CONTAINER_HIT_Z_INDEX = 4
const YUAN_SUB_OVERLAY_Z_INDEX = 18
/** 元容器内非宋区域点击 → 元朝详情 */
const YUAN_NAV_FIELDS = {
  entityType: 'regime',
  entityId: 'ZQ_HX_YUAN_YUAN',
  dynastyId: 'CD_HX_YUAN',
  dynasty: '元',
  displayName: '元',
  person: '',
  kind: 'dynasty',
  navigateContainerId: '元',
}

const QING_CONTAINER_START = mingQing.QING_CONTAINER_START
const QING_CONTAINER_END = mingQing.QING_CONTAINER_END
const QING_EARLY_END = 1661
const QING_TAIZONG_REIGN_END = 1643
const QING_EMPEROR_MIN_CARD_H_RPX = 56
const QING_TAIZONG_MIN_CARD_H_RPX = 72
const QING_SUB_CARD_Z_INDEX = 4
const QING_CONTAINER_HIT_Z_INDEX = 4
const QING_SUB_OVERLAY_Z_INDEX = 18
const QING_NAV_FIELDS = {
  entityType: 'regime',
  entityId: 'ZQ_HX_QING_QING',
  dynastyId: 'CD_HX_QING',
  dynasty: '清',
  displayName: '清',
  person: '',
  kind: 'dynasty',
  navigateContainerId: '清',
}

const CHUNQIU_NAV_FIELDS = {
  entityType: 'regime',
  entityId: 'HX-CQ',
  legacyId: 'HX-CQ',
  dynastyId: 'CD_HX_CHUNQIU',
  dynasty: '春秋',
  displayName: '春秋',
  person: '',
  kind: 'dynasty',
  navigateContainerId: '春秋',
}

const ZHANGUO_NAV_FIELDS = {
  entityType: 'regime',
  entityId: 'HX-ZG',
  legacyId: 'HX-ZG',
  dynastyId: 'CD_HX_ZHANGUO',
  dynasty: '战国',
  displayName: '战国',
  person: '',
  kind: 'dynasty',
  navigateContainerId: '战国',
}

const NANBEI_NAV_FIELDS = {
  entityType: 'regime',
  entityId: 'CD_HX_NANBEICHAO',
  dynastyId: 'CD_HX_NANBEICHAO',
  dynasty: '南北朝',
  displayName: '南北朝',
  person: '',
  kind: 'dynasty',
  navigateContainerId: '南北朝',
}

const WUDAI_NAV_FIELDS = {
  entityType: 'regime',
  entityId: 'CD_HX_WUDAISHIGUO',
  dynastyId: 'CD_HX_WUDAISHIGUO',
  dynasty: '五代十国',
  displayName: '五代十国',
  person: '',
  kind: 'dynasty',
  navigateContainerId: '五代十国',
}

const LIAO_NAV_FIELDS = {
  entityType: 'regime',
  entityId: 'ZQ_HX_LIAO_LIAO',
  legacyId: 'HX-L',
  dynastyId: 'CD_HX_LIAO',
  dynasty: '辽',
  displayName: '辽',
  person: '',
  kind: 'dynasty',
  navigateContainerId: '辽',
}

const JIN_NAV_FIELDS = {
  entityType: 'regime',
  entityId: 'ZQ_HX_JIN_JIN',
  legacyId: 'HX-J',
  dynastyId: 'CD_HX_JIN',
  dynasty: '金',
  displayName: '金',
  person: '',
  kind: 'dynasty',
  navigateContainerId: '金',
}

const CONTAINER_NAV_FIELDS = {
  春秋: CHUNQIU_NAV_FIELDS,
  战国: ZHANGUO_NAV_FIELDS,
  南北朝: NANBEI_NAV_FIELDS,
  五代十国: WUDAI_NAV_FIELDS,
  辽: LIAO_NAV_FIELDS,
  金: JIN_NAV_FIELDS,
}

function getContainerNavFields(containerId) {
  return CONTAINER_NAV_FIELDS[containerId] || null
}

const REGIME_CONTAINER_HIT_Z_INDEX = 4

/** 辽/金收起态：仅保留容器外壳，顶栏需展示朝代标签 */
function isCollapsedChannelContainerShell(containerId, expandedDynasties) {
  if (containerId === '辽') return !songLiaoJin.isLiaoEmperorsVisible(expandedDynasties)
  if (containerId === '金') return !songLiaoJin.isJinEmperorsVisible(expandedDynasties)
  return false
}

function resolveContainerShellHighlights(containerId, colorIdx) {
  const nav = getContainerNavFields(containerId)
  return buildHighlightTagList(getMatrixHighlights({
    id: nav && nav.entityId,
    legacyId: nav && nav.legacyId,
    dynastyName: containerId,
    displayName: containerId,
    isEmperor: false,
  }), {
    dynastyName: containerId,
    themeIndex: colorIdx != null ? colorIdx : 0,
  })
}

function pushCollapsedChannelContainerHit(containerHits, containerId, containerBlock, layout, civId) {
  const navFields = getContainerNavFields(containerId)
  if (!navFields || !containerBlock) return
  containerHits.push(Object.assign({}, navFields, {
    id: `container_hit_${containerId}`,
    containerId,
    top: containerBlock.top,
    h: containerBlock.h,
    leftPct: containerBlock.leftPct,
    widthPct: containerBlock.widthPct,
    zIndex: REGIME_CONTAINER_HIT_Z_INDEX,
    civ: civId,
    anchorYear: layout.start,
  }))
}

/** 金容器二级帝王卡几何（右半通道内单列） */
function calcJinChannelSubCardGeom() {
  const rightGeom = songLiaoJin.calcRightHalfGeom()
  const innerWidthPct = 100 - CONTAINER_INSET_PCT * 2
  return {
    leftPct: rightGeom.leftPct + rightGeom.widthPct * CONTAINER_INSET_PCT / 100,
    widthPct: rightGeom.widthPct * innerWidthPct / 100,
  }
}

/** 元成宗及以后：容器内单列，左右保留标准内边距 */
function calcYuanInnerSubCardGeom(containerBlock) {
  const innerWidthPct = 100 - CONTAINER_INSET_PCT * 2
  return toCanvasSubCardGeom(containerBlock, CONTAINER_INSET_PCT, innerWidthPct)
}

/** 清太宗：右半通道半宽，左缘对齐右通道（与崇祯等左半卡保留 BLOCK_H_GAP_PCT），右缘与顺治等全宽二级卡右缘对齐 */
function calcQingTaizongSubCardGeom(containerBlock) {
  const postGeom = calcQingPostEmperorSubCardGeom(containerBlock)
  const rightEdge = postGeom.leftPct + postGeom.widthPct
  const rightGeom = mingQing.calcRightHalfGeom()
  const scale = containerBlock.widthPct / 100
  const leftPct = containerBlock.leftPct + rightGeom.leftPct * scale
  const widthPct = Math.max(8, rightEdge - leftPct)
  return {
    leftPct,
    widthPct,
  }
}

/** 顺治及以后：容器内全宽留白 */
function calcQingPostEmperorSubCardGeom(containerBlock) {
  return calcYuanInnerSubCardGeom(containerBlock)
}

/**
 * 元世祖：左缘与金末帝对齐，右缘与元成宗等全宽二级卡对齐
 */
function calcYuanShizuSubCardGeom(containerBlock, expandedDynasties) {
  if (!songLiaoJin.isSongExpanded(expandedDynasties)) {
    return calcYuanInnerSubCardGeom(containerBlock)
  }
  const jinGeom = calcJinChannelSubCardGeom()
  const postGeom = calcYuanInnerSubCardGeom(containerBlock)
  const rightEdge = postGeom.leftPct + postGeom.widthPct
  return {
    leftPct: jinGeom.leftPct,
    widthPct: Math.max(8, rightEdge - jinGeom.leftPct),
  }
}

function applyYuanContainerBlockGeometry(blocks, expandedDynasties) {
  if (!isDynastyContainerActive('元', expandedDynasties)) return
  ;(blocks || []).forEach(b => {
    if (b.entryId === 'container_span_元' || (b.isDynastyContainer && b.containerId === '元')) {
      b.leftPct = 0
      b.widthPct = 100
      b.zIndex = 3
    }
  })
}

function applyQingContainerBlockGeometry(blocks, expandedDynasties) {
  if (!isDynastyContainerActive('清', expandedDynasties)) return
  ;(blocks || []).forEach(b => {
    if (b.entryId === 'container_span_清' || (b.isDynastyContainer && b.containerId === '清')) {
      b.leftPct = 0
      b.widthPct = 100
      b.zIndex = 2
    }
  })
}

/**
 * 宋展开态 sync 会重映射 907–1279 行高，可能压扁元容器时段。
 * 在 sync 之后补足元容器（1260–1368）最低高度，并下移后续朝代。
 */
function ensureYuanContainerTimelineAfterSongSync(rows, blocks, overlays, displayEntries, expandedDynasties) {
  if (!isDynastyContainerActive('元', expandedDynasties) || !rows || !rows.length) return

  const indices = []
  rows.forEach((r, i) => {
    if (r.tE <= YUAN_CONTAINER_START || r.tS >= YUAN_CONTAINER_END) return
    indices.push(i)
  })
  if (!indices.length) return

  const minH = calcYuanContainerMinTimelineHeight(displayEntries)
  const currentTotal = indices.reduce((sum, i) => sum + rows[i].h, 0)
  if (currentTotal >= minH) {
    songLiaoJin.repositionYuanContainerBlock(blocks, rows, expandedDynasties)
    return
  }

  const extra = minH - currentTotal
  const lastIdx = indices[indices.length - 1]
  const oldBoundaryY = rows[lastIdx].y + rows[lastIdx].h

  rows[lastIdx].h += extra
  for (let i = lastIdx + 1; i < rows.length; i++) {
    rows[i].y += extra
  }

  songLiaoJin.repositionYuanContainerBlock(blocks, rows, expandedDynasties)
  songLiaoJin.shiftPostSongZoneBlocks(blocks, extra, oldBoundaryY)
  songLiaoJin.shiftPostSongZoneOverlays(overlays, blocks, extra, oldBoundaryY)
}

function ensureQingContainerTimelineAfterMingSync(rows, blocks, overlays, displayEntries, expandedDynasties) {
  if (!isDynastyContainerActive('清', expandedDynasties) || !rows || !rows.length) return

  const indices = []
  rows.forEach((r, i) => {
    if (r.tE <= QING_CONTAINER_START || r.tS >= QING_CONTAINER_END) return
    indices.push(i)
  })
  if (!indices.length) return

  const minH = calcQingContainerMinTimelineHeight(displayEntries)
  const currentTotal = indices.reduce((sum, i) => sum + rows[i].h, 0)
  if (currentTotal >= minH) {
    mingQing.repositionQingContainerBlock(blocks, rows, expandedDynasties)
    return
  }

  const extra = minH - currentTotal
  const lastIdx = indices[indices.length - 1]
  const oldBoundaryY = rows[lastIdx].y + rows[lastIdx].h

  rows[lastIdx].h += extra
  for (let i = lastIdx + 1; i < rows.length; i++) {
    rows[i].y += extra
  }

  mingQing.repositionQingContainerBlock(blocks, rows, expandedDynasties)
  mingQing.shiftPostQingZoneBlocks(blocks, extra, oldBoundaryY)
  mingQing.shiftPostQingZoneOverlays(overlays, blocks, extra, oldBoundaryY)
}

function getContainerSubCardGap(containerId) {
  return (isFitToContainerId(containerId) || isYuanContainerId(containerId) || isQingContainerId(containerId))
    ? FIT_CONTAINER_SUB_CARD_GAP_RPX
    : SUB_CARD_GAP_RPX
}

function getContainerInnerPad(containerId) {
  return isFitToContainerId(containerId)
    ? FIT_CONTAINER_SUB_CARD_PAD_RPX
    : SUB_CARD_PAD_RPX
}

function calcEqualFitCardHeights(emperors, targetStackH, gapRpx = SUB_CARD_GAP_RPX, minCardH = 1) {
  const n = emperors.length
  if (!n || targetStackH <= 0) return []
  const gapTotal = Math.max(0, n - 1) * gapRpx
  const cardArea = Math.max(0, targetStackH - gapTotal)
  const floorMin = Math.max(1, minCardH)
  if (cardArea < n * floorMin) {
    return emperors.map(emp => ({ emp, h: floorMin }))
  }
  if (cardArea < n) {
    const h = Math.max(floorMin, Math.floor(targetStackH / n))
    return emperors.map(emp => ({ emp, h }))
  }
  const heights = emperors.map(() => Math.floor(cardArea / n))
  let used = heights.reduce((a, b) => a + b, 0)
  let i = 0
  while (used < cardArea && i < n * 50) {
    heights[i % n] += 1
    used += 1
    i += 1
  }
  while (used > cardArea) {
    const idx = heights.findIndex(x => x > floorMin)
    if (idx < 0) break
    heights[idx] -= 1
    used -= 1
  }
  return emperors.map((emp, idx) => ({ emp, h: Math.max(floorMin, heights[idx]) }))
}

function calcYuanContainerMinTimelineHeight(displayEntries) {
  const members = (displayEntries || [])
    .filter(e => e.containerId === '元' && e.isEmperor && e.start >= YUAN_CONTAINER_START)
  const postCount = Math.max(0, members.length - 1)
  if (!members.length) return 0
  const gap = FIT_CONTAINER_SUB_CARD_GAP_RPX
  const postStackMin = postCount > 0
    ? postCount * YUAN_EMPEROR_MIN_CARD_H_RPX + postCount * gap
    : 0
  const spanYears = YUAN_CONTAINER_END - YUAN_CONTAINER_START
  const shizuSpan = YUAN_SHIZU_REIGN_END - YUAN_CONTAINER_START
  const postSpan = spanYears - shizuSpan
  const minInnerFromShizu = YUAN_SHIZU_MIN_CARD_H_RPX * spanYears / shizuSpan
  const minInnerFromPost = postCount > 0
    ? postStackMin * spanYears / postSpan
    : 0
  const minInner = Math.max(minInnerFromShizu, minInnerFromPost)
  const headerReserve = containerDynastyHeaderReserve('元')
  return minInner + SUB_CARD_PAD_RPX * 2 + CONTAINER_BLOCK_GAP_RESERVE_RPX + headerReserve
}

/** 1294 后帝王堆叠：优先 16rpx 间距，空间不足时逐步缩小间距 */
function calcQingContainerMinTimelineHeight(displayEntries) {
  const members = (displayEntries || [])
    .filter(e => e.containerId === '清' && e.isEmperor && e.start >= QING_CONTAINER_START)
    .sort((a, b) => a.start - b.start)
  const postMembers = members.length > 2 ? members.slice(2) : []
  const postCount = postMembers.length
  if (!members.length) return 0
  const gap = FIT_CONTAINER_SUB_CARD_GAP_RPX
  const postStackMin = postCount > 0
    ? postCount * QING_EMPEROR_MIN_CARD_H_RPX + Math.max(0, postCount - 1) * gap
    : 0
  const spanYears = QING_CONTAINER_END - QING_CONTAINER_START
  const earlySpan = QING_EARLY_END - QING_CONTAINER_START
  const postSpan = spanYears - earlySpan
  const minInnerFromEarly = QING_TAIZONG_MIN_CARD_H_RPX + QING_EMPEROR_MIN_CARD_H_RPX + gap
  const minInnerFromEarlyTime = minInnerFromEarly * spanYears / earlySpan
  const minInnerFromPost = postCount > 0
    ? postStackMin * spanYears / postSpan
    : 0
  const minInner = Math.max(minInnerFromEarlyTime, minInnerFromPost)
  const headerReserve = containerDynastyHeaderReserve('清')
  return minInner + SUB_CARD_PAD_RPX * 2 + CONTAINER_BLOCK_GAP_RESERVE_RPX + headerReserve
}

function calcAdaptiveQingPostStack(postMembers, postRemaining, preferredGap, minCardH) {
  if (!postMembers.length || postRemaining <= 0) {
    return { gap: preferredGap, layouts: [] }
  }
  let gap = preferredGap
  while (gap >= SUB_CARD_GAP_RPX) {
    const cardStackH = postRemaining - gap
    if (cardStackH < postMembers.length * minCardH) {
      gap -= 1
      continue
    }
    const layouts = calcEqualFitCardHeights(postMembers, cardStackH, gap, minCardH)
    const totalH = gap + layouts.reduce((sum, item) => sum + item.h, 0)
      + Math.max(0, postMembers.length - 1) * gap
    if (totalH <= postRemaining + 1) {
      return { gap, layouts }
    }
    gap -= 1
  }
  const fallbackGap = SUB_CARD_GAP_RPX
  const cardStackH = Math.max(0, postRemaining - fallbackGap)
  return {
    gap: fallbackGap,
    layouts: calcEqualFitCardHeights(postMembers, cardStackH, fallbackGap, minCardH),
  }
}

function calcAdaptiveYuanPostStack(postMembers, postRemaining, preferredGap, minCardH) {
  if (!postMembers.length || postRemaining <= 0) {
    return { gap: preferredGap, layouts: [] }
  }
  let gap = preferredGap
  while (gap >= SUB_CARD_GAP_RPX) {
    const cardStackH = postRemaining - gap
    if (cardStackH < postMembers.length * minCardH) {
      gap -= 1
      continue
    }
    const layouts = calcEqualFitCardHeights(postMembers, cardStackH, gap, minCardH)
    const totalH = gap + layouts.reduce((sum, item) => sum + item.h, 0)
      + Math.max(0, postMembers.length - 1) * gap
    if (totalH <= postRemaining + 1) {
      return { gap, layouts }
    }
    gap -= 1
  }
  const fallbackGap = SUB_CARD_GAP_RPX
  const cardStackH = Math.max(0, postRemaining - fallbackGap)
  return {
    gap: fallbackGap,
    layouts: calcEqualFitCardHeights(postMembers, cardStackH, fallbackGap, minCardH),
  }
}

function calcContainerMinTimelineHeight(displayEntries, containerId) {
  if (containerId === '元') {
    return calcYuanContainerMinTimelineHeight(displayEntries)
  }
  if (containerId === '清') {
    return calcQingContainerMinTimelineHeight(displayEntries)
  }
  const layout = DYNASTY_CONTAINER_LAYOUTS[containerId]
  if (!layout) return 0
  if (layout.rows) {
    // 多行容器：每行内取最大列卡片数，多行叠加
    const cardH = containerId === '南北朝' ? SUB_CARD_H_NANBEI_RPX : SUB_CARD_H_RPX
    let totalH = 0
    layout.rows.forEach((row, ri) => {
      const counts = row.columns.map(col =>
        (displayEntries || []).filter(e =>
          e.containerId === containerId && e.containerColumn === col.key
        ).length
      )
      const maxCount = Math.max(0, ...counts)
      const rowH = cardH * maxCount + Math.max(0, maxCount - 1) * SUB_CARD_GAP_RPX
      totalH += rowH
      if (ri < layout.rows.length - 1) totalH += SUB_CARD_GAP_RPX
    })
    // 南北朝容器底部额外留白，让隋文帝卡片可以重叠在容器区域内
    const bottomPad = 0
    const headerReserve = containerDynastyHeaderReserve(containerId)
    return totalH + SUB_CARD_PAD_RPX * 2 + CONTAINER_BLOCK_GAP_RESERVE_RPX + bottomPad + headerReserve
  }
  const counts = layout.columns.map(col =>
    (displayEntries || []).filter(e =>
      e.containerId === containerId && e.containerColumn === col.key
    ).length
  )
  const maxCount = Math.max(0, ...counts)
  const headerReserve = containerDynastyHeaderReserve(containerId)
  return calcUniformColumnStackHeight(maxCount)
    + SUB_CARD_PAD_RPX * 2
    + CONTAINER_BLOCK_GAP_RESERVE_RPX
    + headerReserve
}

/**
 * 容器时段行高不足时，等比放大该时段各切片高度（仍与时间轴年界对齐）
 */
function applyContainerTimelineHeightBoost(mergedSlices, expandedDynasties, displayEntries, calcSliceH) {
  if (!mergedSlices || !mergedSlices.length) return

  Object.keys(DYNASTY_CONTAINER_LAYOUTS).forEach(containerId => {
    if (!isDynastyContainerActive(containerId, expandedDynasties)) return
    const layout = DYNASTY_CONTAINER_LAYOUTS[containerId]
    const timelineEnd = getContainerTimelineEnd(layout)
    const minTotalH = calcContainerMinTimelineHeight(displayEntries, containerId)
    if (minTotalH <= 0) return

    const indices = []
    let currentTotal = 0
    mergedSlices.forEach((sl, i) => {
      if (sl.tE <= layout.start || sl.tS >= timelineEnd) return
      indices.push(i)
      currentTotal += calcSliceH(sl.tS, sl.tE, sl.active)
    })
    if (!indices.length || currentTotal >= minTotalH) return

    const scale = minTotalH / currentTotal
    indices.forEach(i => {
      mergedSlices[i]._containerHeightScale = scale
    })
  })
}

function findContainerBlock(blocks, containerId) {
  const entryId = `container_span_${containerId}`
  const segs = (blocks || [])
    .filter(b => b.entryId === entryId || b.containerId === containerId)
    .sort((a, b) => a.top - b.top)
  if (!segs.length) return null
  const top = segs[0].top
  const bottom = Math.max(...segs.map(s => s.top + s.h))
  return {
    entryId,
    top,
    h: bottom - top,
    leftPct: segs[0].leftPct,
    widthPct: segs[0].widthPct,
    segs,
  }
}

function calcColumnGeometry(numCols, insetPct, gapPct) {
  const n = Math.max(1, numCols)
  const gaps = (n - 1) * gapPct
  const usable = 100 - insetPct * 2 - gaps
  const widthPct = usable / n
  let left = insetPct
  return Array.from({ length: n }, (_, i) => {
    const geom = { leftPct: left, widthPct, colIndex: i, numCols: n }
    left += widthPct + (i < n - 1 ? gapPct : 0)
    return geom
  })
}

function buildYuanContainerEmperors(ctx) {
  const {
    containerBlock,
    containerId,
    displayEntries,
    civId,
    expandedDynasties,
    entryToCardFields,
    fitCardTimeFontSize,
    inferLabelLayout,
    innerTop,
    innerBottom,
    HEADER_TOP_INSET,
    subCardBg,
    subCards,
    subOverlays,
  } = ctx

  const members = (displayEntries || [])
    .filter(e => e.containerId === containerId && e.isEmperor && e.start >= YUAN_CONTAINER_START)
    .sort((a, b) => a.start - b.start)
  if (!members.length) return

  const shizuGeom = calcYuanShizuSubCardGeom(containerBlock, expandedDynasties)
  const postGeom = calcYuanInnerSubCardGeom(containerBlock)
  const innerH = Math.max(0, innerBottom - innerTop)
  const preferredGap = getContainerSubCardGap(containerId)
  const spanYears = YUAN_CONTAINER_END - YUAN_CONTAINER_START
  const shizuSpan = YUAN_SHIZU_REIGN_END - YUAN_CONTAINER_START

  const shizu = members.find(e => e.displayName === '元世祖' || e.name === '元世祖')
    || members[0]
  const postMembers = members.filter(e => e.id !== shizu.id)

  // 元世祖区按 1260–1294 时间比例占高，底缘对齐 1294，不参与压缩
  const shizuH = Math.max(
    YUAN_SHIZU_MIN_CARD_H_RPX,
    Math.floor(innerH * shizuSpan / spanYears)
  )

  const postRemaining = Math.max(0, innerH - shizuH)
  const { gap: postGap, layouts } = calcAdaptiveYuanPostStack(
    postMembers,
    postRemaining,
    preferredGap,
    YUAN_EMPEROR_MIN_CARD_H_RPX
  )

  const pushEmperorCard = (emp, top, h, colIdx, geom) => {
    if (h <= 0) return
    const fields = entryToCardFields(emp, civId)
    const cardId = `${emp.id}_sub_${colIdx}`
    const headerInset = h < YUAN_EMPEROR_MIN_CARD_H_RPX ? 8 : HEADER_TOP_INSET
    const cardHeaderTop = top + headerInset
    const isCompact = h < YUAN_EMPEROR_MIN_CARD_H_RPX

    subCards.push(Object.assign({}, fields, YUAN_NAV_FIELDS, {
      id: cardId,
      entryId: emp.id,
      legacyId: emp.legacyId || '',
      isContainerSubCard: true,
      containerId,
      top,
      h,
      leftPct: geom.leftPct,
      widthPct: geom.widthPct,
      subCardBg,
      subCardStroke: SUB_CARD_STROKE,
      radiusRpx: 12,
      cardBg: subCardBg,
      zIndex: YUAN_SUB_CARD_Z_INDEX,
      anchorYear: emp.start,
    }))

    subOverlays.push({
      id: `${cardId}_chrome`,
      entryId: emp.id,
      kind: fields.kind,
      person: fields.person,
      displayName: fields.displayName,
      dynasty: fields.dynasty,
      timeRange: fields.timeRange,
      highlights: fields.highlights || [],
      hideLabels: false,
      hideTags: false,
      hideTime: !!fields.hideTime,
      labelLayout: inferLabelLayout(geom.widthPct),
      headerTop: cardHeaderTop,
      headerLeftPct: geom.leftPct,
      headerWidthPct: geom.widthPct,
      headerHeight: Math.max(0, h - headerInset * 2),
      timeFontRpx: fitCardTimeFontSize(fields.timeRange, geom.widthPct),
      zIndex: YUAN_SUB_OVERLAY_Z_INDEX,
      isRegimeCard: false,
      isContainerRegimeLabel: false,
      isContainerEmperorCard: true,
      isContainerEmperorInline: true,
      isContainerEmperorCompact: isCompact,
    })
  }

  pushEmperorCard(
    shizu,
    innerTop,
    shizuH,
    0,
    shizuGeom
  )

  if (!postMembers.length) return

  let cardTop = innerTop + shizuH + postGap
  layouts.forEach(({ emp, h: cardH }, idx) => {
    const h = Math.max(YUAN_EMPEROR_MIN_CARD_H_RPX, cardH)
    pushEmperorCard(emp, cardTop, h, idx + 1, postGeom)
    cardTop += h + postGap
  })
}

function buildQingContainerEmperors(ctx) {
  const {
    containerBlock,
    containerId,
    displayEntries,
    civId,
    entryToCardFields,
    fitCardTimeFontSize,
    inferLabelLayout,
    innerTop,
    innerBottom,
    HEADER_TOP_INSET,
    subCardBg,
    subCards,
    subOverlays,
  } = ctx

  const members = (displayEntries || [])
    .filter(e => e.containerId === containerId && e.isEmperor && e.start >= QING_CONTAINER_START)
    .sort((a, b) => a.start - b.start)
  if (!members.length) return

  const taizongGeom = calcQingTaizongSubCardGeom(containerBlock)
  const postGeom = calcQingPostEmperorSubCardGeom(containerBlock)
  const innerH = Math.max(0, innerBottom - innerTop)
  const preferredGap = getContainerSubCardGap(containerId)
  const stackLimit = innerBottom

  const taizong = members.find(e => e.displayName === '清太宗' || e.name === '清太宗')
    || members[0]
  const shunzhi = members.find(e => e.displayName === '顺治' || e.name === '顺治')
  const postMembers = members.filter(e => e.id !== taizong.id && e.id !== (shunzhi && shunzhi.id))

  const ordered = [taizong]
  if (shunzhi) ordered.push(shunzhi)
  ordered.push(...postMembers)

  const minForEmp = (emp) => emp.id === taizong.id
    ? QING_TAIZONG_MIN_CARD_H_RPX
    : QING_EMPEROR_MIN_CARD_H_RPX

  const layouts = calcQingStackCardHeights(ordered, innerH, preferredGap, minForEmp)

  const pushEmperorCard = (emp, top, h, colIdx, geom) => {
    if (!emp || h <= 0) return
    const fields = entryToCardFields(emp, civId)
    const cardId = `${emp.id}_sub_${colIdx}`
    const headerInset = h < QING_EMPEROR_MIN_CARD_H_RPX ? 8 : HEADER_TOP_INSET
    const cardHeaderTop = top + headerInset
    const isCompact = h < QING_EMPEROR_MIN_CARD_H_RPX

    subCards.push(Object.assign({}, fields, QING_NAV_FIELDS, {
      id: cardId,
      entryId: emp.id,
      legacyId: emp.legacyId || '',
      isContainerSubCard: true,
      containerId,
      top,
      h,
      leftPct: geom.leftPct,
      widthPct: geom.widthPct,
      subCardBg,
      subCardStroke: SUB_CARD_STROKE,
      radiusRpx: 12,
      cardBg: subCardBg,
      zIndex: QING_SUB_CARD_Z_INDEX,
      anchorYear: emp.start,
    }))

    subOverlays.push({
      id: `${cardId}_chrome`,
      entryId: emp.id,
      kind: fields.kind,
      person: fields.person,
      displayName: fields.displayName,
      dynasty: fields.dynasty,
      timeRange: fields.timeRange,
      highlights: fields.highlights || [],
      hideLabels: false,
      hideTags: false,
      hideTime: !!fields.hideTime,
      labelLayout: inferLabelLayout(geom.widthPct),
      headerTop: cardHeaderTop,
      headerLeftPct: geom.leftPct,
      headerWidthPct: geom.widthPct,
      headerHeight: Math.max(0, h - headerInset * 2),
      timeFontRpx: fitCardTimeFontSize(fields.timeRange, geom.widthPct),
      zIndex: QING_SUB_OVERLAY_Z_INDEX,
      isRegimeCard: false,
      isContainerRegimeLabel: false,
      isContainerEmperorCard: true,
      isContainerEmperorInline: true,
      isContainerEmperorCompact: isCompact,
    })
  }

  let cardTop = innerTop
  layouts.forEach(({ emp, h: cardH }, idx) => {
    if (cardTop >= stackLimit) return
    let h = cardH
    if (cardTop + h > stackLimit) {
      h = Math.max(1, stackLimit - cardTop)
    }
    if (h <= 0) return
    const geom = emp.id === taizong.id ? taizongGeom : postGeom
    pushEmperorCard(emp, cardTop, h, idx, geom)
    cardTop += h + preferredGap
  })
}

function buildDynastyContainerVisuals(ctx) {
  const {
    blocks,
    displayEntries,
    expandedDynasties,
    civId,
    entryToCardFields,
    fitCardTimeFontSize,
    inferLabelLayout,
    fmtRange,
    HEADER_TOP_INSET,
  } = ctx

  const subCards = []
  const subOverlays = []
  const containerHits = []

  Object.keys(DYNASTY_CONTAINER_LAYOUTS).forEach(containerId => {
    const layout = DYNASTY_CONTAINER_LAYOUTS[containerId]
    if (!isDynastyContainerActive(containerId, expandedDynasties)) return
    const isChunqiu = containerId === '春秋'
    const isZhanguo = containerId === '战国'
    const isNanbei = containerId === '南北朝'
    const isWudai = containerId === '五代十国'
    const subCardBg = isChunqiu ? SUB_CARD_BG_A : isZhanguo ? SUB_CARD_BG_B : SUB_CARD_BG_NEUTRAL
    const rowCardH = (isNanbei || isWudai) ? SUB_CARD_H_NANBEI_RPX : SUB_CARD_H_RPX
    const showDynastyHeader = usesContainerDynastyHeader(containerId)
    const dynastyHeaderReserve = containerDynastyHeaderReserve(containerId)

    const containerBlock = findContainerBlock(blocks, containerId)
    if (!containerBlock) return

    if (showDynastyHeader && typeof fmtRange === 'function') {
      const timeRange = resolveContainerHeaderTimeRange(
        containerId, layout, displayEntries, fmtRange
      )
      const yuanHeaderGeom = containerId === '元'
        ? calcYuanShizuSubCardGeom(containerBlock, expandedDynasties)
        : null
      const qingHeaderGeom = containerId === '清'
        ? calcQingTaizongSubCardGeom(containerBlock)
        : null
      const headerWidthPct = qingHeaderGeom
        ? qingHeaderGeom.widthPct
        : yuanHeaderGeom
          ? yuanHeaderGeom.widthPct
          : containerBlock.widthPct
      const headerLeftPct = qingHeaderGeom
        ? qingHeaderGeom.leftPct
        : yuanHeaderGeom
          ? yuanHeaderGeom.leftPct
          : containerBlock.leftPct
      const collapsedShell = isCollapsedChannelContainerShell(containerId, expandedDynasties)
      const shellColorIdx = containerBlock.colorIdx != null ? containerBlock.colorIdx : 0
      const shellHighlights = collapsedShell
        ? resolveContainerShellHighlights(containerId, shellColorIdx)
        : []
      subOverlays.push({
        id: `container_header_${containerId}`,
        kind: 'dynasty',
        displayName: containerId,
        timeRange,
        hideLabels: false,
        hideTags: !collapsedShell,
        hideTime: false,
        highlights: shellHighlights,
        containerTagPlacement: collapsedShell ? 'below-name' : 'none',
        labelLayout: collapsedShell
          ? 'stacked'
          : (typeof inferLabelLayout === 'function'
            ? inferLabelLayout(headerWidthPct)
            : 'wide'),
        headerTop: containerBlock.top + HEADER_TOP_INSET,
        headerLeftPct,
        headerWidthPct,
        isContainerDynastyHeader: true,
        isCollapsedDynastyCard: collapsedShell,
        isContainerDynastyHeaderYuan: containerId === '元' || containerId === '清',
        isContainerDynastyHeaderRight: false,
        timeFontRpx: fitCardTimeFontSize(timeRange, headerWidthPct),
        zIndex: 26,
        containerId,
        ...(getContainerNavFields(containerId) || {}),
      })
    }

    // 辽/金/元：对应通道未展开时仅保留容器色块，不展示帝王二级卡
    if (containerId === '辽' && !songLiaoJin.isLiaoEmperorsVisible(expandedDynasties)) {
      pushCollapsedChannelContainerHit(containerHits, containerId, containerBlock, layout, civId)
      return
    }
    if (containerId === '金' && !songLiaoJin.isJinEmperorsVisible(expandedDynasties)) {
      pushCollapsedChannelContainerHit(containerHits, containerId, containerBlock, layout, civId)
      return
    }
    if (containerId === '元' && !songLiaoJin.isYuanEmperorsVisible(expandedDynasties)) return
    if (containerId === '清' && !mingQing.isQingEmperorsVisible(expandedDynasties)) return

    const innerPad = getContainerInnerPad(containerId)
    const innerTop = containerBlock.top + innerPad + dynastyHeaderReserve

    let innerBottom = containerBlock.top + containerBlock.h - innerPad
  // 辽帝王卡不侵入金容器：在金容器上缘处截断
    if (containerId === '辽' && songLiaoJin.isJinContainerActive(expandedDynasties)) {
      const jinBlock = findContainerBlock(blocks, '金')
      if (jinBlock) {
        innerBottom = Math.min(innerBottom, jinBlock.top - getContainerSubCardGap('辽'))
      }
    }

    const fitGap = getContainerSubCardGap(containerId)

    if (layout.rows) {
      // 多行容器（南北朝专用）
      const cardH = rowCardH
      let rowTop = innerTop
      layout.rows.forEach((row, ri) => {
        const colGeoms = calcColumnGeometry(
          row.columns.length,
          CONTAINER_INSET_PCT,
          CONTAINER_COL_GAP_PCT
        )
        const columnPlans = row.columns.map((col, colIdx) => {
          const members = (displayEntries || [])
            .filter(e => e.containerId === containerId && e.containerColumn === col.key)
            .sort((a, b) => a.start - b.start)
          return { colIdx, geom: colGeoms[colIdx], members }
        })
        const maxCount = Math.max(0, ...columnPlans.map(p => p.members.length))
        if (!maxCount) return
        const targetStackH = cardH * maxCount + Math.max(0, maxCount - 1) * SUB_CARD_GAP_RPX

        columnPlans.forEach(plan => {
          const { geom, members, colIdx } = plan
          if (!members.length) return
          const isDenseColumn = members.length === maxCount
          const cardLayouts = calcColumnCardHeights(members, targetStackH, isDenseColumn)
          let cardTop = rowTop
          cardLayouts.forEach(({ emp, h: empH }) => {
            const fields = entryToCardFields(emp, civId)
            const top = cardTop
            const cardId = `${emp.id}_sub_${containerId}_r${ri}_c${colIdx}`
            const isRegimeCard = !!emp.isRegimeOnly
            const isContainerRegimeLabel = showDynastyHeader &&
              isContainerSubRegimeLabel(containerId, emp, fields)
            const actualH = (isNanbei || isWudai) ? Math.min(empH, cardH) : empH
            const canvasGeom = toCanvasSubCardGeom(containerBlock, geom.leftPct, geom.widthPct)

            subCards.push(Object.assign({}, fields, {
              id: cardId,
              entryId: emp.id,
              legacyId: emp.legacyId || '',
              isContainerSubCard: true,
              containerId,
              top,
              h: actualH,
              leftPct: canvasGeom.leftPct,
              widthPct: canvasGeom.widthPct,
              subCardBg,
              subCardStroke: SUB_CARD_STROKE,
              radiusRpx: 12,
              cardBg: subCardBg,
              zIndex: 8,
              entityType: 'regime',
              entityId: emp.regimeId || emp.id,
              regimeId: emp.regimeId || emp.id,
              dynastyId: emp.dynastyId || (getContainerNavFields(containerId) || {}).dynastyId || '',
            }))

            const timeFontRpx = fitCardTimeFontSize(fields.timeRange, canvasGeom.widthPct)
            const isWudaiFiveRegimeVertical = isWudai &&
              WUDAI_FIVE_REGIME_KEYS.has(emp.containerColumn)
            subOverlays.push({
              id: `${cardId}_chrome`,
              entryId: emp.id,
              kind: fields.kind,
              person: fields.person,
              displayName: fields.displayName,
              dynasty: fields.dynasty,
              timeRange: fields.timeRange,
              highlights: fields.highlights || [],
              hideLabels: false,
              hideTags: false,
              hideTime: !!fields.hideTime || !!emp.isRegimeOnly,
              labelLayout: inferLabelLayout(canvasGeom.widthPct),
              headerTop: top,
              headerLeftPct: canvasGeom.leftPct,
              headerWidthPct: canvasGeom.widthPct,
              headerHeight: actualH,
              timeFontRpx,
              zIndex: 25,
              isRegimeCard,
              isContainerRegimeLabel,
              isWudaiFiveRegimeVertical,
            })

            cardTop += actualH + SUB_CARD_GAP_RPX
          })
        })
        rowTop += calcUniformColumnStackHeight(maxCount) + SUB_CARD_GAP_RPX
      })
      const navFields = getContainerNavFields(containerId)
      if (navFields) {
        containerHits.push(Object.assign({}, navFields, {
          id: `container_hit_${containerId}`,
          containerId,
          top: containerBlock.top,
          h: containerBlock.h,
          leftPct: containerBlock.leftPct,
          widthPct: containerBlock.widthPct,
          zIndex: REGIME_CONTAINER_HIT_Z_INDEX,
          civ: civId,
          anchorYear: layout.start,
        }))
      }
      return
    }

    if (isYuanContainerId(containerId)) {
      buildYuanContainerEmperors({
        containerBlock,
        containerId,
        displayEntries,
        civId,
        expandedDynasties,
        entryToCardFields,
        fitCardTimeFontSize,
        inferLabelLayout,
        innerTop,
        innerBottom,
        HEADER_TOP_INSET,
        subCardBg: SUB_CARD_BG_NEUTRAL,
        subCards,
        subOverlays,
      })
      containerHits.push(Object.assign({}, YUAN_NAV_FIELDS, {
        id: `container_hit_${containerId}`,
        containerId,
        top: containerBlock.top,
        h: containerBlock.h,
        leftPct: containerBlock.leftPct,
        widthPct: containerBlock.widthPct,
        zIndex: YUAN_CONTAINER_HIT_Z_INDEX,
        civ: civId,
        anchorYear: YUAN_CONTAINER_START,
      }))
      return
    }

    if (isQingContainerId(containerId)) {
      buildQingContainerEmperors({
        containerBlock,
        containerId,
        displayEntries,
        civId,
        entryToCardFields,
        fitCardTimeFontSize,
        inferLabelLayout,
        innerTop,
        innerBottom,
        HEADER_TOP_INSET,
        subCardBg: SUB_CARD_BG_NEUTRAL,
        subCards,
        subOverlays,
      })
      containerHits.push(Object.assign({}, QING_NAV_FIELDS, {
        id: `container_hit_${containerId}`,
        containerId,
        top: containerBlock.top,
        h: containerBlock.h,
        leftPct: containerBlock.leftPct,
        widthPct: containerBlock.widthPct,
        zIndex: QING_CONTAINER_HIT_Z_INDEX,
        civ: civId,
        anchorYear: QING_CONTAINER_START,
      }))
      return
    }

    // 单行容器（三国/春秋/战国 原有逻辑）
    const colGeoms = calcColumnGeometry(
      layout.columns.length,
      CONTAINER_INSET_PCT,
      CONTAINER_COL_GAP_PCT
    )

    const columnPlans = layout.columns.map((col, colIdx) => {
      const members = (displayEntries || [])
        .filter(e => e.containerId === containerId && e.containerColumn === col.key)
        .sort((a, b) => a.start - b.start)
      return { colIdx, geom: colGeoms[colIdx], members }
    })

    const maxCount = Math.max(0, ...columnPlans.map(p => p.members.length))
    if (!maxCount) return

    const availableStackH = Math.max(0, innerBottom - innerTop)
    const fitToContainer = isFitToContainerId(containerId)
    const targetStackH = fitToContainer
      ? Math.floor(availableStackH * FIT_CONTAINER_STACK_FILL_RATIO)
      : calcUniformColumnStackHeight(maxCount)

    columnPlans.forEach(plan => {
      const { geom, members, colIdx } = plan
      if (!members.length) return

      const isDenseColumn = !fitToContainer && members.length === maxCount
      const cardLayouts = fitToContainer
        ? calcEqualFitCardHeights(members, targetStackH, fitGap)
        : calcColumnCardHeights(members, targetStackH, isDenseColumn)
      let cardTop = innerTop
      const stackLimit = innerBottom

      cardLayouts.forEach(({ emp, h: cardH }) => {
        if (cardTop >= stackLimit) return
        let h = cardH
        if (cardTop + h > stackLimit) {
          h = Math.max(1, stackLimit - cardTop)
        }
        if (h <= 0) return
        const fields = entryToCardFields(emp, civId)
        const top = cardTop
        const cardId = `${emp.id}_sub_${colIdx}`
        const isRegimeCard = !!emp.isRegimeOnly
        const isContainerRegimeLabel = showDynastyHeader &&
          isContainerSubRegimeLabel(containerId, emp, fields)
        const useStackedLayout = containerId === '三国'
        const useInlineEmperorLayout = isFitToContainerId(containerId)
        const isCompactEmperorCard = useInlineEmperorLayout && !emp.isRegimeOnly && h < 64
        const headerInset = isCompactEmperorCard ? FIT_COMPACT_HEADER_INSET_RPX : HEADER_TOP_INSET
        const cardHeaderTop = isRegimeCard
          ? top
          : ((useStackedLayout || useInlineEmperorLayout) ? top + headerInset : top)
        const canvasGeom = toCanvasSubCardGeom(containerBlock, geom.leftPct, geom.widthPct)

        subCards.push(Object.assign({}, fields, {
          id: cardId,
          entryId: emp.id,
          legacyId: emp.legacyId || '',
          isContainerSubCard: true,
          containerId,
          top,
          h,
          leftPct: canvasGeom.leftPct,
          widthPct: canvasGeom.widthPct,
          subCardBg,
          subCardStroke: SUB_CARD_STROKE,
          radiusRpx: 12,
          cardBg: subCardBg,
          zIndex: 8,
          entityType: emp.isRegimeOnly ? 'regime' : 'emperor',
          entityId: emp.regimeId || emp.id,
          regimeId: emp.regimeId || emp.id,
          dynastyId: emp.dynastyId || (getContainerNavFields(containerId) || {}).dynastyId || '',
        }))

        const timeFontRpx = isCompactEmperorCard
          ? Math.min(12, fitCardTimeFontSize(fields.timeRange, canvasGeom.widthPct))
          : fitCardTimeFontSize(fields.timeRange, canvasGeom.widthPct)
        const isContainerEmperorCard = (useStackedLayout || useInlineEmperorLayout) && !emp.isRegimeOnly
        const labelLayout = useStackedLayout
          ? 'stacked'
          : inferLabelLayout(canvasGeom.widthPct)
        subOverlays.push({
          id: `${cardId}_chrome`,
          entryId: emp.id,
          kind: fields.kind,
          person: fields.person,
          displayName: fields.displayName,
          dynasty: fields.dynasty,
          timeRange: fields.timeRange,
          highlights: fields.highlights || [],
          hideLabels: false,
          hideTags: false,
          hideTime: !!fields.hideTime || !!emp.isRegimeOnly,
          labelLayout,
          headerTop: cardHeaderTop,
          headerLeftPct: canvasGeom.leftPct,
          headerWidthPct: canvasGeom.widthPct,
          headerHeight: isContainerRegimeLabel
            ? h
            : ((useStackedLayout || useInlineEmperorLayout)
              ? Math.max(0, h - headerInset * 2)
              : h),
          timeFontRpx,
          zIndex: 25,
          isRegimeCard,
          isContainerRegimeLabel,
          isContainerEmperorCard,
          isContainerEmperorInline: useInlineEmperorLayout && !emp.isRegimeOnly,
          isContainerEmperorCompact: isCompactEmperorCard,
        })

        cardTop += h + getContainerSubCardGap(containerId)
      })
    })

    const navFields = getContainerNavFields(containerId)
    if (navFields && !isYuanContainerId(containerId) && !isQingContainerId(containerId)) {
      containerHits.push(Object.assign({}, navFields, {
        id: `container_hit_${containerId}`,
        containerId,
        top: containerBlock.top,
        h: containerBlock.h,
        leftPct: containerBlock.leftPct,
        widthPct: containerBlock.widthPct,
        zIndex: REGIME_CONTAINER_HIT_Z_INDEX,
        civ: civId,
        anchorYear: layout.start,
      }))
    }
  })

  return { subCards, subOverlays, containerHits }
}

function applyDynastyContainerBlockStyles(blocks) {
  ;(blocks || []).forEach(b => {
    if (!b.isDynastyContainer) return
    b.radiusStyle = `${CONTAINER_RADIUS_RPX}rpx`
    b.edgeClass = (b.edgeClass || '') + ' era-block--dynasty-container'
    // 容器底色须在二级卡之下（二级卡 z-index 8）
    b.zIndex = 3
  })
}

module.exports = {
  DYNASTY_CONTAINER_LAYOUTS,
  REGIME_TO_DYNASTY_KEY,
  SUB_CARD_BG_A,
  SUB_CARD_BG_B,
  SUB_CARD_BG_NEUTRAL,
  CONTAINER_RADIUS_RPX,
  SUB_CARD_H_RPX,
  SUB_CARD_PAD_RPX,
  CONTAINER_BLOCK_GAP_RESERVE_RPX,
  buildHuaxiaDynastyColorMap,
  resolveHuaxiaDynastyKey,
  assignHuaxiaDynastyColorIndices,
  getHuaxiaDynastyColorIdx,
  isDynastyContainerActive,
  isRegimeContainerExpanded,
  REGIME_CONTAINER_IDS,
  filterEntriesForTimeSlices,
  calcContainerMinTimelineHeight,
  applyContainerTimelineHeightBoost,
  buildDynastyContainerVisuals,
  applyDynastyContainerBlockStyles,
  applyYuanContainerBlockGeometry,
  applyQingContainerBlockGeometry,
  ensureYuanContainerTimelineAfterSongSync,
  ensureQingContainerTimelineAfterMingSync,
  getContainerTimelineEnd,
  getContainerNavFields,
}
