/**
 * 明清双通道布局 — 镜像 song-liao-jin-layout 宋辽金元逻辑
 * 左半：明帝王堆叠（展开态）/ 明朝代卡（收起态）
 * 全宽：清一级容器（明展开态，z-index 低于明帝王块）
 */

const BLOCK_H_GAP_PCT = 3.2
const BLOCK_V_GAP_RPX = 16
const BLOCK_MIN_SEG_H = 20
const COLLAPSED_DYNASTY_CARD_H_RPX = 200
const BLOCK_RADIUS_RPX = 12
const EMP_CARD_H_MIN_RPX = 80
const EMP_CARD_H_MAX_RPX = 200
const EMP_CARD_REF_YEARS = 71

const MING_START = 1368
const MING_QING_COEXIST_START = 1616
const MING_QING_COEXIST_END = 1662

const QING_CONTAINER_START = 1626
const QING_CONTAINER_END = 1912
const MING_ZONE_END = QING_CONTAINER_END

const QING_ENTRY = 'ZQ_HX_QING_QING'
const MING_ENTRY = 'ZQ_HX_MING_MING'
const YUAN_CONTAINER = 'container_span_元'
const MING_AXIS_KEY = '明'
/** 时间轴上可点击收展的联动轴标（明/清同控明清区域） */
const MING_LINKED_AXIS_KEYS = ['明', '清']

function isMingLinkedAxisKey(dynKey) {
  return MING_LINKED_AXIS_KEYS.indexOf(dynKey) >= 0
}

/** 明/清轴标联动：展开/收起同一套明清区域 */
function applyMingLinkedExpansion(next, willExpand) {
  if (willExpand) {
    next[MING_AXIS_KEY] = true
    next['清'] = true
  } else {
    delete next[MING_AXIS_KEY]
    delete next['清']
  }
  return next
}
const QING_CONTAINER = 'container_span_清'
const CHONGZHEN_ENTRY = 'DW_HX_MING_MING_CHONGZHEN'

const Z_MID = 5

const { parseHistoryYearSpan } = require('../year-format')

function calcHalfWidthPct() {
  return (100 - BLOCK_H_GAP_PCT) / 2
}

function calcLeftHalfGeom() {
  const w = calcHalfWidthPct()
  return { leftPct: 0, widthPct: w, colIndex: 0, numCols: 2 }
}

function calcRightHalfGeom() {
  const w = calcHalfWidthPct()
  return { leftPct: w + BLOCK_H_GAP_PCT, widthPct: w, colIndex: 1, numCols: 2 }
}

function calcFullWidthGeom() {
  return { leftPct: 0, widthPct: 100 }
}

function isMingExpanded(expandedDynasties) {
  if (!expandedDynasties) return false
  return MING_LINKED_AXIS_KEYS.some(k => !!expandedDynasties[k])
}

function isQingExpanded(expandedDynasties) {
  return isMingExpanded(expandedDynasties)
}

function isQingContainerActive(expandedDynasties) {
  return isMingExpanded(expandedDynasties)
}

function isQingEmperorsVisible(expandedDynasties) {
  return isQingContainerActive(expandedDynasties)
}

function isQingContainerSpanEntry(entry) {
  if (!entry) return false
  return (entry.isContainerSpan || entry.isDynastyContainer) && entry.containerId === '清'
}

function isMingSequenceEntry(entry) {
  if (!entry) return false
  return entry.dynastyName === '明' || entry.dynastyGroup === '明'
}

function isQingSequenceEntry(entry) {
  if (!entry) return false
  return entry.dynastyName === '清' || entry.dynastyGroup === '清'
}

function isBridgeBlock(b) {
  return !!(b && (b.isLBridge || b.isNanbeiLBridge || b.isBridgeBlock))
}

function findRowForYear(rows, year) {
  const exactStart = (rows || []).find(r => r.tS === year)
  if (exactStart) return { row: exactStart, ratio: 0 }
  const exactEnd = (rows || []).find(r => r.tE === year)
  if (exactEnd) return { row: exactEnd, ratio: 1 }
  const containing = (rows || []).find(r => r.tS < year && r.tE > year)
  if (!containing) return null
  const span = containing.tE - containing.tS
  const ratio = span > 0 ? (year - containing.tS) / span : 0
  return { row: containing, ratio }
}

