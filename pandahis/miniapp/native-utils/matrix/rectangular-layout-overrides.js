/**
 * 首页矩阵：将 L 形/阶梯形卡片统一为矩形（允许重叠，靠 zIndex 控制层级）。
 */

const BLOCK_H_GAP_PCT = 3.2
const BLOCK_RADIUS_RPX = 12
const BLOCK_MIN_SEG_H = 20

const SHILIUGUO_ENTRY = 'merged_十六国'
const NANBEI_ENTRY = 'merged_南北朝'
const WUDAI_ENTRY = 'merged_五代十国'

const JIN_WUDI_REFS = ['zhong_hua_jin_si_ma_yan', 'DW_HX_XIJIN_XIJIN_JINWUDI']
const JIN_HUIDI_REFS = ['zhong_hua_jin_si_ma_zhong', 'DW_HX_XIJIN_XIJIN_JINHUIDI']
const JIN_XIAOWUDI_REFS = ['zhong_hua_jin_si_ma_yao', 'DW_HX_DONGJIN_DONGJIN_JINXIAOWUDI']
const JIN_ANDI_REFS = ['zhong_hua_jin_si_ma_de_zong', 'DW_HX_DONGJIN_DONGJIN_JINANDI']
const JIN_GONGDI_REFS = ['zhong_hua_jin_si_ma_de_wen']
const SUI_WENDI_REFS = ['zhong_hua_sui_wen_di', 'DW_HX_SUI_SUI_SUIWENDI']
const SUI_YANGDI_REFS = ['zhong_hua_sui_yang_di', 'DW_HX_SUI_SUI_SUIYANGDI']
const SUI_DYNASTY_REFS = ['ZQ_HX_SUI_SUI']
const TANG_AIDI_REFS = ['zhong_hua_tang_ai_di', 'DW_HX_TANG_TANG_TANGAIDI']
const SONG_TAIZU_REFS = ['DW_HX_BEISONG_BEISONG_SONGTAIZU']
const SONG_TAIZONG_REFS = ['DW_HX_BEISONG_BEISONG_SONGTAIZONG']

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

function isBridgeBlock(b) {
  return !!(b.isLBridge || b.isNanbeiLBridge || b.isSongHalfLBridge || b.isXiaowudiBridge)
}

function yearTop(rows, year) {
  const row = rows.find(r => r.tS === year)
  return row != null ? row.y : null
}

