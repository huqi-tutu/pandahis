/**
 * 西周 / 春秋 / 战国 特殊布局
 * - 西周：仅西周帝王/政权
 * - 春秋战国：固定 8 单位列栅，政权级色块（不收展帝王）
 */

const WESTERN_ZHOU_START = -1046
const WESTERN_ZHOU_END = -770
const SPRING_AUTUMN_START = -770
const SPRING_AUTUMN_END = -476
const WARRING_STATES_START = -475
const WARRING_STATES_END = -221

const SPRING_AUTUMN_SLOTS = ['东周', '齐', '秦', '楚', '宋', '晋']
const WARRING_STATES_SLOTS = ['东周', '齐', '秦', '楚', '燕', '韩', '赵', '魏']

const REGIME_ERA_UNIT_COLS = 8
const WARRING_TRIPLE_REGIMES = new Set(['韩', '赵', '魏'])
const SPRING_ONLY_REGIMES = new Set(['宋', '晋'])
const WARRING_ONLY_REGIMES = new Set(['燕', '韩', '赵', '魏'])
const SPANNING_REGIMES = new Set(['东周', '齐', '秦', '楚'])
const REGIME_ONLY_NAMES = new Set([
  '春秋', '齐', '楚', '燕', '秦(诸侯)', '晋', '韩', '赵', '魏', '宋',
])
/** 春秋/战国固定列槽外的小国，不展示 */
const REGIME_EXCLUDED_NAMES = new Set(['鲁', '郑', '吴', '越'])

const REGIME_FALL_YEAR = {
  '春秋': -256,
  '东周': -256,
  '齐': -221,
  '秦(诸侯)': -221,
  '秦': -221,
  '楚': -223,
  '宋': -286,
  '晋': -403,
  '燕': -222,
  '韩': -230,
  '赵': -228,
  '魏': -225,
}

const SPRING_UNIT_SPAN = {
  '东周': [0, 1], '齐': [1, 1], '秦': [2, 1], '楚': [3, 1], '宋': [4, 1], '晋': [5, 3],
}
const WARRING_UNIT_SPAN = {
  '东周': [0, 1], '齐': [1, 1], '秦': [2, 1], '楚': [3, 1],
  '燕': [4, 1], '韩': [5, 1], '赵': [6, 1], '魏': [7, 1],
}

let REGIME_ERA_COLOR_IDX = 0

function setRegimeEraColorIdx(idx) {
  REGIME_ERA_COLOR_IDX = idx
}

function getRegimeEraColorIdx() {
  return REGIME_ERA_COLOR_IDX
}

function isWesternZhouSlice(tS) {
  return tS >= WESTERN_ZHOU_START && tS < WESTERN_ZHOU_END
}

function isSpringAutumnSlice(tS) {
  return tS >= SPRING_AUTUMN_START && tS < SPRING_AUTUMN_END
}

function isWarringStatesSlice(tS) {
  return tS >= WARRING_STATES_START && tS < WARRING_STATES_END
}

function isSpringAutumnWarringEra(tS) {
  return isSpringAutumnSlice(tS) || isWarringStatesSlice(tS)
}

function isRegimeOnlyEraGroup(groupName) {
  return groupName === '春秋' || groupName === '战国'
}

function isRegimeOnlyDynasty(dyn) {
  return REGIME_ONLY_NAMES.has(dyn.name)
}

function isExcludedRegimeDynasty(dyn) {
  if (!REGIME_EXCLUDED_NAMES.has(dyn.name)) return false
  const era = dyn.dynasty || dyn.dynasty2
  return era === '春秋' || era === '战国'
}

function getRegimeDisplayName(name) {
  if (name === '春秋') return '东周'
  if (name === '秦(诸侯)') return '秦'
  return name
}

function matchRegimeSlotKey(entry, slotKey) {
  const label = getRegimeDisplayName(entry.dynastyName)
  return label === slotKey
}

function getRegimeFallEnd(dyn) {
  const key = dyn.name || dyn.dynastyName
  const mapped = REGIME_FALL_YEAR[key] ?? REGIME_FALL_YEAR[getRegimeDisplayName(key)]
  if (mapped != null) return mapped
  return dyn.end
}

function getRegimeKey(dyn) {
  return dyn.name || dyn.dynastyName || ''
}

function getRegimeVisualStart(dyn) {
  const key = getRegimeKey(dyn)
  if (WARRING_ONLY_REGIMES.has(key)) return WARRING_STATES_START
  if (dyn.name === '春秋' || key === '东周') return SPRING_AUTUMN_START
  const parsed = typeof dyn.start === 'number'
    ? dyn.start
    : parseInt(String(dyn.start || '').replace('约', ''), 10) || SPRING_AUTUMN_START
  return Math.max(parsed, SPRING_AUTUMN_START)
}