function yearY(rows, year) {
  const hit = findRowForYear(rows, year)
  if (!hit) return null
  const { row, ratio } = hit
  return row.y + Math.round(row.h * Math.max(0, Math.min(1, ratio)))
}

function yearTop(rows, year) {
  return yearY(rows, year)
}

function yearBlockSpan(rows, startYear, endYear) {
  const top = yearTop(rows, startYear)
  const endY = yearY(rows, endYear)
  if (top == null || endY == null) return null
  const bottom = Math.max(top + BLOCK_MIN_SEG_H, endY)
  return { top, h: Math.max(BLOCK_MIN_SEG_H, bottom - top) }
}

function parseBlockYearSpan(block) {
  const span = parseHistoryYearSpan(String(block.timeRange || ''))
  if (span) return span
  const y = block.anchorYear || 0
  return { start: y, end: y }
}

function calcEmperorCardHeight(years) {
  const y = Math.max(1, Math.min(Number(years) || 1, EMP_CARD_REF_YEARS))
  const span = EMP_CARD_H_MAX_RPX - EMP_CARD_H_MIN_RPX
  return Math.max(
    EMP_CARD_H_MIN_RPX,
    Math.min(EMP_CARD_H_MAX_RPX, Math.round(EMP_CARD_H_MIN_RPX + (y / EMP_CARD_REF_YEARS) * span))
  )
}

function fullRadiusStyle() {
  const R = BLOCK_RADIUS_RPX
  return `${R}rpx ${R}rpx ${R}rpx ${R}rpx`
}

function isMingZoneBlock(b) {
  if (!b || isBridgeBlock(b)) return false
  if (b.dynasty === '明' || b.dynasty === '清') return true
  const id = b.entryId || ''
  return id === MING_ENTRY || id === QING_ENTRY || id === QING_CONTAINER
}

function findBlockBase(blocks, entryId) {
  return (blocks || []).find(b => b.entryId === entryId && !isBridgeBlock(b))
}

function makeMingRect(base, geom, top, h, zIndex) {
  return Object.assign({}, base, {
    id: `${base.entryId}_ming_rect`,
    top,
    h: Math.max(BLOCK_MIN_SEG_H, h),
    leftPct: geom.leftPct,
    widthPct: geom.widthPct,
    zIndex: zIndex != null ? zIndex : Z_MID,
    rTL: true, rTR: true, rBR: true, rBL: true,
    radiusStyle: fullRadiusStyle(),
    edgeClass: '',
    edgeTop: false, edgeRight: false, edgeBottom: false, edgeLeft: false,
    fillSeamFix: false,
    isLBridge: false, isNanbeiLBridge: false,
  })
}

function isChongzhenMingBlock(base) {
  if (!base) return false
  if (base.person === '崇祯') return true
  if (base.entryId === CHONGZHEN_ENTRY) return true
  return String(base.entryId || '').includes('CHONGZHEN')
}

/** 明太祖—明熹宗全宽，仅崇祯左半宽 */
function stackMingEmperors(sourceBlocks, startTop, gap) {
  const emps = (sourceBlocks || []).filter(b =>
    b.dynasty === '明' && b.kind === 'single' && !isBridgeBlock(b)
  )
  const byEntry = {}
  emps.forEach(b => { if (!byEntry[b.entryId]) byEntry[b.entryId] = b })
  const ordered = Object.values(byEntry).sort((a, b) =>
    parseBlockYearSpan(a).start - parseBlockYearSpan(b).start
  )
  const fullGeom = calcFullWidthGeom()
  const leftGeom = calcLeftHalfGeom()
  let top = startTop
  const rects = []
  ordered.forEach(base => {
    const geom = isChongzhenMingBlock(base) ? leftGeom : fullGeom
    const { start, end } = parseBlockYearSpan(base)
    const h = calcEmperorCardHeight(Math.max(1, end - start))
    rects.push(makeMingRect(base, geom, top, h, Z_MID))
    top += h + gap
  })
  return {
    rects,
    bottom: ordered.length ? top - gap : startTop,
  }
}

function centerCollapsedCardTop(rows, anchorY, cardH) {
  const row = (rows || []).find(r => anchorY >= r.y && anchorY < r.y + r.h)
    || (rows || []).find(r => r.y === anchorY)
  if (!row) return anchorY
  return row.y + Math.max(0, Math.round((row.h - cardH) / 2))
}

