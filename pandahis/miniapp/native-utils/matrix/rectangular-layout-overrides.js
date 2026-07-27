/**
 * 首页矩阵：将 L 形/阶梯形卡片统一为矩形（允许重叠，靠 zIndex 控制层级）。
 */

const BLOCK_H_GAP_PCT = 3.2
const BLOCK_RADIUS_RPX = 12
const BLOCK_MIN_SEG_H = 20

const SHILIUGUO_ENTRY = 'merged_十六国'
const NANBEI_ENTRY = 'merged_南北朝'
const XIJIN_DYNASTY_ENTRY = 'ZQ_HX_XIJIN_XIJIN'
const DONGJIN_DYNASTY_ENTRY = 'ZQ_HX_DONGJIN_DONGJIN'
const SANGUO_ENTRY = 'collapsed_三国'
const DONGHAN_ENTRY = 'ZQ_HX_DONGHAN_DONGHAN'
const LIANGJIN_COLLAPSED_V_GAP_RPX = 16
const DEFAULT_COLLAPSED_DYNASTY_CARD_H_RPX = 200
const JIN_PARALLEL_START = 307

const JIN_WUDI_REFS = ['zhong_hua_jin_si_ma_yan', 'DW_HX_XIJIN_XIJIN_JINWUDI']
const JIN_HUIDI_REFS = ['zhong_hua_jin_si_ma_zhong', 'DW_HX_XIJIN_XIJIN_JINHUIDI']
const JIN_HUAIDI_REFS = ['DW_HX_XIJIN_XIJIN_JINHUAIDI']
const JIN_WUDI_REIGN_YEARS = 24
const JIN_XIAOWUDI_REFS = ['zhong_hua_jin_si_ma_yao', 'DW_HX_DONGJIN_DONGJIN_JINXIAOWUDI']
const JIN_ANDI_REFS = ['zhong_hua_jin_si_ma_de_zong', 'DW_HX_DONGJIN_DONGJIN_JINANDI']
const JIN_GONGDI_REFS = ['zhong_hua_jin_si_ma_de_wen']
const SUI_WENDI_REFS = ['zhong_hua_sui_wen_di', 'DW_HX_SUI_SUI_SUIWENDI']
const SUI_YANGDI_REFS = ['zhong_hua_sui_yang_di', 'DW_HX_SUI_SUI_SUIYANGDI']
const SUI_DYNASTY_REFS = ['ZQ_HX_SUI_SUI']
const TANG_AIDI_REFS = ['zhong_hua_tang_ai_di', 'DW_HX_TANG_TANG_TANGAIDI']
const SONG_TAIZU_REFS = ['DW_HX_BEISONG_BEISONG_SONGTAIZU']
const SONG_TAIZONG_REFS = ['DW_HX_BEISONG_BEISONG_SONGTAIZONG']

const songLiaoJin = require('./song-liao-jin-layout.js')
const mingQing = require('./ming-qing-layout.js')

const JIN_TAIZU_REFS = ['DW_HX_JIN_JIN_JINTAIZU']
const JIN_TAIZONG_REFS = ['DW_HX_JIN_JIN_JINTAIZONG']
const LIAO_TIANZUO_REFS = ['DW_HX_LIAO_LIAO_LIAOTIANZUODI']
const YUAN_SHIZU_REFS = ['DW_HX_YUAN_YUAN_YUANSHIZU', 'zhong_hua_yuan_hu_lie']

/** 宋徽宗（1100）起拓宽至左半 */
const SONG_FROM_HUIZONG_NAMES = new Set([
  '宋徽宗', '宋钦宗', '宋高宗', '宋孝宗', '宋光宗', '宋宁宗',
  '宋理宗', '宋度宗', '宋恭帝', '宋端宗', '宋少帝',
])

const Z_BELOW = 2
const Z_MID = 5
const Z_ABOVE = 8
const Z_TOP = 12
/** 文字层 = 色块 zIndex + 偏移，须严格大于 era-block 最大值 12 */
const Z_CHROME_OFFSET = 20

const EMP_CARD_H_MIN_RPX = 80
const EMP_CARD_H_MAX_RPX = 200
const EMP_CARD_REF_YEARS = 71

