/**
 * 宋辽金元双通道布局（907–1279）
 * 左半：五代十国容器 + 北宋/南宋帝王
 * 右半：辽/金容器（十六国式显隐）+ 元（1271 起）
 */

const BLOCK_H_GAP_PCT = 3.2
const BLOCK_V_GAP_RPX = 16
const BLOCK_MIN_SEG_H = 20
const COLLAPSED_DYNASTY_CARD_H_RPX = 200

const ZONE_START = 907
const ZONE_END = 1279
const WUDAI_LAYOUT_END = 960
const BEISONG_END = 1127
const LIAO_END = 1125
const JIN_START = 1115
const JIN_END = 1234
const YUAN_AXIS = 1260
/** 元一级容器时间轴起止（与 DYNASTY_CONTAINER_LAYOUTS.元 一致） */
const YUAN_CONTAINER_START = 1260
const YUAN_CONTAINER_END = 1368

const SONG_REGIMES = new Set(['北宋', '南宋'])
/** 时间轴 960「宋」节点统一控制的政权 */
const SONG_AXIS_KEY = '宋'
const SONG_CONTROLLED_KEYS = ['北宋', '南宋', '辽', '金']
/** 时间轴上可点击收展的联动轴标（四节点同控宋辽金元区域） */
const SONG_LINKED_AXIS_KEYS = ['宋', '金', '南宋', '元']

function isSongLinkedAxisKey(dynKey) {
  return SONG_LINKED_AXIS_KEYS.indexOf(dynKey) >= 0
}

/** 四轴标联动：展开/收起同一套政权键 */
function applySongLinkedExpansion(next, willExpand) {
  SONG_CONTROLLED_KEYS.forEach(name => {
    if (willExpand) next[name] = true
    else delete next[name]
  })
  if (willExpand) {
    next[SONG_AXIS_KEY] = true
    next['元'] = true
  } else {
    delete next[SONG_AXIS_KEY]
    delete next['元']
  }
  return next
}
const WUDAI_FIVE_REGIMES = new Set(['后梁', '后唐', '后晋', '后汉', '后周'])
const HIDDEN_DYNASTIES = new Set(['西夏', '西辽', '大理', '后金'])

const TEN_KINGDOM_KEYS = [
  '十国·吴', '十国·前蜀', '十国·吴越', '十国·闽', '十国·南汉',
  '十国·南平', '十国·后蜀', '十国·南唐', '十国·北汉',
]

function isInSongLiaoJinZone(tS) {
  return tS >= ZONE_START && tS < ZONE_END
}

function calcHalfWidthPct() {
  return (100 - BLOCK_H_GAP_PCT) / 2
}

function calcLeftHalfGeom() {
  const w = calcHalfWidthPct()
  return { leftPct: 0, widthPct: w }
}

function calcRightHalfGeom() {
  const w = calcHalfWidthPct()
  return { leftPct: w + BLOCK_H_GAP_PCT, widthPct: w }
}

function isSongEntry(entry) {
  if (!entry) return false
  return SONG_REGIMES.has(entry.dynastyName) ||
    SONG_REGIMES.has(entry.dynastyGroup) ||
    SONG_REGIMES.has(entry.displayName)
}

function isYuanEntry(entry) {
  if (!entry) return false
  return entry.dynastyName === '元' || entry.dynastyGroup === '元'
}

function isWudaiEntry(entry) {
  if (!entry) return false
  if (entry.containerId === '五代十国') return true
  if (entry.isContainerSpan && entry.containerId === '五代十国') return true
  if (entry.id === 'collapsed_五代十国') return true
  if (entry.isCollapsedDynastyCard && entry.dynastyName === '五代十国') return true
  return false
}

function isLiaoEntry(entry) {
  if (!entry) return false
  if (entry.containerId === '辽') return true
  if (entry.isContainerSpan && entry.containerId === '辽') return true
  return entry.dynastyName === '辽' || entry.dynastyGroup === '辽'
}

function isJinEntry(entry) {
  if (!entry) return false
  if (entry.containerId === '金') return true
  if (entry.isContainerSpan && entry.containerId === '金') return true
  return entry.dynastyName === '金' || entry.dynastyGroup === '金'
}

function isLeftChannelEntry(entry) {
  if (!entry) return false
  if (isWudaiEntry(entry)) return true
  if (isSongEntry(entry)) return true
  return false
}

function isRightChannelEntry(entry, tS) {
  if (!entry) return false
  if (isYuanContainerSpanEntry(entry)) return false
  if (entry.containerId === '元' && entry.isEmperor) return false
  if (tS >= YUAN_AXIS && isYuanEntry(entry) && !isYuanContainerSpanEntry(entry)) return true
  if (tS < LIAO_END && isLiaoEntry(entry)) return true
  if (tS >= JIN_START && tS < JIN_END && isJinEntry(entry)) return true
  return false
}

function isWudaiFiveRegime(dyn) {
  return dyn && WUDAI_FIVE_REGIMES.has(dyn.name)
}

function isWudaiTenKingdomColumn(colKey) {
  return TEN_KINGDOM_KEYS.includes(colKey)
}

function isWudaiContainerColumn(colKey) {
  return WUDAI_FIVE_REGIMES.has(colKey) || isWudaiTenKingdomColumn(colKey)
}

function isWudaiExpanded(expandedDynasties) {
  return true
}

function isSongExpanded(expandedDynasties) {
  if (!expandedDynasties) return false
  if (expandedDynasties[SONG_AXIS_KEY]) return true
  return SONG_CONTROLLED_KEYS.some(k => !!expandedDynasties[k])
}