function pushCollapsedQingCard(next, blocks, rows, exp, ctx) {
  if (isQingContainerActive(exp)) return
  const CARD_H = ctx && ctx.collapsedDynastyCardH != null
    ? ctx.collapsedDynastyCardH
    : COLLAPSED_DYNASTY_CARD_H_RPX
  const y1636 = yearTop(rows, 1636)
  const qingBase = findBlockBase(blocks, QING_ENTRY)
  if (!qingBase || y1636 == null) return
  const top = centerCollapsedCardTop(rows, y1636, CARD_H)
  next.push(makeMingRect(qingBase, calcFullWidthGeom(), top, CARD_H, Z_MID))
}

function enforceCollapsedMingQingCardHeights(blocks, rows, exp, ctx) {
  if (isMingExpanded(exp)) return
  const CARD_H = ctx && ctx.collapsedDynastyCardH != null
    ? ctx.collapsedDynastyCardH
    : COLLAPSED_DYNASTY_CARD_H_RPX
  const collapsedIds = new Set([MING_ENTRY, QING_ENTRY])
  ;(blocks || []).forEach(b => {
    if (!collapsedIds.has(b.entryId)) return
    b.h = CARD_H
    b.top = centerCollapsedCardTop(rows, b.top, CARD_H)
  })
}

function applyCollapsedMingQingRects(blocks, rows, exp, ctx) {
  const GAP = ctx && ctx.collapsedDynastyGapRpx != null
    ? ctx.collapsedDynastyGapRpx
    : BLOCK_V_GAP_RPX
  const CARD_H = ctx && ctx.collapsedDynastyCardH != null
    ? ctx.collapsedDynastyCardH
    : COLLAPSED_DYNASTY_CARD_H_RPX
  const y1368 = yearTop(rows, MING_START)

  let next = (blocks || []).filter(b => {
    if (!isMingZoneBlock(b)) return true
    // 收起态：剔除时间轴碎片（含 1616+ 明左/清右共存条），仅保留下方合成的两张朝代卡
    return false
  })

  const mingBase = findBlockBase(blocks, MING_ENTRY)
  if (mingBase && y1368 != null) {
    const top = centerCollapsedCardTop(rows, y1368, CARD_H)
    next.push(makeMingRect(mingBase, calcFullWidthGeom(), top, CARD_H, Z_MID))
  }
  pushCollapsedQingCard(next, blocks, rows, exp, ctx)
  enforceCollapsedMingQingCardHeights(next, rows, exp, ctx)
  return next
}

/**
 * 明清矩形覆盖：移除时间轴碎片明/清帝王块，左通道堆叠明帝王（镜像 applySongLiaoJinRectLayout）
 */
function applyMingQingRectLayout(blocks, rows, ctx) {
  const exp = ctx.expandedDynasties || {}
  const y1368 = yearTop(rows, MING_START)
  if (y1368 == null) return blocks

  if (!isMingExpanded(exp)) {
    return applyCollapsedMingQingRects(blocks, rows, exp, ctx)
  }

  const GAP = ctx.collapsedDynastyGapRpx || BLOCK_V_GAP_RPX

  let next = (blocks || []).filter(b => {
    if (!isMingZoneBlock(b)) return true
    if (b.entryId === MING_ENTRY) return false
    if (b.entryId === QING_ENTRY) return false
    if (b.entryId === QING_CONTAINER && !isQingContainerActive(exp)) return false
    if (b.dynasty === '明' && b.kind === 'single' && isMingExpanded(exp)) return false
    if (b.dynasty === '清' && b.kind === 'single' && isQingExpanded(exp)) return false
    return true
  })

  const mingStack = stackMingEmperors(blocks, y1368, GAP)
  next.push(...mingStack.rects)

  return next
}

function isLeftChannelBlock(b) {
  if (!b) return false
  const lg = calcLeftHalfGeom()
  const mid = b.leftPct + b.widthPct * 0.5
  return mid <= lg.leftPct + lg.widthPct + 1
}