function filterActiveForEra(active, tS) {
  if (isWesternZhouSlice(tS)) {
    return active.filter(e =>
      e.dynastyName === '西周' ||
      e.dynastyGroup === '西周' ||
      (e.isEmperor && e.dynastyName === '西周')
    )
  }
  if (isSpringAutumnSlice(tS) || isWarringStatesSlice(tS)) {
    const collapsed = active.filter(e =>
      e.isCollapsedRegimeSummary && e.id === 'collapsed_春秋战国'
    )
    if (collapsed.length) return collapsed
    if (isSpringAutumnSlice(tS)) {
      return active.filter(e =>
        e.isRegimeOnly && SPRING_AUTUMN_SLOTS.some(k => matchRegimeSlotKey(e, k))
      )
    }
    return active.filter(e =>
      e.isRegimeOnly && WARRING_STATES_SLOTS.some(k => matchRegimeSlotKey(e, k))
    )
  }
  return active
}

function entryOverlapsRegimeEra(entry) {
  return entry.isRegimeOnly &&
    entry.start < WARRING_STATES_END &&
    entry.end > SPRING_AUTUMN_START
}

function calcRegimeEraUnitGeometry(startCol, span, G) {
  const totalG = (REGIME_ERA_UNIT_COLS - 1) * G
  const unitW = (100 - totalG) / REGIME_ERA_UNIT_COLS
  const leftPct = startCol * (unitW + G)
  const widthPct = span * unitW + (span - 1) * G
  return { leftPct, widthPct, unitW }
}

function calcRegimeEraUnitSpan(slotKey, tS) {
  const map = isSpringAutumnSlice(tS) ? SPRING_UNIT_SPAN : WARRING_UNIT_SPAN
  const m = map[slotKey]
  return m ? { startCol: m[0], span: m[1] } : null
}

function calcRegimeEraPlacement(entry, tS, G) {
  const slots = isSpringAutumnSlice(tS) ? SPRING_AUTUMN_SLOTS : WARRING_STATES_SLOTS
  const slotKey = slots.find(k => matchRegimeSlotKey(entry, k))
  if (!slotKey) {
    const { widthPct } = calcRegimeEraUnitGeometry(0, 1, G)
    return { leftPct: 0, widthPct, colIndex: 0, numCols: REGIME_ERA_UNIT_COLS }
  }
  const spec = calcRegimeEraUnitSpan(slotKey, tS)
  if (!spec) {
    const { widthPct } = calcRegimeEraUnitGeometry(0, 1, G)
    return { leftPct: 0, widthPct, colIndex: 0, numCols: REGIME_ERA_UNIT_COLS }
  }
  const geo = calcRegimeEraUnitGeometry(spec.startCol, spec.span, G)
  return {
    leftPct: geo.leftPct,
    widthPct: geo.widthPct,
    colIndex: spec.startCol,
    numCols: REGIME_ERA_UNIT_COLS,
  }
}

function assignRegimeEraPlacements(active, makePlacement, tS, G) {
  return active.map(entry => {
    const pl = calcRegimeEraPlacement(entry, tS, G)
    return makePlacement(entry, pl.leftPct, pl.widthPct, pl.colIndex, pl.numCols)
  }).sort((a, b) => a.leftPct - b.leftPct)
}

function yearToY(rows, year) {
  for (let i = 0; i < rows.length; i++) {
    const row = rows[i]
    if (year >= row.tS && year < row.tE) {
      const span = row.tE - row.tS
      const frac = span > 0 ? (year - row.tS) / span : 0
      return row.y + frac * row.h
    }
  }
  if (rows.length) {
    const last = rows[rows.length - 1]
    return last.y + last.h
  }
  return 0
}

function getRegimeEraTimeSegments(entry) {
  const visualStart = getRegimeVisualStart(entry)
  const end = getRegimeFallEnd(entry)
  const label = getRegimeDisplayName(entry.dynastyName)
  const segments = []
  const push = (tS, tE, tPlacement) => {
    if (tE <= tS) return
    segments.push({ tS, tE, tPlacement: tPlacement != null ? tPlacement : tS })
  }

  if (SPRING_ONLY_REGIMES.has(label)) {
    const tS = Math.max(visualStart, SPRING_AUTUMN_START)
    const tE = Math.min(end, SPRING_AUTUMN_END)
    push(tS, tE, tS)
    return segments
  }

  if (WARRING_ONLY_REGIMES.has(label)) {
    const tS = Math.max(visualStart, WARRING_STATES_START)
    const tE = Math.min(end, WARRING_STATES_END)
    push(tS, tE, WARRING_STATES_START)
    return segments
  }

  if (SPANNING_REGIMES.has(label)) {
    const tS = Math.max(visualStart, SPRING_AUTUMN_START)
    const tE = Math.min(end, WARRING_STATES_END)
    push(tS, tE, tS)
    return segments
  }

  if (!segments.length && end > visualStart) {
    push(visualStart, end, visualStart)
  }
  return segments
}

function getConcurrentCountAtTop(rows, top) {
  if (!rows || !rows.length) return 1
  const row = rows.find(r => Math.abs(r.y - top) < 2)
    || rows.find(r => top >= r.y && top < r.y + r.h)
  if (!row) return 1
  if (row.concurrentRegimeCount != null) return row.concurrentRegimeCount
  return row.placements ? row.placements.length : 1
}