function isBeisongExpanded(expandedDynasties) {
  return isSongExpanded(expandedDynasties)
}

function isNansongExpanded(expandedDynasties) {
  return isSongExpanded(expandedDynasties)
}

/** 元展开/收起完全跟随宋轴标 */
function isYuanExpanded(expandedDynasties) {
  return isSongExpanded(expandedDynasties)
}

/** 元容器与二级帝王：仅宋展开态展示 */
function isYuanContainerActive(expandedDynasties) {
  return isSongExpanded(expandedDynasties)
}

function isYuanEmperorsVisible(expandedDynasties) {
  return isYuanContainerActive(expandedDynasties)
}

function isYuanContainerSpanEntry(entry) {
  if (!entry) return false
  return (entry.isContainerSpan || entry.isDynastyContainer) && entry.containerId === '元'
}

/** 左侧任一相关轴标展开 → 右半辽/金可见（十六国式） */
function isLeftChannelExpanded(expandedDynasties, tS) {
  if (!expandedDynasties) return false
  if (tS < WUDAI_LAYOUT_END) return isWudaiExpanded(expandedDynasties)
  if (tS < ZONE_END) return isSongExpanded(expandedDynasties)
  return false
}

function shouldShowLiaoContainer(expandedDynasties, tS) {
  return tS >= ZONE_START && tS < LIAO_END &&
    isLeftChannelExpanded(expandedDynasties, tS)
}

function shouldShowJinContainer(expandedDynasties, tS) {
  return tS >= JIN_START && tS < JIN_END &&
    isLeftChannelExpanded(expandedDynasties, tS)
}

function shouldShowYuanOnRight(tS) {
  return tS >= YUAN_AXIS
}

/** 辽容器外壳：左通道（五代/北宋）任一展开即可见，无需独立轴标 */
function isLiaoContainerActive(expandedDynasties) {
  return isWudaiExpanded(expandedDynasties) || isBeisongExpanded(expandedDynasties)
}

/** 辽帝王列表：随「宋」展开而展开 */
function isLiaoEmperorsVisible(expandedDynasties) {
  return isSongExpanded(expandedDynasties)
}

/** 金容器外壳：「宋」展开即可见 */
function isJinContainerActive(expandedDynasties) {
  return isSongExpanded(expandedDynasties)
}

/** 金帝王列表：随「宋」展开而展示 */
function isJinEmperorsVisible(expandedDynasties) {
  return isSongExpanded(expandedDynasties)
}

function filterHiddenDynasties(entries) {
  return (entries || []).filter(e => {
    const name = e.dynastyName || e.dynastyGroup || e.displayName || ''
    return !HIDDEN_DYNASTIES.has(name)
  })
}