function normalizeYearAnchors(anchors) {
  const byYear = {}
  ;(anchors || []).forEach(a => {
    if (!Number.isFinite(a.year) || !Number.isFinite(a.y)) return
    if (!byYear[a.year]) byYear[a.year] = []
    byYear[a.year].push(a.y)
  })
  return Object.keys(byYear)
    .map(Number)
    .sort((a, b) => a - b)
    .map(year => ({
      year,
      y: Math.round(byYear[year].reduce((sum, v) => sum + v, 0) / byYear[year].length),
    }))
}

function collectMingExpandedYearAnchors(blocks) {
  const anchors = []
  const add = (year, y) => {
    if (!Number.isFinite(year) || !Number.isFinite(y)) return
    anchors.push({ year, y })
  }

  ;(blocks || []).forEach(b => {
    if (!isMingZoneBlock(b) || isBridgeBlock(b)) return
    if (b.dynasty !== '明' || b.kind !== 'single') return
    const span = parseBlockYearSpan(b)
    add(span.start, b.top)
    add(span.end, b.top + b.h)
  })

  const firstMing = (blocks || [])
    .filter(b => b.dynasty === '明' && !isBridgeBlock(b) && b.kind === 'single')
    .sort((a, b) => a.top - b.top)[0]
  if (firstMing) add(MING_START, firstMing.top)

  return normalizeYearAnchors(anchors)
}

function yearToYFromAnchors(anchors, year) {
  if (!anchors || !anchors.length || !Number.isFinite(year)) return null
  if (year <= anchors[0].year) return anchors[0].y
  if (year >= anchors[anchors.length - 1].year) return anchors[anchors.length - 1].y
  for (let i = 0; i < anchors.length - 1; i++) {
    const a = anchors[i]
    const b = anchors[i + 1]
    if (year < a.year || year > b.year) continue
    if (b.year === a.year) return a.y
    const t = (year - a.year) / (b.year - a.year)
    return Math.round(a.y + t * (b.y - a.y))
  }
  return null
}

function remapMingExpandedTimelineRows(rows, anchors) {
  if (!rows || !rows.length || !anchors || anchors.length < 2) return { delta: 0, oldEndY: 0 }

  let firstIdx = -1
  let lastIdx = -1
  rows.forEach((r, i) => {
    if (r.tE > MING_START && r.tS < MING_ZONE_END) {
      if (firstIdx < 0) firstIdx = i
      lastIdx = i
    }
  })
  if (firstIdx < 0 || lastIdx < 0) return { delta: 0, oldEndY: 0 }

  const oldEndY = rows[lastIdx].y + rows[lastIdx].h
  const yearToY = year => yearToYFromAnchors(anchors, year)

  for (let i = firstIdx; i <= lastIdx; i++) {
    const r = rows[i]
    const y0 = yearToY(Math.max(r.tS, MING_START))
    const y1 = yearToY(Math.min(r.tE, MING_ZONE_END))
    if (y0 == null || y1 == null) continue
    rows[i].y = y0
    rows[i].h = Math.max(BLOCK_MIN_SEG_H, y1 - y0)
  }

  const newEndY = yearToY(MING_ZONE_END) ?? (rows[lastIdx].y + rows[lastIdx].h)
  const delta = newEndY - oldEndY
  for (let i = lastIdx + 1; i < rows.length; i++) {
    rows[i].y += delta
  }
  return { delta, oldEndY }
}

function repositionQingContainerBlock(blocks, rows, exp) {
  if (!isQingContainerActive(exp)) return
  const span = yearBlockSpan(rows, QING_CONTAINER_START, QING_CONTAINER_END)
  if (!span) return
  ;(blocks || []).forEach(b => {
    if (b.entryId !== QING_CONTAINER) return
    b.top = span.top
    b.h = Math.round(span.h)
  })
}

function shiftPostQingZoneBlocks(blocks, delta, oldEndY) {
  if (!delta || !Number.isFinite(oldEndY)) return
  ;(blocks || []).forEach(b => {
    if (b.entryId === QING_CONTAINER) return
    if (b.top >= oldEndY - 1) b.top += delta
  })
}

function shiftPostQingZoneOverlays(overlays, blocks, delta, oldEndY) {
  if (!delta || !overlays || !overlays.length || !Number.isFinite(oldEndY)) return
  const shiftedIds = new Set(
    (blocks || [])
      .filter(b => b.entryId !== QING_CONTAINER && b.top >= oldEndY - 1 + delta)
      .map(b => b.entryId)
  )
  overlays.forEach(ov => {
    if (!shiftedIds.has(ov.entryId)) return
    if (ov.headerTop != null) ov.headerTop += delta
    if (ov.barTop != null) ov.barTop += delta
  })
}