function calcEmperorCardHeight(years) {
  const y = Math.max(1, Math.min(Number(years) || 1, EMP_CARD_REF_YEARS))
  const span = EMP_CARD_H_MAX_RPX - EMP_CARD_H_MIN_RPX
  return Math.max(
    EMP_CARD_H_MIN_RPX,
    Math.min(EMP_CARD_H_MAX_RPX, Math.round(EMP_CARD_H_MIN_RPX + (y / EMP_CARD_REF_YEARS) * span))
  )
}

function isBridgeBlock(b) {
  return !!(b.isLBridge || b.isNanbeiLBridge || b.isSongHalfLBridge || b.isXiaowudiBridge)
}

function yearTop(rows, year) {
  const row = rows.find(r => r.tS === year)
  return row != null ? row.y : null
}

/** 有华夏轴标（如 317 东晋）的行顶 y，用于展开态帝王卡与刻度齐线 */
function axisMarkRowTop(rows, year) {
  const row = rows.find(r => r.tS === year && r.hxLabel)
  return row != null ? row.y : null
}

function yearEndY(rows, year) {
  const row = rows.find(r => r.tE === year)
  if (row) return row.y
  const startRow = rows.find(r => r.tS === year)
  return startRow ? startRow.y + startRow.h : null
}

/** 某年历史时间带的底边 y（用于帝王卡贴合时间轴） */
function yearSpanBottom(rows, year) {
  const row = rows.find(r => r.tE === year)
  if (row) return row.y + row.h
  const containing = rows.find(r => r.tS <= year && r.tE > year)
  return containing ? containing.y + containing.h : null
}

function calcLeftHalf() {
  const half = (100 - BLOCK_H_GAP_PCT) / 2
  return { leftPct: 0, widthPct: half }
}

function calcRightHalf() {
  const half = (100 - BLOCK_H_GAP_PCT) / 2
  return { leftPct: half + BLOCK_H_GAP_PCT, widthPct: half }
}

function calcRightThird() {
  const usable = 100 - BLOCK_H_GAP_PCT
  const leftW = usable * 2 / 3
  const rightW = usable / 3
  return { leftPct: leftW + BLOCK_H_GAP_PCT, widthPct: rightW }
}

function calcJinTwoThirdsWidth() {
  return (100 - BLOCK_H_GAP_PCT) * 2 / 3
}

function fullRadiusStyle() {
  const R = BLOCK_RADIUS_RPX
  return `${R}rpx ${R}rpx ${R}rpx ${R}rpx`
}

function realSegs(blocks, matchFn) {
  return blocks.filter(b => matchFn(b) && !isBridgeBlock(b))
}

function segBounds(segs) {
  if (!segs.length) return null
  return {
    top: Math.min(...segs.map(s => s.top)),
    bottom: Math.max(...segs.map(s => s.top + s.h)),
  }
}

function replaceEntryWithRect(blocks, matchFn, geom, zIndex = Z_MID) {
  const segs = blocks.filter(b => matchFn(b))
  if (!segs.length) return blocks

  const base = segs.find(b => !isBridgeBlock(b)) || segs[0]
  const real = segs.filter(b => !isBridgeBlock(b))
  const bounds = segBounds(real)
  if (!bounds) return blocks.filter(b => !segs.some(s => s.id === b.id))

  const top = geom.top != null ? geom.top : bounds.top
  const bottom = geom.bottom != null ? geom.bottom : bounds.bottom
  const leftPct = geom.leftPct != null ? geom.leftPct : Math.min(...real.map(s => s.leftPct))
  const widthPct = geom.widthPct != null ? geom.widthPct : (
    Math.max(...real.map(s => s.leftPct + s.widthPct)) - leftPct
  )

  const removeIds = new Set(segs.map(s => s.id))
  const rect = Object.assign({}, base, {
    id:            `${base.entryId}_rect`,
    top,
    h:             Math.max(BLOCK_MIN_SEG_H, bottom - top),
    leftPct,
    widthPct,
    zIndex,
    rTL: true,
    rTR: true,
    rBR: true,
    rBL: true,
    radiusStyle:   fullRadiusStyle(),
    edgeClass:     '',
    edgeTop:       false,
    edgeRight:     false,
    edgeBottom:    false,
    edgeLeft:      false,
    fillSeamFix:   false,
    isLBridge:     false,
    isNanbeiLBridge: false,
    isSongHalfLBridge: false,
    isXiaowudiBridge: false,
  })

  return blocks.filter(b => !removeIds.has(b.id)).concat(rect)
}