function yearEndY(rows, year) {
  const row = rows.find(r => r.tE === year)
  if (row) return row.y
  const startRow = rows.find(r => r.tS === year)
  return startRow ? startRow.y + startRow.h : null
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
  const matchWudai = matchEntry(WUDAI_ENTRY)
  const matchLiao = (b) => b.dynasty === '辽' && b.kind === 'single'
  const matchJin = (b) => b.dynasty === '金' && b.kind === 'single'
  const matchSongFromHuizong = (b) =>
    b.kind === 'single' &&
    (b.dynasty === '北宋' || b.dynasty === '南宋') &&
    SONG_FROM_HUIZONG_NAMES.has(b.person)

  const y307 = yearTop(rows, 307)
  const y420 = yearTop(rows, 420)
  const y589 = yearEndY(rows, 589)
  const rightThird = calcRightThird()
  const leftHalf = calcLeftHalf()
  const rightHalf = calcRightHalf()
  const jinWidth = calcJinTwoThirdsWidth()

  // ① 晋武帝：单矩形全宽
  next = replaceEntryWithRect(next, matchRef(JIN_WUDI_REFS), {
    leftPct: 0,
    widthPct: 100,
  }, Z_MID)

  // ② 十六国：307 年起、420 线止，右 1/3 矩形（时间轴 304 标签不变）
  if (y307 != null && y420 != null) {
    next = replaceEntryWithRect(next, matchShiliuguo, {
      top: y307,
      bottom: y420,
      leftPct: rightThird.leftPct,
      widthPct: rightThird.widthPct,
    }, Z_BELOW)
  }

  // ③ 晋惠帝：单矩形全宽
  next = replaceEntryWithRect(next, matchRef(JIN_HUIDI_REFS), {
    leftPct: 0,
    widthPct: 100,
  }, Z_MID)

  // ④ 晋孝武帝、晋安帝、晋恭帝：统一左列宽度
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

  // ⑤ 南北朝整段矩形；隋文帝整段矩形，叠在南北朝之上
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

  // ⑥ 唐哀帝：单矩形全宽
  next = replaceEntryWithRect(next, matchRef(TANG_AIDI_REFS), {
    leftPct: 0,
    widthPct: 100,
  }, Z_MID)

  // ⑦ 五代十国左半；宋太祖/宋太宗在上层
  next = replaceEntryWithRect(next, matchWudai, {
    leftPct: leftHalf.leftPct,
    widthPct: leftHalf.widthPct,
  }, Z_BELOW)
  next = setZIndex(next, matchRef(SONG_TAIZU_REFS), Z_ABOVE)
  next = setZIndex(next, matchRef(SONG_TAIZONG_REFS), Z_ABOVE)

  // ⑧ 辽朝帝王：右半矩形
  const liaoByEntry = {}
  next.filter(matchLiao).forEach(b => {
    if (!liaoByEntry[b.entryId]) liaoByEntry[b.entryId] = []
    liaoByEntry[b.entryId].push(b)
  })
  Object.keys(liaoByEntry).forEach(entryId => {
    const matchOne = (b) => b.entryId === entryId
    next = replaceEntryWithRect(next, matchOne, {
      leftPct: rightHalf.leftPct,
      widthPct: rightHalf.widthPct,
    }, Z_MID)
  })

  // 其余不规则帝王：合并为全宽矩形
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
    if (matchAnyRef(entryId, JIN_XIAOWUDI_REFS, entryIdsMatch)) return
    if (matchAnyRef(entryId, JIN_ANDI_REFS, entryIdsMatch)) return
    if (matchAnyRef(entryId, JIN_GONGDI_REFS, entryIdsMatch)) return
    if (matchAnyRef(entryId, SUI_WENDI_REFS, entryIdsMatch)) return
    if (matchAnyRef(entryId, SUI_YANGDI_REFS, entryIdsMatch)) return
    if (matchAnyRef(entryId, SUI_DYNASTY_REFS, entryIdsMatch)) return
    if (matchAnyRef(entryId, TANG_AIDI_REFS, entryIdsMatch)) return
    if (segs[0].dynasty === '辽') return
    if (segs[0].dynasty === '金') return
    if (matchAnyRef(entryId, YUAN_SHIZU_REFS, entryIdsMatch)) return
    if (SONG_FROM_HUIZONG_NAMES.has(segs[0].person)) return
    if (!isIrregularEntryShape(segs)) return
    const matchOne = (b) => b.entryId === entryId
    next = replaceEntryWithRect(next, matchOne, {
      leftPct: 0,
      widthPct: 100,
    }, Z_MID)
  })

  // ⑨ 金朝帝王：右半矩形
  const jinByEntry = {}
  next.filter(matchJin).forEach(b => {
    if (!jinByEntry[b.entryId]) jinByEntry[b.entryId] = []
    jinByEntry[b.entryId].push(b)
  })
  Object.keys(jinByEntry).forEach(entryId => {
    const matchOne = (b) => b.entryId === entryId
    next = replaceEntryWithRect(next, matchOne, {
      leftPct: rightHalf.leftPct,
      widthPct: rightHalf.widthPct,
    }, Z_MID)
  })

  // ⑩ 宋徽宗起：左半矩形
  const songHzByEntry = {}
  next.filter(matchSongFromHuizong).forEach(b => {
    if (!songHzByEntry[b.entryId]) songHzByEntry[b.entryId] = []
    songHzByEntry[b.entryId].push(b)
  })
  Object.keys(songHzByEntry).forEach(entryId => {
    const matchOne = (b) => b.entryId === entryId
    next = replaceEntryWithRect(next, matchOne, {
      leftPct: leftHalf.leftPct,
      widthPct: leftHalf.widthPct,
    }, Z_MID)
  })

  // ⑪ 元世祖：右半矩形
  next = replaceEntryWithRect(next, matchRef(YUAN_SHIZU_REFS), {
    leftPct: rightHalf.leftPct,
    widthPct: rightHalf.widthPct,
  }, Z_MID)

  // 金太祖/金太宗与辽天祚帝重叠：金在上
  next = setZIndex(next, matchRef(LIAO_TIANZUO_REFS), Z_BELOW)
  next = setZIndex(next, matchRef(JIN_TAIZU_REFS), Z_ABOVE)
  next = setZIndex(next, matchRef(JIN_TAIZONG_REFS), Z_ABOVE)

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

module.exports = {
  applyRectangularLayoutOverrides,
}