function isYuanContainerBlock(b) {
  if (!b) return false
  return b.entryId === YUAN_CONTAINER || (b.isDynastyContainer && b.containerId === '元')
}

/** 元容器展开时，明太祖堆叠须与容器底缘保持标准间距 */
function ensureMingGapAfterYuanContainer(blocks, gap, overlays) {
  const yuan = (blocks || []).find(isYuanContainerBlock)
  if (!yuan) return 0

  const mingBlocks = (blocks || []).filter(b =>
    b.dynasty === '明' && b.kind === 'single' && !isBridgeBlock(b)
  )
  if (!mingBlocks.length) return 0

  const firstMing = mingBlocks.reduce((a, b) => (a.top < b.top ? a : b))
  const targetTop = yuan.top + yuan.h + gap
  const delta = Math.round(targetTop - firstMing.top)
  if (delta <= 1) return 0

  const mingIds = new Set(mingBlocks.map(b => b.entryId))
  mingBlocks.forEach(b => { b.top += delta })
  if (overlays && overlays.length) {
    overlays.forEach(ov => {
      if (!mingIds.has(ov.entryId)) return
      if (ov.headerTop != null) ov.headerTop += delta
      if (ov.barTop != null) ov.barTop += delta
    })
  }
  return delta
}

/**
 * 明展开态：左通道堆叠后重映射时间轴，并定位清容器（镜像 syncSongExpandedTimeline）
 */
function syncMingExpandedTimeline(rows, blocks, exp, ctx, overlays) {
  if (!isMingExpanded(exp) || !rows || !blocks) return
  const GAP = ctx && ctx.collapsedDynastyGapRpx != null
    ? ctx.collapsedDynastyGapRpx
    : BLOCK_V_GAP_RPX
  ensureMingGapAfterYuanContainer(blocks, GAP, overlays)
  const anchors = collectMingExpandedYearAnchors(blocks)
  const remap = remapMingExpandedTimelineRows(rows, anchors) || {}
  const delta = remap.delta || 0
  const oldEndY = remap.oldEndY
  repositionQingContainerBlock(blocks, rows, exp)
  shiftPostQingZoneBlocks(blocks, delta, oldEndY)
  shiftPostQingZoneOverlays(overlays, blocks, delta, oldEndY)
}

function filterActiveForMingQing(active, tS, expandedDynasties) {
  const list = (active || []).filter(Boolean)
  const containerActive = isQingContainerActive(expandedDynasties)

  return list.filter(e => {
    if (isQingContainerSpanEntry(e)) {
      return containerActive && tS >= QING_CONTAINER_START
    }
    if (containerActive && e.isEmperor && isQingSequenceEntry(e)) {
      return false
    }
    if (containerActive && e.isCollapsedDynastyCard && isQingSequenceEntry(e)) {
      return false
    }
    return true
  })
}

function makePlacement(entry, leftPct, widthPct, colIndex, numCols) {
  return {
    id: entry.id,
    leftPct: Math.max(0, Math.min(100, leftPct)),
    widthPct: Math.max(8, Math.min(100, widthPct)),
    colIndex: colIndex != null ? colIndex : 0,
    numCols: numCols != null ? numCols : 1,
  }
}

/** 明左半 + 清容器全宽（时间轴切片阶段，避免 containerSpan 分支吞掉明条目） */
function assignMingWithQingContainerPlacements(active, prevPlacements, tS, tE) {
  const prevMap = {}
  if (prevPlacements) prevPlacements.forEach(p => { prevMap[p.id] = p })

  const leftGeom = calcLeftHalfGeom()
  const fullGeom = calcFullWidthGeom()
  const mingEntries = active.filter(isMingSequenceEntry)
  const qingContainers = active.filter(isQingContainerSpanEntry)
  const ideal = {}

  mingEntries.forEach(e => {
    const isChongzhen = e.displayName === '崇祯' || e.id === CHONGZHEN_ENTRY
    const geom = isChongzhen ? leftGeom : fullGeom
    ideal[e.id] = makePlacement(
      e, geom.leftPct, geom.widthPct, geom.colIndex || 0, geom.numCols || 1
    )
  })
  qingContainers.forEach(e => {
    ideal[e.id] = makePlacement(e, 0, 100, 0, 1)
  })

  return active
    .filter(e => ideal[e.id])
    .map(e => {
      const next = ideal[e.id]
      const prev = prevMap[e.id]
      if (prev && e.end !== tE && e.start !== tS) {
        const same =
          Math.abs(prev.leftPct - next.leftPct) < 0.5 &&
          Math.abs(prev.widthPct - next.widthPct) < 0.5
        if (same) return Object.assign({}, prev, { id: e.id })
      }
      return next
    })
    .sort((a, b) => a.leftPct - b.leftPct)
}