function setZIndex(blocks, matchFn, zIndex) {
  blocks.forEach(b => {
    if (matchFn(b)) b.zIndex = zIndex
  })
  return blocks
}

function matchAnyRef(entryId, refs, entryIdsMatch) {
  return refs.some(ref => entryIdsMatch(entryId, ref))
}

function rebuildOverlays(blocks, ctx) {
  const byEntry = {}
  blocks.forEach(b => {
    if (b.isDynastyContainer || isBridgeBlock(b)) return
    if (!byEntry[b.entryId]) byEntry[b.entryId] = []
    byEntry[b.entryId].push(b)
  })

  const overlays = []
  Object.keys(byEntry).forEach(entryId => {
    if (String(entryId).startsWith('container_span_')) return
    const segs = byEntry[entryId].sort((a, b) => a.top - b.top)
    const chrome = ctx.finalizeEntryShape(segs)
    if (chrome) {
      const blockZ = Math.max(...segs.map(s => s.zIndex || Z_MID))
      chrome.zIndex = blockZ + Z_CHROME_OFFSET
      overlays.push(chrome)
    }
  })
  return overlays
}

/**
 * @param {object[]} blocks
 * @param {object[]} overlays
 * @param {object[]} rows
 * @param {object} ctx - { entryIdsMatch, isIrregularEntryShape, finalizeEntryShape }
 */