function filterActiveForSongLiaoJin(active, tS, expandedDynasties) {
  let list = filterHiddenDynasties(active)
  const showLiao = shouldShowLiaoContainer(expandedDynasties, tS)
  const showJin = shouldShowJinContainer(expandedDynasties, tS)

  list = list.filter(e => {
    if (isLiaoEntry(e) && !showLiao) return false
    if (isJinEntry(e) && !showJin) return false
    if (isJinEntry(e) && tS >= JIN_END) return false
    if (isYuanContainerSpanEntry(e)) {
      return tS >= YUAN_CONTAINER_START
    }
    if (isYuanEntry(e) && tS < YUAN_AXIS) return false
    if (isYuanEntry(e) && tS >= JIN_END && tS < YUAN_AXIS) return false
    return true
  })
  return list
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

function assignSongLiaoJinPlacements(active, prevPlacements, tS, tE, expandedDynasties) {
  const filtered = filterActiveForSongLiaoJin(active, tS, expandedDynasties)
  if (!filtered.length) return []

  const leftGeom = calcLeftHalfGeom()
  const rightGeom = calcRightHalfGeom()
  const prevMap = {}
  if (prevPlacements) prevPlacements.forEach(p => { prevMap[p.id] = p })

  const placements = filtered.map(e => {
    let geom
    if (isLeftChannelEntry(e)) {
      geom = leftGeom
    } else if (isRightChannelEntry(e, tS)) {
      geom = rightGeom
    } else {
      geom = { leftPct: 0, widthPct: 100 }
    }
    const next = makePlacement(e, geom.leftPct, geom.widthPct, 0, 2)
    const prev = prevMap[e.id]
    if (prev && e.end !== tE && e.start !== tS) {
      const same =
        Math.abs(prev.leftPct - next.leftPct) < 0.5 &&
        Math.abs(prev.widthPct - next.widthPct) < 0.5
      if (same) return Object.assign({}, prev, { id: e.id })
    }
    return next
  })

  return placements.sort((a, b) => a.leftPct - b.leftPct)
}

function buildTenKingdomRegimeEntries(emperors, colorIdx) {
  const byKey = {}
  ;(emperors || []).forEach(emp => {
    const key = emp.dynasty2 || emp.dynasty
    if (!key || !String(key).startsWith('十国·')) return
    if (!byKey[key]) byKey[key] = []
    byKey[key].push(emp)
  })
  return TEN_KINGDOM_KEYS.filter(k => byKey[k]).map(key => {
    const list = byKey[key]
    const start = Math.min(...list.map(e => e.start))
    const end = Math.max(...list.map(e => e.end))
    const label = key.replace(/^十国·/, '')
    return {
      id:              `wudai_regime_${key}`,
      isEmperor:       false,
      isRegimeOnly:    true,
      dynastyName:     label,
      dynastyGroup:    '五代十国',
      displayName:     label,
      start,
      end,
      years:           Math.max(1, end - start),
      colorIdx:        colorIdx != null ? colorIdx : 0,
      startStr:        String(start),
      endStr:          String(end),
      containerId:     '五代十国',
      containerColumn: key,
      hideTime:        true,
    }
  })
}

function buildCollapsedWudaiEntry(colorIdx) {
  return {
    id:              'collapsed_五代十国',
    isEmperor:       false,
    isCollapsedDynastyCard: true,
    dynastyName:     '五代十国',
    dynastyGroup:    '五代十国',
    displayName:     '五代十国',
    dynastyId:       'CD_HX_WUDAISHIGUO',
    entityType:      'regime',
    entityId:        'CD_HX_WUDAISHIGUO',
    start:           ZONE_START,
    end:             WUDAI_LAYOUT_END,
    years:           979 - ZONE_START,
    colorIdx:        colorIdx != null ? colorIdx : 0,
    startStr:        '907',
    endStr:          '979',
  }
}

const BLOCK_RADIUS_RPX = 12
const EMP_CARD_H_MIN_RPX = 80
const EMP_CARD_H_MAX_RPX = 200
const EMP_CARD_REF_YEARS = 71
const Z_MID = 5

const BEISONG_ENTRY = 'ZQ_HX_BEISONG_BEISONG'
const NANSONG_ENTRY = 'ZQ_HX_NANSONG_NANSONG'
const JIN_ENTRY = 'ZQ_HX_JIN_JIN'
const YUAN_ENTRY = 'ZQ_HX_YUAN_YUAN'
const MING_ENTRY = 'ZQ_HX_MING_MING'
const WUDAI_COLLAPSED = 'collapsed_五代十国'
const WUDAI_CONTAINER = 'container_span_五代十国'
const LIAO_CONTAINER = 'container_span_辽'
const JIN_CONTAINER = 'container_span_金'
const YUAN_CONTAINER = 'container_span_元'

function isBridgeBlock(b) {
  return !!(b && (b.isLBridge || b.isNanbeiLBridge || b.isSongHalfLBridge || b.isXiaowudiBridge))
}

function findRowForYear(rows, year) {
  const exactStart = rows.find(r => r.tS === year)
  if (exactStart) return { row: exactStart, ratio: 0 }
  const exactEnd = rows.find(r => r.tE === year)
  if (exactEnd) return { row: exactEnd, ratio: 1 }
  const containing = rows.find(r => r.tS < year && r.tE > year)
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

function yearEndY(rows, year) {
  return yearY(rows, year)
}

/** 将起止年映射为画布纵向区间（与时间轴刻度对齐） */
function yearBlockSpan(rows, startYear, endYear) {
  const top = yearTop(rows, startYear)
  const endY = yearEndY(rows, endYear)
  if (top == null || endY == null) return null
  const bottom = Math.max(top + BLOCK_MIN_SEG_H, endY)
  return {
    top,
    h: Math.max(BLOCK_MIN_SEG_H, bottom - top),
  }
}

const { parseHistoryYearSpan } = require('../year-format')

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

function isSongZoneBlock(b) {
  if (!b || isBridgeBlock(b)) return false
  const d = b.dynasty
  if (d === '北宋' || d === '南宋' || d === '辽' || d === '金' || d === '元' || d === '五代十国') return true
  const id = b.entryId || ''
  return id === WUDAI_COLLAPSED || id === WUDAI_CONTAINER ||
    id === LIAO_CONTAINER || id === JIN_CONTAINER ||
    id === BEISONG_ENTRY || id === NANSONG_ENTRY || id === JIN_ENTRY || id === YUAN_ENTRY
}

function makeSongRect(base, geom, top, h, zIndex) {
  return Object.assign({}, base, {
    id:            `${base.entryId}_song_rect`,
    top,
    h:             Math.max(BLOCK_MIN_SEG_H, h),
    leftPct:       geom.leftPct,
    widthPct:      geom.widthPct,
    zIndex:        zIndex != null ? zIndex : Z_MID,
    rTL: true, rTR: true, rBR: true, rBL: true,
    radiusStyle:   fullRadiusStyle(),
    edgeClass:     '',
    edgeTop: false, edgeRight: false, edgeBottom: false, edgeLeft: false,
    fillSeamFix:   false,
    isLBridge: false, isNanbeiLBridge: false,
    isSongHalfLBridge: false, isXiaowudiBridge: false,
  })
}

function stackDynastyEmperors(sourceBlocks, dynasty, geom, startTop, gap) {
  const emps = sourceBlocks.filter(b =>
    b.dynasty === dynasty && b.kind === 'single' && !isBridgeBlock(b)
  )
  const byEntry = {}
  emps.forEach(b => { if (!byEntry[b.entryId]) byEntry[b.entryId] = b })
  const ordered = Object.values(byEntry).sort((a, b) =>
    parseBlockYearSpan(a).start - parseBlockYearSpan(b).start
  )
  let top = startTop
  const rects = []
  ordered.forEach(base => {
    const { start, end } = parseBlockYearSpan(base)
    const h = calcEmperorCardHeight(Math.max(1, end - start))
    rects.push(makeSongRect(base, geom, top, h, Z_MID))
    top += h + gap
  })
  return {
    rects,
    bottom: ordered.length ? top - gap : startTop,
  }
}

function calcFullWidthGeom() {
  return { leftPct: 0, widthPct: 100 }
}

function centerCollapsedCardTop(rows, anchorY, cardH) {
  const row = (rows || []).find(r => anchorY >= r.y && anchorY < r.y + r.h)
    || (rows || []).find(r => r.y === anchorY)
  if (!row) return anchorY
  return row.y + Math.max(0, Math.round((row.h - cardH) / 2))
}

function pushCollapsedYuanCard(next, blocks, exp, ctx, top) {
  if (isYuanContainerActive(exp)) return
  const CARD_H = ctx.collapsedDynastyCardH || COLLAPSED_DYNASTY_CARD_H_RPX
  const yuanBase = findBlockBase(blocks, YUAN_ENTRY)
  if (!yuanBase || !Number.isFinite(top)) return
  next.push(makeSongRect(yuanBase, calcFullWidthGeom(), top, CARD_H, Z_MID))
}

function enforceSongCollapsedDynastyCardHeights(blocks, exp, ctx) {
  if (isSongExpanded(exp)) return
  const CARD_H = ctx.collapsedDynastyCardH || COLLAPSED_DYNASTY_CARD_H_RPX
  const collapsedIds = new Set([
    WUDAI_COLLAPSED, BEISONG_ENTRY, NANSONG_ENTRY, JIN_ENTRY, YUAN_ENTRY,
  ])
  blocks.forEach(b => {
    if (!collapsedIds.has(b.entryId)) return
    b.h = CARD_H
  })
}

function findBlockBase(blocks, entryId) {
  return blocks.find(b => b.entryId === entryId && !isBridgeBlock(b))
}

function resolveCollapsedJinBase(blocks) {
  const existing = findBlockBase(blocks, JIN_ENTRY)
  if (existing) return existing
  const template = findBlockBase(blocks, NANSONG_ENTRY) || findBlockBase(blocks, BEISONG_ENTRY)
  if (!template) return null
  return Object.assign({}, template, {
    entryId: JIN_ENTRY,
    legacyId: 'HX-J',
    dynasty: '金',
    kind: 'dynasty',
    displayName: '金',
    person: '金',
    timeRange: '1115–1234',
    hideTime: false,
    highlights: undefined,
    dynastyId: 'CD_HX_JIN',
    entityType: 'regime',
    entityId: JIN_ENTRY,
  })
}

function appendCollapsedSongDualRow(next, blocks, leftGeom, rightGeom, dualTop, CARD_H) {
  const nsBase = findBlockBase(blocks, NANSONG_ENTRY)
  const jinBase = resolveCollapsedJinBase(blocks)
  if (nsBase) next.push(makeSongRect(nsBase, leftGeom, dualTop, CARD_H, Z_MID))
  if (jinBase) next.push(makeSongRect(jinBase, rightGeom, dualTop, CARD_H, Z_MID))
}

function applyCollapsedSongLiaoJinRects(blocks, rows, exp, ctx) {
  const leftGeom = calcLeftHalfGeom()
  const rightGeom = calcRightHalfGeom()
  const GAP = ctx.collapsedDynastyGapRpx || BLOCK_V_GAP_RPX
  const CARD_H = ctx.collapsedDynastyCardH || COLLAPSED_DYNASTY_CARD_H_RPX
  const y907 = yearTop(rows, ZONE_START)
  if (y907 == null) return blocks

  let next = blocks.filter(b => {
    if (!isSongZoneBlock(b)) return true
    if (b.entryId === YUAN_CONTAINER && !isYuanContainerActive(exp)) return false
    if (!isSongExpanded(exp) && (
      b.entryId === NANSONG_ENTRY ||
      b.entryId === JIN_ENTRY ||
      b.entryId === YUAN_ENTRY
    )) return false
    return true
  })

  let leftTop = y907
  const wudaiBase = findBlockBase(blocks, WUDAI_COLLAPSED)
  if (wudaiBase) {
    next.push(makeSongRect(wudaiBase, leftGeom, leftTop, CARD_H, Z_MID))
    leftTop += CARD_H + GAP
  }

  const bsBase = findBlockBase(blocks, BEISONG_ENTRY)
  if (bsBase) {
    next.push(makeSongRect(bsBase, leftGeom, leftTop, CARD_H, Z_MID))
    leftTop += CARD_H + GAP
  }

  const beisongBottom = leftTop - GAP
  const liaoBase = findBlockBase(blocks, LIAO_CONTAINER)
  if (liaoBase && beisongBottom > y907) {
    next.push(makeSongRect(
      liaoBase, rightGeom, y907,
      Math.max(BLOCK_MIN_SEG_H, beisongBottom - y907), Z_MID
    ))
  }

  appendCollapsedSongDualRow(next, blocks, leftGeom, rightGeom, leftTop, CARD_H)
  leftTop += CARD_H + GAP
  pushCollapsedYuanCard(next, blocks, exp, ctx, leftTop)

  enforceSongCollapsedDynastyCardHeights(next, exp, ctx)
  return next
}

/**
 * 宋辽金元双通道矩形覆盖：左通道堆叠、右通道辽/金容器联动、移除碎片化帝王块
 */
function applySongLiaoJinRectLayout(blocks, rows, ctx) {
  const exp = ctx.expandedDynasties || {}
  const y907 = yearTop(rows, ZONE_START)
  if (y907 == null) return blocks

  const leftGeom = calcLeftHalfGeom()
  const rightGeom = calcRightHalfGeom()
  const GAP = ctx.collapsedDynastyGapRpx || BLOCK_V_GAP_RPX
  const CARD_H = ctx.collapsedDynastyCardH || COLLAPSED_DYNASTY_CARD_H_RPX
  const y1271 = yearTop(rows, YUAN_AXIS)

  const anyLeftExpanded = isWudaiExpanded(exp) || isSongExpanded(exp)
  const showLiaoContainer = isWudaiExpanded(exp) || isSongExpanded(exp)
  const showJinContainer = isSongExpanded(exp)

  if (!anyLeftExpanded && !showLiaoContainer && !showJinContainer && !isYuanExpanded(exp)) {
    return applyCollapsedSongLiaoJinRects(blocks, rows, exp, ctx)
  }

  let next = blocks.filter(b => {
    if (!isSongZoneBlock(b)) return true
    if (b.dynasty === '辽' && b.kind === 'single' && showLiaoContainer) return false
    if (b.dynasty === '金' && b.kind === 'single' && showJinContainer) return false
    if (b.entryId === WUDAI_COLLAPSED) return false
    if (b.entryId === WUDAI_CONTAINER) return false
    if (b.entryId === BEISONG_ENTRY) return false
    if (b.entryId === NANSONG_ENTRY) return false
    if (b.entryId === JIN_ENTRY) return false
    if (b.entryId === YUAN_ENTRY) return false
    if (b.entryId === LIAO_CONTAINER) return false
    if (b.entryId === JIN_CONTAINER) return false
    if (b.entryId === YUAN_CONTAINER && !isYuanContainerActive(exp)) return false
    if (b.dynasty === '北宋' && b.kind === 'single' && isSongExpanded(exp)) return false
    if (b.dynasty === '南宋' && b.kind === 'single' && isSongExpanded(exp)) return false
    if (b.dynasty === '元' && b.kind === 'single' && isYuanExpanded(exp)) return false
    return true
  })

  let leftTop = y907

  if (isWudaiExpanded(exp)) {
    const base = findBlockBase(blocks, WUDAI_CONTAINER)
    if (base) {
      const h = Math.max(base.h || 0, CARD_H)
      next.push(makeSongRect(base, leftGeom, leftTop, h, Z_MID))
      leftTop += h + GAP
    }
  } else {
    const base = findBlockBase(blocks, WUDAI_COLLAPSED)
    if (base) {
      next.push(makeSongRect(base, leftGeom, leftTop, CARD_H, Z_MID))
      leftTop += CARD_H + GAP
    }
  }

  if (isSongExpanded(exp)) {
    const bsStack = stackDynastyEmperors(blocks, '北宋', leftGeom, leftTop, GAP)
    next.push(...bsStack.rects)
    if (bsStack.rects.length) leftTop = bsStack.bottom + GAP

    // 展开态：南宋紧接北宋堆叠，不按时间轴 1127 锚点（避免与钦宗之间出现大段空白）
    const nsStack = stackDynastyEmperors(blocks, '南宋', leftGeom, leftTop, GAP)
    next.push(...nsStack.rects)
    if (nsStack.rects.length) leftTop = Math.max(leftTop, nsStack.bottom + GAP)
  } else {
    const bsBase = findBlockBase(blocks, BEISONG_ENTRY)
    if (bsBase) {
      next.push(makeSongRect(bsBase, leftGeom, leftTop, CARD_H, Z_MID))
      leftTop += CARD_H + GAP
    }
    // 收起态：南宋与金在底部双卡行展示，不在 1127 时间轴位单独占位
  }

  const songCollapsedDualRow = !isSongExpanded(exp)
  const beisongBottom = !isSongExpanded(exp) && leftTop > y907
    ? leftTop - GAP
    : null

  const leftBottom = leftTop > y907 ? leftTop - GAP : y907
  const totalLeftH = Math.max(BLOCK_MIN_SEG_H, leftBottom - y907)

  const liaoSpan = yearBlockSpan(rows, ZONE_START, LIAO_END)
  const jinSpan = yearBlockSpan(rows, JIN_START, JIN_END)

  if (showLiaoContainer) {
    const liaoBase = findBlockBase(blocks, LIAO_CONTAINER)
    const jinBase = showJinContainer ? findBlockBase(blocks, JIN_CONTAINER) : null
    if (liaoBase) {
      if (!isSongExpanded(exp)) {
        // 收起态：辽底缘仅对齐北宋底缘（不含南宋）
        const liaoTop = y907
        const liaoH = Math.max(
          BLOCK_MIN_SEG_H,
          (beisongBottom != null ? beisongBottom : (liaoTop + totalLeftH)) - liaoTop
        )
        next.push(makeSongRect(liaoBase, rightGeom, liaoTop, liaoH, Z_MID))
      } else if (jinBase && jinSpan) {
        if (liaoSpan) {
          next.push(makeSongRect(liaoBase, rightGeom, liaoSpan.top, liaoSpan.h, Z_MID))
        }
        next.push(makeSongRect(jinBase, rightGeom, jinSpan.top, jinSpan.h, Z_MID + 1))
      } else if (liaoSpan) {
        next.push(makeSongRect(liaoBase, rightGeom, liaoSpan.top, liaoSpan.h, Z_MID))
      } else if (jinBase) {
        const liaoH = Math.max(BLOCK_MIN_SEG_H, Math.round(totalLeftH * 0.55))
        const jinH = Math.max(BLOCK_MIN_SEG_H, totalLeftH - liaoH - GAP)
        next.push(makeSongRect(liaoBase, rightGeom, y907, liaoH, Z_MID))
        next.push(makeSongRect(jinBase, rightGeom, y907 + liaoH + GAP, jinH, Z_MID))
      } else {
        next.push(makeSongRect(liaoBase, rightGeom, y907, totalLeftH, Z_MID))
      }
    }
  } else if (showJinContainer) {
    const jinBase = findBlockBase(blocks, JIN_CONTAINER)
    if (jinBase) {
      if (jinSpan) {
        next.push(makeSongRect(jinBase, rightGeom, jinSpan.top, jinSpan.h, Z_MID))
      } else {
        next.push(makeSongRect(jinBase, rightGeom, y907, totalLeftH, Z_MID))
      }
    }
  }

  const yuanContainerActive = isYuanContainerActive(exp)

  if (songCollapsedDualRow) {
    const dualRowTop = leftTop
    appendCollapsedSongDualRow(next, blocks, leftGeom, rightGeom, dualRowTop, CARD_H)
    leftTop += CARD_H + GAP
    pushCollapsedYuanCard(next, blocks, exp, ctx, leftTop)
  } else if (isYuanExpanded(exp) && !yuanContainerActive) {
    const stacked = stackDynastyEmperors(
      blocks,
      '元',
      rightGeom,
      y1271 != null ? y1271 : leftBottom,
      GAP
    )
    next.push(...stacked.rects)
  } else if (!showLiaoContainer && !showJinContainer && !yuanContainerActive) {
    pushCollapsedYuanCard(next, blocks, exp, ctx, leftTop)
  }

  enforceSongCollapsedDynastyCardHeights(next, exp, ctx)
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

function collectSongExpandedYearAnchors(blocks) {
  const anchors = []
  const add = (year, y) => {
    if (!Number.isFinite(year) || !Number.isFinite(y)) return
    anchors.push({ year, y })
  }

  blocks.forEach(b => {
    if (!isSongZoneBlock(b) || isBridgeBlock(b)) return
    if (!isLeftChannelBlock(b)) return
    const span = parseBlockYearSpan(b)
    if (!span) return
    add(span.start, b.top)
    add(span.end, b.top + b.h)
  })

  const firstLeft = blocks
    .filter(b => isSongZoneBlock(b) && !isBridgeBlock(b) && isLeftChannelBlock(b))
    .sort((a, b) => a.top - b.top)[0]
  if (firstLeft) add(ZONE_START, firstLeft.top)

  const nsFirst = blocks
    .filter(b => b.dynasty === '南宋' && b.kind === 'single' && !isBridgeBlock(b))
    .sort((a, b) => a.top - b.top)[0]
  if (nsFirst) add(BEISONG_END, nsFirst.top)

  const yuanFirst = blocks
    .filter(b => b.dynasty === '元' && b.kind === 'single' && !isBridgeBlock(b))
    .sort((a, b) => a.top - b.top)[0]
  if (yuanFirst) add(YUAN_AXIS, yuanFirst.top)

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

function remapSongExpandedTimelineRows(rows, anchors) {
  if (!rows || !rows.length || !anchors || anchors.length < 2) return 0

  let firstIdx = -1
  let lastIdx = -1
  rows.forEach((r, i) => {
    if (r.tE > ZONE_START && r.tS < ZONE_END) {
      if (firstIdx < 0) firstIdx = i
      lastIdx = i
    }
  })
  if (firstIdx < 0 || lastIdx < 0) return 0

  const oldEndY = rows[lastIdx].y + rows[lastIdx].h
  const yearY = year => yearToYFromAnchors(anchors, year)

  for (let i = firstIdx; i <= lastIdx; i++) {
    const r = rows[i]
    const y0 = yearY(Math.max(r.tS, ZONE_START))
    const y1 = yearY(Math.min(r.tE, ZONE_END))
    if (y0 == null || y1 == null) continue
    rows[i].y = y0
    rows[i].h = Math.max(BLOCK_MIN_SEG_H, y1 - y0)
  }

  const newEndY = yearY(ZONE_END) ?? (rows[lastIdx].y + rows[lastIdx].h)
  const delta = newEndY - oldEndY
  for (let i = lastIdx + 1; i < rows.length; i++) {
    rows[i].y += delta
  }
  return { delta, oldEndY }
}

function repositionSongZoneRightContainers(blocks, rows, exp) {
  const showLiaoContainer = isWudaiExpanded(exp) || isSongExpanded(exp)
  const showJinContainer = isSongExpanded(exp)
  const liaoSpan = yearBlockSpan(rows, ZONE_START, LIAO_END)
  const jinSpan = yearBlockSpan(rows, JIN_START, JIN_END)

  blocks.forEach(b => {
    if (b.entryId === LIAO_CONTAINER && showLiaoContainer && liaoSpan) {
      b.top = liaoSpan.top
      b.h = liaoSpan.h
    }
    if (b.entryId === JIN_CONTAINER && showJinContainer && jinSpan) {
      b.top = jinSpan.top
      b.h = jinSpan.h
    }
  })
}

function repositionYuanContainerBlock(blocks, rows, exp) {
  if (!isYuanContainerActive(exp)) return
  const span = yearBlockSpan(rows, YUAN_CONTAINER_START, YUAN_CONTAINER_END)
  if (!span) return
  blocks.forEach(b => {
    if (b.entryId !== YUAN_CONTAINER) return
    b.top = span.top
    b.h = Math.round(span.h)
  })
}

function shiftPostSongZoneBlocks(blocks, delta, oldEndY) {
  if (!delta || !Number.isFinite(oldEndY)) return
  const skipIds = new Set([YUAN_CONTAINER, LIAO_CONTAINER, JIN_CONTAINER])
  blocks.forEach(b => {
    if (skipIds.has(b.entryId)) return
    if (b.top >= oldEndY - 1) {
      b.top += delta
    }
  })
}

function shiftPostSongZoneOverlays(overlays, blocks, delta, oldEndY) {
  if (!delta || !overlays || !overlays.length || !Number.isFinite(oldEndY)) return
  const skipIds = new Set([YUAN_CONTAINER, LIAO_CONTAINER, JIN_CONTAINER])
  const shiftedIds = new Set(
    blocks
      .filter(b => !skipIds.has(b.entryId) && b.top >= oldEndY - 1 + delta)
      .map(b => b.entryId)
  )
  overlays.forEach(ov => {
    if (!shiftedIds.has(ov.entryId)) return
    if (ov.headerTop != null) ov.headerTop += delta
    if (ov.barTop != null) ov.barTop += delta
  })
}

function isMingZoneBlock(b) {
  if (!b || isBridgeBlock(b)) return false
  if (b.entryId === MING_ENTRY) return true
  return b.dynasty === '明' && b.kind === 'single'
}

function collectMingZoneBlocks(blocks) {
  return blocks.filter(isMingZoneBlock).sort((a, b) => a.top - b.top)
}

/**
 * 收起态：按实际卡片堆叠位置收集年份锚点，压缩 907–1279 多余行高
 */
function collectSongCollapsedYearAnchors(blocks) {
  const anchors = []
  const add = (year, y) => {
    if (!Number.isFinite(year) || !Number.isFinite(y)) return
    anchors.push({ year, y })
  }

  const wudai = findBlockBase(blocks, WUDAI_COLLAPSED) || findBlockBase(blocks, WUDAI_CONTAINER)
  const beisong = findBlockBase(blocks, BEISONG_ENTRY)
  const nansong = findBlockBase(blocks, NANSONG_ENTRY)
  const yuan = findBlockBase(blocks, YUAN_ENTRY)

  if (wudai) add(ZONE_START, wudai.top)
  if (beisong) add(WUDAI_LAYOUT_END, beisong.top)
  if (nansong) add(BEISONG_END, nansong.top)
  if (yuan) {
    add(YUAN_AXIS, yuan.top)
    add(ZONE_END, yuan.top + yuan.h)
  } else if (nansong) {
    add(ZONE_END, nansong.top + nansong.h)
  }

  return normalizeYearAnchors(anchors)
}

function repositionCollapsedSongZoneRight(blocks, exp, ctx) {
  if (isSongExpanded(exp)) return

  const CARD_H = ctx && ctx.collapsedDynastyCardH != null
    ? ctx.collapsedDynastyCardH
    : COLLAPSED_DYNASTY_CARD_H_RPX
  const rightGeom = calcRightHalfGeom()
  const showLiao = isWudaiExpanded(exp) || isSongExpanded(exp)

  const wudai = findBlockBase(blocks, WUDAI_COLLAPSED) || findBlockBase(blocks, WUDAI_CONTAINER)
  const beisong = findBlockBase(blocks, BEISONG_ENTRY)
  const nansong = findBlockBase(blocks, NANSONG_ENTRY)
  const jin = findBlockBase(blocks, JIN_ENTRY)
  const liao = findBlockBase(blocks, LIAO_CONTAINER)

  const zoneTop = wudai ? wudai.top : (beisong ? beisong.top : null)
  const beisongBottom = beisong ? beisong.top + beisong.h : null

  if (showLiao && liao && zoneTop != null && beisongBottom != null) {
    liao.top = zoneTop
    liao.h = Math.max(BLOCK_MIN_SEG_H, beisongBottom - zoneTop)
    liao.leftPct = rightGeom.leftPct
    liao.widthPct = rightGeom.widthPct
  }

  if (jin && nansong) {
    jin.top = nansong.top
    jin.h = CARD_H
    jin.leftPct = rightGeom.leftPct
    jin.widthPct = rightGeom.widthPct
  }
}

function syncCollapsedSongLiaoJinTimeline(rows, blocks, overlays, exp, ctx) {
  if (isSongExpanded(exp) || !rows || !blocks) return 0

  repositionCollapsedSongZoneRight(blocks, exp, ctx)

  const anchors = collectSongCollapsedYearAnchors(blocks)
  if (!anchors || anchors.length < 2) return 0

  const remap = remapSongExpandedTimelineRows(rows, anchors) || {}
  const delta = remap.delta || 0
  const oldEndY = remap.oldEndY
  if (!delta) return 0

  repositionCollapsedSongZoneRight(blocks, exp, ctx)
  shiftPostSongZoneBlocks(blocks, delta, oldEndY)
  shiftPostSongZoneOverlays(overlays, blocks, delta, oldEndY)
  return Math.abs(delta)
}

/**
 * 元收起态（无容器）：压缩 1271–1368 多余行高，使明（收起卡或展开帝王）紧贴元卡片
 */
function syncCollapsedYuanMingTimeline(rows, blocks, overlays, exp, ctx) {
  if (isYuanContainerActive(exp) || !rows || !rows.length) return 0

  const GAP = ctx && ctx.collapsedDynastyGapRpx != null
    ? ctx.collapsedDynastyGapRpx
    : BLOCK_V_GAP_RPX
  const yuan = blocks.find(b => b.entryId === YUAN_ENTRY && !isBridgeBlock(b))
  const mingZoneBlocks = collectMingZoneBlocks(blocks)
  const mingFirst = mingZoneBlocks[0]
  if (!yuan || !mingFirst) return 0

  const targetMingTop = yuan.top + yuan.h + GAP
  const delta = Math.round(mingFirst.top - targetMingTop)
  if (delta <= 1) return 0

  const mingRowIdx = rows.findIndex(r => r.tS === 1368)
  if (mingRowIdx <= 0) return 0

  const row1260Idx = rows.findIndex(r => r.tS === YUAN_AXIS)
  const trimFromIdx = row1260Idx >= 0 ? row1260Idx + 1 : rows.findIndex(r => r.tS >= 1271)
  if (trimFromIdx < 1 || trimFromIdx >= mingRowIdx) return 0

  let remaining = delta
  for (let i = trimFromIdx; i < mingRowIdx && remaining > 0; i++) {
    const cut = Math.min(rows[i].h, remaining)
    rows[i].h -= cut
    remaining -= cut
  }

  let y = rows[trimFromIdx - 1].y + rows[trimFromIdx - 1].h
  for (let i = trimFromIdx; i < rows.length; i++) {
    rows[i].y = y
    y += rows[i].h
  }

  const shiftBoundary = mingFirst.top
  const mingOffsets = mingZoneBlocks.map(b => b.top - mingFirst.top)
  const mingEntryIds = new Set(mingZoneBlocks.map(b => b.entryId))

  blocks.forEach(b => {
    if (isBridgeBlock(b)) return
    if (b.entryId === YUAN_ENTRY || mingEntryIds.has(b.entryId)) return
    if (b.top >= shiftBoundary - 1) b.top -= delta
  })

  mingZoneBlocks.forEach((b, i) => {
    b.top = targetMingTop + mingOffsets[i]
  })

  if (overlays && overlays.length) {
    overlays.forEach(ov => {
      if (ov.headerTop == null || ov.headerTop < shiftBoundary - 1) return
      ov.headerTop -= delta
      if (ov.barTop != null && ov.barTop >= shiftBoundary - 1) ov.barTop -= delta
    })
  }

  return delta
}

function repositionYuanStack(blocks, rows, exp, ctx) {
  if (!isYuanExpanded(exp) || isYuanContainerActive(exp)) return
  const y1271 = yearTop(rows, YUAN_AXIS)
  if (y1271 == null) return
  const rightGeom = calcRightHalfGeom()
  const GAP = ctx && ctx.collapsedDynastyGapRpx != null
    ? ctx.collapsedDynastyGapRpx
    : BLOCK_V_GAP_RPX
  const stacked = stackDynastyEmperors(blocks, '元', rightGeom, y1271, GAP)
  stacked.rects.forEach(rect => {
    const existing = blocks.find(b =>
      b.entryId === rect.entryId && b.dynasty === '元' && !isBridgeBlock(b)
    )
    if (!existing) return
    existing.top = rect.top
    existing.h = rect.h
    existing.leftPct = rect.leftPct
    existing.widthPct = rect.widthPct
  })
}

/**
 * 宋展开态：左通道帝王为堆叠布局，需将时间轴行高重映射到实际卡片位置
 */
function syncSongExpandedTimeline(rows, blocks, exp, ctx, overlays) {
  if (!isSongExpanded(exp) || !rows || !blocks) return
  const anchors = collectSongExpandedYearAnchors(blocks)
  const remap = remapSongExpandedTimelineRows(rows, anchors) || {}
  const delta = remap.delta || 0
  const oldEndY = remap.oldEndY
  repositionSongZoneRightContainers(blocks, rows, exp)
  repositionYuanContainerBlock(blocks, rows, exp)
  shiftPostSongZoneBlocks(blocks, delta, oldEndY)
  shiftPostSongZoneOverlays(overlays, blocks, delta, oldEndY)
  repositionYuanStack(blocks, rows, exp, ctx)
}

module.exports = {
  ZONE_START,
  ZONE_END,
  WUDAI_LAYOUT_END,
  BEISONG_END,
  LIAO_END,
  JIN_START,
  JIN_END,
  YUAN_AXIS,
  YUAN_CONTAINER_START,
  YUAN_CONTAINER_END,
  SONG_REGIMES,
  SONG_AXIS_KEY,
  SONG_CONTROLLED_KEYS,
  SONG_LINKED_AXIS_KEYS,
  isSongLinkedAxisKey,
  applySongLinkedExpansion,
  WUDAI_FIVE_REGIMES,
  TEN_KINGDOM_KEYS,
  HIDDEN_DYNASTIES,
  isInSongLiaoJinZone,
  calcLeftHalfGeom,
  calcRightHalfGeom,
  isSongEntry,
  isYuanEntry,
  isWudaiEntry,
  isLiaoEntry,
  isJinEntry,
  isLeftChannelEntry,
  isRightChannelEntry,
  isWudaiFiveRegime,
  isWudaiContainerColumn,
  isWudaiExpanded,
  isSongExpanded,
  isBeisongExpanded,
  isNansongExpanded,
  isYuanExpanded,
  isYuanContainerActive,
  isYuanEmperorsVisible,
  isYuanContainerSpanEntry,
  isLeftChannelExpanded,
  shouldShowLiaoContainer,
  shouldShowJinContainer,
  shouldShowYuanOnRight,
  isLiaoContainerActive,
  isLiaoEmperorsVisible,
  isJinContainerActive,
  isJinEmperorsVisible,
  filterHiddenDynasties,
  filterActiveForSongLiaoJin,
  assignSongLiaoJinPlacements,
  buildTenKingdomRegimeEntries,
  buildCollapsedWudaiEntry,
  applySongLiaoJinRectLayout,
  syncSongExpandedTimeline,
  syncCollapsedSongLiaoJinTimeline,
  syncCollapsedYuanMingTimeline,
  repositionYuanContainerBlock,
  shiftPostSongZoneBlocks,
  shiftPostSongZoneOverlays,
  BLOCK_V_GAP_RPX,
  BLOCK_MIN_SEG_H,
  COLLAPSED_DYNASTY_CARD_H_RPX,
}