function trimTimelineBelow(rows, targetBottomY) {
  if (!rows || !rows.length) return 0
  const lastRow = rows[rows.length - 1]
  const timelineBottom = lastRow.y + lastRow.h
  const trimAmount = timelineBottom - targetBottomY
  if (trimAmount <= 1) return 0

  let remaining = trimAmount
  let trimIdx = rows.length - 1
  while (trimIdx >= 0 && remaining > 0) {
    const cut = Math.min(rows[trimIdx].h, remaining)
    rows[trimIdx].h -= cut
    remaining -= cut
    trimIdx -= 1
  }

  const rechainStart = Math.max(0, trimIdx + 1)
  let chainY = rechainStart > 0
    ? rows[rechainStart - 1].y + rows[rechainStart - 1].h
    : rows[0].y
  for (let i = rechainStart; i < rows.length; i++) {
    rows[i].y = chainY
    chainY += rows[i].h
  }
  return trimAmount
}

function syncCollapsedMingQingTimeline(rows, blocks, overlays, exp, ctx) {
  if (isQingContainerActive(exp) || !rows || !rows.length) return 0

  const GAP = ctx && ctx.collapsedDynastyGapRpx != null
    ? ctx.collapsedDynastyGapRpx
    : BLOCK_V_GAP_RPX
  const ming = findBlockBase(blocks, MING_ENTRY)
  const qing = findBlockBase(blocks, QING_ENTRY)
  if (!ming || !qing) return 0

  const targetQingTop = ming.top + ming.h + GAP
  if (Math.abs(qing.top - targetQingTop) > 1) {
    qing.top = targetQingTop
  }

  const contentBottom = qing.top + qing.h
  const trimAmount = trimTimelineBelow(rows, contentBottom)
  const shiftBoundary = contentBottom

  if (trimAmount > 0 && overlays && overlays.length) {
    overlays.forEach(ov => {
      if (ov.headerTop == null || ov.headerTop < shiftBoundary - 1) return
      if (ov.entryId === MING_ENTRY || ov.entryId === QING_ENTRY) return
      ov.headerTop -= trimAmount
      if (ov.barTop != null && ov.barTop >= shiftBoundary - 1) ov.barTop -= trimAmount
    })
  }

  return trimAmount
}

module.exports = {
  BLOCK_H_GAP_PCT,
  BLOCK_V_GAP_RPX,
  BLOCK_MIN_SEG_H,
  COLLAPSED_DYNASTY_CARD_H_RPX,
  MING_START,
  MING_QING_COEXIST_START,
  MING_QING_COEXIST_END,
  QING_CONTAINER_START,
  QING_CONTAINER_END,
  QING_ENTRY,
  MING_ENTRY,
  QING_CONTAINER,
  MING_AXIS_KEY,
  MING_LINKED_AXIS_KEYS,
  isMingLinkedAxisKey,
  applyMingLinkedExpansion,
  calcLeftHalfGeom,
  calcRightHalfGeom,
  calcFullWidthGeom,
  isMingExpanded,
  isQingExpanded,
  isQingContainerActive,
  isQingEmperorsVisible,
  isQingContainerSpanEntry,
  isMingSequenceEntry,
  isQingSequenceEntry,
  filterActiveForMingQing,
  assignMingWithQingContainerPlacements,
  applyMingQingRectLayout,
  syncMingExpandedTimeline,
  repositionQingContainerBlock,
  shiftPostQingZoneBlocks,
  shiftPostQingZoneOverlays,
  syncCollapsedMingQingTimeline,
  yearTop,
  yearBlockSpan,
}