function applyRectangularLayoutOverrides(blocks, overlays, rows, ctx) {
  const { entryIdsMatch, isIrregularEntryShape, finalizeEntryShape } = ctx
  let next = blocks.filter(b => !isBridgeBlock(b))

  const matchRef = (refs) => (b) => matchAnyRef(b.entryId, refs, entryIdsMatch)
  const matchEntry = (ref) => (b) => entryIdsMatch(b.entryId, ref)
  const matchShiliuguo = matchEntry(SHILIUGUO_ENTRY)
  const matchNanbei = matchEntry(NANBEI_ENTRY)

  const y266 = yearTop(rows, 266)
  const y307 = yearTop(rows, 307)
  const y420 = yearTop(rows, 420)
  const y589 = yearEndY(rows, 589)
  const rightThird = calcRightThird()
  const jinWidth = calcJinTwoThirdsWidth()

  if (ctx.liangjinExpanded) {
    next = applyLiangjinExpandedLayout(next, rows)
  } else {
  // ① 晋武帝：按在位年数定高，避免与收起态「三国」并列时行高被撑大
  if (y266 != null) {
    const wudiH = calcEmperorCardHeight(JIN_WUDI_REIGN_YEARS)
    next = replaceEntryWithRect(next, matchRef(JIN_WUDI_REFS), {
      top: y266,
      bottom: y266 + wudiH,
      leftPct: 0,
      widthPct: 100,
    }, Z_MID)
  }

  // ② 晋怀帝：307 年起全宽，与十六国顶缘齐平
  if (y307 != null) {
    const huaidiBottom = yearSpanBottom(rows, 313)
    next = replaceEntryWithRect(next, matchRef(JIN_HUAIDI_REFS), {
      top: y307,
      bottom: huaidiBottom != null ? huaidiBottom : undefined,
      leftPct: 0,
      widthPct: 100,
    }, Z_MID)
  }

  // ③ 十六国：307 年起、420 线止，右 1/3 矩形（与晋怀帝同一水平线）
  if (y307 != null && y420 != null) {
    const huaidiSegs = realSegs(next, matchRef(JIN_HUAIDI_REFS))
    const shiliuguoTop = huaidiSegs.length
      ? Math.min(...huaidiSegs.map(s => s.top))
      : y307
    next = replaceEntryWithRect(next, matchShiliuguo, {
      top: shiliuguoTop,
      bottom: y420,
      leftPct: rightThird.leftPct,
      widthPct: rightThird.widthPct,
    }, Z_BELOW)
  }

  // ④ 晋惠帝：单矩形全宽
  next = replaceEntryWithRect(next, matchRef(JIN_HUIDI_REFS), {
    leftPct: 0,
    widthPct: 100,
  }, Z_MID)

  // ⑤ 晋孝武帝、晋安帝、晋恭帝：统一左列宽度
  next = replaceEntryWithRect(next, matchRef(JIN_XIAOWUDI_REFS), {
    leftPct: 0,
    widthPct: jinWidth,
  }, Z_MID)
  next = replaceEntryWithRect(next, matchRef(JIN_ANDI_REFS), {
    leftPct: 0,
    widthPct: jinWidth,
  }, Z_MID)
  next = replaceEntryWithRect(next, matchRef(JIN_GONGDI_REFS), {
    leftPct: 0,
    widthPct: jinWidth,
  }, Z_MID)
  } // end !liangjinExpanded

  // ⑥ 南北朝整段矩形；隋文帝整段矩形，叠在南北朝之上（双收起态由 syncCollapsedNanbeiSuiTimeline 处理）
  if (!ctx.nanbeiSuiCollapsed) {
    if (y420 != null) {
      const nbBounds = segBounds(realSegs(next, matchNanbei))
      const nbBottom = y589 != null ? y589 : (nbBounds ? nbBounds.bottom : y420)
      next = replaceEntryWithRect(next, matchNanbei, {
        top: y420,
        bottom: nbBottom,
        leftPct: 0,
        widthPct: 100,
      }, Z_BELOW)
    }

    next = replaceEntryWithRect(next, matchRef(SUI_WENDI_REFS), {
      leftPct: 0,
      widthPct: 100,
    }, Z_TOP)
    next = replaceEntryWithRect(next, matchRef(SUI_YANGDI_REFS), {
      leftPct: 0,
      widthPct: 100,
    }, Z_MID)
    next = replaceEntryWithRect(next, matchRef(SUI_DYNASTY_REFS), {
      leftPct: 0,
      widthPct: 100,
    }, Z_MID)
  }

  // ⑥ 唐哀帝：单矩形全宽
  next = replaceEntryWithRect(next, matchRef(TANG_AIDI_REFS), {
    leftPct: 0,
    widthPct: 100,
  }, Z_MID)

  // 其余不规则帝王：合并为全宽矩形（宋辽金元区由双通道布局单独处理）
  const byEntry = {}
  next.forEach(b => {
    if (isBridgeBlock(b)) return
    if (!byEntry[b.entryId]) byEntry[b.entryId] = []
    byEntry[b.entryId].push(b)
  })
  Object.entries(byEntry).forEach(([entryId, segs]) => {
    if (segs[0].kind !== 'single') return
    if (segs[0].isDynastyContainer) return
    if (matchAnyRef(entryId, JIN_WUDI_REFS, entryIdsMatch)) return
    if (matchAnyRef(entryId, JIN_HUIDI_REFS, entryIdsMatch)) return
    if (matchAnyRef(entryId, JIN_HUAIDI_REFS, entryIdsMatch)) return
    if (matchAnyRef(entryId, JIN_XIAOWUDI_REFS, entryIdsMatch)) return
    if (matchAnyRef(entryId, JIN_ANDI_REFS, entryIdsMatch)) return
    if (matchAnyRef(entryId, JIN_GONGDI_REFS, entryIdsMatch)) return
    if (matchAnyRef(entryId, SUI_WENDI_REFS, entryIdsMatch)) return
    if (matchAnyRef(entryId, SUI_YANGDI_REFS, entryIdsMatch)) return
    if (matchAnyRef(entryId, SUI_DYNASTY_REFS, entryIdsMatch)) return
    if (matchAnyRef(entryId, TANG_AIDI_REFS, entryIdsMatch)) return
    if (segs[0].dynasty === '辽') return
    if (segs[0].dynasty === '金') return
    if (segs[0].dynasty === '北宋' || segs[0].dynasty === '南宋' || segs[0].dynasty === '元') return
    if (segs[0].dynasty === '明' || segs[0].dynasty === '清') return
    if (matchAnyRef(entryId, YUAN_SHIZU_REFS, entryIdsMatch)) return
    if (SONG_FROM_HUIZONG_NAMES.has(segs[0].person)) return
    if (!isIrregularEntryShape(segs)) return
    const matchOne = (b) => b.entryId === entryId
    next = replaceEntryWithRect(next, matchOne, {
      leftPct: 0,
      widthPct: 100,
    }, Z_MID)
  })

  // ⑦ 宋辽金元双通道矩形覆盖
  next = songLiaoJin.applySongLiaoJinRectLayout(next, rows, ctx)

  // ⑧ 明清双通道矩形覆盖（左明堆叠 + 清容器）
  next = mingQing.applyMingQingRectLayout(next, rows, ctx)

  // 金太祖/金太宗与辽天祚帝重叠：金在上（仅当碎片化帝王块仍存在时）
  next = setZIndex(next, matchRef(LIAO_TIANZUO_REFS), Z_BELOW)
  next = setZIndex(next, matchRef(JIN_TAIZU_REFS), Z_ABOVE)
  next = setZIndex(next, matchRef(JIN_TAIZONG_REFS), Z_ABOVE)

  if (ctx.liangjinCollapsed) {
    next = applyLiangjinCollapsedDynastyRects(next, rows, ctx)
  }

  next.sort((a, b) => (a.zIndex || Z_MID) - (b.zIndex || Z_MID) || a.top - b.top || a.leftPct - b.leftPct)
  next.forEach(b => {
    if (b.isDynastyContainer) {
      b.zIndex = 3
    } else if (b.zIndex == null) {
      b.zIndex = Z_MID
    }
  })

  const newOverlays = rebuildOverlays(next, { finalizeEntryShape })
  return { blocks: next, overlays: newOverlays }
}