/** 春秋末→战国初过渡行高于标准垂直间距的部分，由宋/晋与燕韩赵魏分摊消减 */
function getSpringWarringGapTrim(rows, blockVGapRpx) {
  const tr = rows.find(r => r.tS === SPRING_AUTUMN_END && r.tE === WARRING_STATES_START)
  if (!tr) return 0
  return Math.max(0, tr.h - (blockVGapRpx || 16))
}

function buildRegimeEraBlocks(rows, displayEntries, civId, deps) {
  const { entryToCardFields, BLOCK_MIN_SEG_H } = deps
  const G = deps.BLOCK_H_GAP_PCT
  const raw = []

  displayEntries.filter(entryOverlapsRegimeEra).forEach(entry => {
    getRegimeEraTimeSegments(entry).forEach(ts => {
      const pl = calcRegimeEraPlacement(entry, ts.tPlacement, G)
      const top = yearToY(rows, ts.tS)
      const bottom = yearToY(rows, ts.tE)
      if (bottom <= top + 1) return
      raw.push(Object.assign({
        id: `${entry.id}_era_${ts.tS}`,
        entryId: entry.id,
        top,
        h: Math.max(BLOCK_MIN_SEG_H, bottom - top),
        leftPct: pl.leftPct,
        widthPct: pl.widthPct,
        concurrentCount: getConcurrentCountAtTop(rows, top),
      }, entryToCardFields(entry, civId)))
    })
  })

  const byEntry = {}
  raw.forEach(b => {
    if (!byEntry[b.entryId]) byEntry[b.entryId] = []
    byEntry[b.entryId].push(b)
  })

  const gapTrim = getSpringWarringGapTrim(rows, deps.BLOCK_V_GAP_RPX)
  if (gapTrim > 0) {
    raw.forEach(b => {
      const label = b.dynasty || b.displayName
      if (SPRING_ONLY_REGIMES.has(label)) b.h += gapTrim
    })
  }

  const merged = []
  Object.values(byEntry).forEach(segs => {
    segs.sort((a, b) => a.top - b.top)
    let cur = null
    segs.forEach(s => {
      const gk = `${s.leftPct.toFixed(1)}|${s.widthPct.toFixed(1)}`
      if (cur && cur._gk === gk && s.top - (cur.top + cur.h) <= 32) {
        const bottom = Math.max(cur.top + cur.h, s.top + s.h)
        cur.h = Math.max(BLOCK_MIN_SEG_H, bottom - cur.top)
      } else {
        if (cur) {
          delete cur._gk
          merged.push(cur)
        }
        cur = Object.assign({}, s, { _gk: gk })
      }
    })
    if (cur) {
      delete cur._gk
      merged.push(cur)
    }
  })
  return merged
}

function canMergeRegimeEraRow(last, sl) {
  if (!isSpringAutumnWarringEra(last.tS) || !isSpringAutumnWarringEra(sl.tS)) return false
  for (const p of sl.placements) {
    const lp = last.placements.find(x => x.id === p.id)
    if (lp && (
      Math.abs(lp.leftPct - p.leftPct) > 0.5 ||
      Math.abs(lp.widthPct - p.widthPct) > 0.5
    )) return false
  }
  return true
}

function buildRegimeOnlyEntry(dyn, parseYear) {
  const visualStart = getRegimeVisualStart(dyn)
  const end = getRegimeFallEnd(dyn)
  const key = getRegimeKey(dyn)
  return {
    id: dyn.id,
    isEmperor: false,
    isRegimeOnly: true,
    dynastyName: dyn.name,
    dynastyGroup: dyn.dynasty,
    displayName: getRegimeDisplayName(dyn.name),
    start: visualStart,
    end,
    years: end - visualStart,
    colorIdx: dyn.colorIdx,
    startStr: WARRING_ONLY_REGIMES.has(key) ? String(WARRING_STATES_START) : dyn.startStr,
    endStr: String(end),
  }
}

module.exports = {
  WESTERN_ZHOU_START,
  WESTERN_ZHOU_END,
  SPRING_AUTUMN_START,
  SPRING_AUTUMN_END,
  WARRING_STATES_START,
  WARRING_STATES_END,
  setRegimeEraColorIdx,
  getRegimeEraColorIdx,
  isWesternZhouSlice,
  isSpringAutumnSlice,
  isWarringStatesSlice,
  isSpringAutumnWarringEra,
  isRegimeOnlyEraGroup,
  isRegimeOnlyDynasty,
  isExcludedRegimeDynasty,
  getRegimeDisplayName,
  matchRegimeSlotKey,
  filterActiveForEra,
  entryOverlapsRegimeEra,
  assignRegimeEraPlacements,
  buildRegimeEraBlocks,
  canMergeRegimeEraRow,
  buildRegimeOnlyEntry,
}