const { parseHistoryYearSpan } = require('../year-format')

function parseBlockYearSpan(block) {
  const span = parseHistoryYearSpan(String(block.timeRange || ''))
  if (span) return span
  const y = block.anchorYear || 0
  return { start: y, end: y }
}

function jinEmperorColumnGeom(startYear, endYear, jinWidth) {
  if (endYear <= JIN_PARALLEL_START) {
    return { leftPct: 0, widthPct: 100 }
  }
  return { leftPct: 0, widthPct: jinWidth }
}

function makeLiangjinEmperorRect(base, geom, top, bottom, zIndex) {
  return Object.assign({}, base, {
    id:            `${base.entryId}_liangjin_rect`,
    top,
    h:             Math.max(BLOCK_MIN_SEG_H, bottom - top),
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

/** 两晋展开：帝王按在位年数定高、纵向 16rpx 等距堆叠；307 起左列帝王 + 右列十六国 */
function applyLiangjinExpandedLayout(blocks, rows) {
  const jinEmperors = blocks.filter(b =>
    (b.dynasty === '西晋' || b.dynasty === '东晋') &&
    b.kind === 'single' &&
    !isBridgeBlock(b)
  )
  if (!jinEmperors.length) return blocks

  const byEntry = {}
  jinEmperors.forEach(b => {
    if (!byEntry[b.entryId]) byEntry[b.entryId] = b
  })

  const ordered = Object.values(byEntry).sort((a, b) =>
    parseBlockYearSpan(a).start - parseBlockYearSpan(b).start
  )

  const rightThird = calcRightThird()
  const jinWidth = calcJinTwoThirdsWidth()
  const y307 = yearTop(rows, JIN_PARALLEL_START)
  const y420 = yearTop(rows, 420)
  const emperorGap = LIANGJIN_COLLAPSED_V_GAP_RPX

  let next = blocks.filter(b => {
    if (isBridgeBlock(b)) return false
    if (b.entryId === SHILIUGUO_ENTRY) return false
    if ((b.dynasty === '西晋' || b.dynasty === '东晋') && b.kind === 'single') return false
    return true
  })

  let stackBottom = null
  ordered.forEach(base => {
    const { start, end } = parseBlockYearSpan(base)
    const reignYears = Math.max(1, end - start)
    const h = calcEmperorCardHeight(reignYears)
    const geom = jinEmperorColumnGeom(start, end, jinWidth)
    let top
    if (stackBottom == null) {
      top = yearTop(rows, start)
      if (top == null) top = 0
    } else {
      top = stackBottom + emperorGap
    }
    const axisTop = axisMarkRowTop(rows, start)
    if (axisTop != null) top = axisTop
    stackBottom = top + h
    next.push(makeLiangjinEmperorRect(base, geom, top, top + h, Z_MID))
  })

  const shiliuBase = blocks.find(b => b.entryId === SHILIUGUO_ENTRY && !isBridgeBlock(b))
  const jinRects = next.filter(b =>
    (b.dynasty === '西晋' || b.dynasty === '东晋') && b.kind === 'single'
  )
  const parallelStartRect = jinRects
    .filter(b => parseBlockYearSpan(b).start >= JIN_PARALLEL_START)
    .sort((a, b) => parseBlockYearSpan(a).start - parseBlockYearSpan(b).start)[0]
  const lastJinRect = jinRects.slice().sort((a, b) => b.top - a.top)[0]
  const shiliuTop = parallelStartRect ? parallelStartRect.top : y307
  const shiliuBottom = lastJinRect
    ? lastJinRect.top + lastJinRect.h
    : (y420 != null ? y420 : shiliuTop + BLOCK_MIN_SEG_H)

  if (shiliuBase && shiliuTop != null && shiliuBottom > shiliuTop) {
    next.push(Object.assign({}, shiliuBase, {
      id:            `${SHILIUGUO_ENTRY}_liangjin_rect`,
      top:           shiliuTop,
      h:             Math.max(BLOCK_MIN_SEG_H, shiliuBottom - shiliuTop),
      leftPct:       rightThird.leftPct,
      widthPct:      rightThird.widthPct,
      zIndex:        Z_BELOW,
      rTL: true, rTR: true, rBR: true, rBL: true,
      radiusStyle:   fullRadiusStyle(),
      edgeClass:     '',
      edgeTop: false, edgeRight: false, edgeBottom: false, edgeLeft: false,
      fillSeamFix:   false,
      isLBridge: false, isNanbeiLBridge: false,
      isSongHalfLBridge: false, isXiaowudiBridge: false,
    }))
  }

  syncLiangjinExpanded317Timeline(next, rows)
  return next
}

const DONGJIN_YUANDI_ENTRY = 'DW_HX_DONGJIN_DONGJIN_JINYUANDI'
const DONGJIN_AXIS_YEAR = 317

function isXijinEmperorBlock(b) {
  return b.dynasty === '西晋' && b.kind === 'single' && !isBridgeBlock(b)
}

/**
 * 两晋展开：317 刻度与晋元帝齐线后，压缩 313–317 间多余行高，
 * 使晋愍帝与晋元帝保持标准 16rpx 间距。
 */
function syncLiangjinExpanded317Timeline(blocks, rows, overlays) {
  const row317Idx = rows.findIndex(r => r.tS === DONGJIN_AXIS_YEAR)
  if (row317Idx < 1) return 0

  const yuandi = blocks.find(b => b.entryId === DONGJIN_YUANDI_ENTRY && !isBridgeBlock(b))
  if (!yuandi) return 0

  const xijinRects = blocks.filter(isXijinEmperorBlock).sort((a, b) => a.top - b.top)
  const lastXijin = xijinRects[xijinRects.length - 1]
  if (!lastXijin) return 0

  const GAP = LIANGJIN_COLLAPSED_V_GAP_RPX
  const oldRow317Y = rows[row317Idx].y
  const targetYuandiTop = lastXijin.top + lastXijin.h + GAP
  const excess = oldRow317Y - targetYuandiTop
  if (excess <= 1) {
    if (Math.abs(yuandi.top - oldRow317Y) > 1) yuandi.top = oldRow317Y
    return 0
  }

  let remaining = excess
  let trimStartIdx = row317Idx
  for (let i = row317Idx - 1; i >= 0 && remaining > 0; i--) {
    const cut = Math.min(rows[i].h, remaining)
    if (cut <= 0) continue
    rows[i].h -= cut
    remaining -= cut
    trimStartIdx = i
  }

  let chainY = trimStartIdx > 0
    ? rows[trimStartIdx - 1].y + rows[trimStartIdx - 1].h
    : rows[trimStartIdx].y
  for (let i = trimStartIdx; i < rows.length; i++) {
    rows[i].y = chainY
    chainY += rows[i].h
  }

  const delta = oldRow317Y - rows[row317Idx].y
  if (delta <= 1) return 0

  const shiftBoundary = oldRow317Y
  blocks.forEach(b => {
    if (isBridgeBlock(b)) return
    if (isXijinEmperorBlock(b)) return
    if (b.top >= shiftBoundary - 1) b.top -= delta
  })

  yuandi.top = rows[row317Idx].y

  const shiliu = blocks.find(b => b.entryId === SHILIUGUO_ENTRY && !isBridgeBlock(b))
  const jinRects = blocks.filter(b =>
    (b.dynasty === '西晋' || b.dynasty === '东晋') && b.kind === 'single' && !isBridgeBlock(b)
  )
  const lastJin = jinRects.slice().sort((a, b) => b.top - a.top)[0]
  if (shiliu && lastJin && lastJin.top + lastJin.h > shiliu.top) {
    shiliu.h = Math.max(BLOCK_MIN_SEG_H, lastJin.top + lastJin.h - shiliu.top)
  }

  if (overlays && overlays.length) {
    overlays.forEach(ov => {
      if (ov.headerTop == null || ov.headerTop < shiftBoundary - 1) return
      const ovBlock = blocks.find(b => b.entryId === ov.entryId)
      if (ovBlock && isXijinEmperorBlock(ovBlock)) return
      ov.headerTop -= delta
      if (ov.barTop != null && ov.barTop >= shiftBoundary - 1) ov.barTop -= delta
    })
  }

  return delta
}

/** 收起态朝代卡：与下方卡片保持固定间距，必要时上移（不超出本段行顶） */
function nudgeCollapsedCardAbove(next, entryId, lowerTop, cardH, gap, rows, eraStartYear) {
  const card = next.find(b => b.entryId === entryId && !isBridgeBlock(b))
  if (!card) return false
  const alignedTop = lowerTop - gap - cardH
  const row = eraStartYear != null ? rows.find(r => r.tS === eraStartYear) : null
  const minTop = row ? row.y : alignedTop
  if (alignedTop >= card.top - 0.5) return false
  card.top = Math.max(minTop, alignedTop)
  return true
}

/** 两晋收起：西晋 + 东晋各一张全宽固定高度朝代卡，间距与其余朝代卡一致 */
function applyLiangjinCollapsedDynastyRects(blocks, rows, ctx) {
  const matchXijin = (b) => b.entryId === XIJIN_DYNASTY_ENTRY && !isBridgeBlock(b)
  const matchDongjin = (b) => b.entryId === DONGJIN_DYNASTY_ENTRY && !isBridgeBlock(b)
  const xijinBase = blocks.find(matchXijin)
  const dongjinBase = blocks.find(matchDongjin)
  if (!xijinBase || !dongjinBase) return blocks

  const CARD_H = ctx.collapsedDynastyCardH || DEFAULT_COLLAPSED_DYNASTY_CARD_H_RPX
  const GAP = ctx.collapsedDynastyGapRpx || LIANGJIN_COLLAPSED_V_GAP_RPX
  const radiusStyle = fullRadiusStyle()

  const nanbeiRow = rows.find(r => r.tS === 420)
  const dongjinRow = rows.find(r => r.tS === 317)
  let dongjinTop = dongjinRow
    ? dongjinRow.y + Math.max(0, Math.round((dongjinRow.h - CARD_H) / 2))
    : yearTop(rows, 317)
  if (nanbeiRow) {
    dongjinTop = Math.min(dongjinTop, nanbeiRow.y - GAP - CARD_H)
  }
  const xijinTop = dongjinTop - GAP - CARD_H

  const next = blocks.filter(b => {
    if (matchXijin(b) || matchDongjin(b)) return false
    return true
  })

  const sanguoMoved = nudgeCollapsedCardAbove(
    next, SANGUO_ENTRY, xijinTop, CARD_H, GAP, rows, 220
  )
  if (sanguoMoved) {
    const sanguoCard = next.find(b => b.entryId === SANGUO_ENTRY && !isBridgeBlock(b))
    if (sanguoCard) {
      nudgeCollapsedCardAbove(
        next, DONGHAN_ENTRY, sanguoCard.top, CARD_H, GAP, rows, 25
      )
    }
  }

  const makeCard = (base, entryId, top) => Object.assign({}, base, {
    id:            `${entryId}_collapsed_rect`,
    entryId,
    top,
    h:             CARD_H,
    leftPct:       0,
    widthPct:      100,
    zIndex:        Z_MID,
    rTL: true, rTR: true, rBR: true, rBL: true,
    radiusStyle,
    edgeClass:     '',
    edgeTop: false, edgeRight: false, edgeBottom: false, edgeLeft: false,
    fillSeamFix:   false,
    isLBridge: false, isNanbeiLBridge: false,
    isSongHalfLBridge: false, isXiaowudiBridge: false,
  })

  next.push(makeCard(xijinBase, XIJIN_DYNASTY_ENTRY, xijinTop))
  next.push(makeCard(dongjinBase, DONGJIN_DYNASTY_ENTRY, dongjinTop))

  return next
}

module.exports = {
  applyRectangularLayoutOverrides,
  syncLiangjinExpanded317Timeline,
}
