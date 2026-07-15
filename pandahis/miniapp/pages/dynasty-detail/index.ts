import { DEV_API_PORT, DEV_LAN_HOST } from '../../native-utils/dev-config'
import { hasToken, request } from '../../native-utils/api'
import { encodePathSegment } from '../../native-utils/encode-path-segment'
import {
  computeUnitFavoriteState,
  fetchFavoritedBoxIdSet,
  promptLoginForFavorite,
  setBoxesFavorited,
} from '../../native-utils/favorite-box'
import { ROUTES, navigateTo } from '../../native-utils/router'
import { decodeQueryValue } from '../../native-utils/query-value'
import { formatHistoryYear } from '../../native-utils/year-format'
import { formatEntrySourceLabel } from '../../native-utils/entry-source-label'
import { promptContentShareUnavailable } from '../../native-utils/share-invite'
import {
  countOffscreenBottom,
  countOffscreenRight,
  dedupeHintItems,
  type OffscreenHintItem,
} from '../../native-utils/offscreen-hints'
const {
  buildSwimMatrixFromMock,
  buildHeroFromMock,
  normalizeDynastyKey,
  isDegradedMockFallback,
} = require('./swim-local-fallback')

type PriorityLevel = 'p0' | 'p1' | 'p2' | 'p3'

const PRIORITY_OPTIONS: { value: PriorityLevel; label: string }[] = [
  { value: 'p0', label: 'P0' },
  { value: 'p1', label: 'P1' },
  { value: 'p2', label: 'P2' },
  { value: 'p3', label: 'P3' },
]

const MAX_LANE_ROWS = 10
const GRID_RPX = 8
const LANE_ROW_HEIGHT_RPX = 44
const LANE_ROW_GAP_RPX = 16
const LANE_TRACK_PAD_VERTICAL_RPX = 24
const CHIP_MAX_RPX = 288
const CHIP_MIN_RPX = 80
const CHIP_HEIGHT_RPX = 52
/** 胶囊左右 padding 合计（与 SCSS 14+14 对齐） */
const CHIP_PAD_H_RPX = 28
const CHIP_TITLE_RPX_PER_CHAR = 24
/** Badge 左右 padding 合计（与 SCSS 8+8 对齐） */
const CHIP_TAG_PAD_H_RPX = 16
const CHIP_TAG_RPX_PER_CHAR = 20
const CHIP_INNER_GAP_RPX = 4
const CHIP_GAP_RPX = 16
const ROW_GAP_RPX = 16
const EDGE_GAP_RPX = 24
const MORE_WIDTH_RPX = 112
const MORE_GAP_RPX = 20
const CANVAS_PAD_LEFT_RPX = 40
const BAND_GAP_RPX = 24
const BAND_PAD_RPX = 16
const MIN_BAND_HEIGHT_RPX = 56
const AXIS_PIN_AT = 150
const AXIS_UNPIN_AT = 110
const CONTINUATION_CUE_THROTTLE_MS = 120
const CONTINUATION_CUE_TOLERANCE_RPX = 16
const CONTINUATION_CUE_BOTTOM_RESERVE_RPX = 128

function roundScrollLeft(left: number): number {
  return Math.round(left)
}

function snapRpx(value: number): number {
  if (value <= 0) return 0
  return Math.max(GRID_RPX, Math.round(value / GRID_RPX) * GRID_RPX)
}


function laneTrackHeight(rowCount: number): number {
  const rows = Math.max(1, rowCount || 1)
  return LANE_TRACK_PAD_VERTICAL_RPX + rows * CHIP_HEIGHT_RPX + (rows - 1) * ROW_GAP_RPX
}

const MIN_BUCKET_YEARS = 10
const MAX_BUCKET_YEARS = 30

function resolveBucketYears(span: number, overflowCount: number): number {
  if (overflowCount <= 0) return span
  if (span <= MAX_BUCKET_YEARS) return span
  const minBuckets = Math.max(1, Math.ceil(overflowCount / 12))
  const maxBuckets = Math.max(minBuckets, Math.ceil(overflowCount / 5))
  const targetBuckets = Math.min(Math.floor(span / MIN_BUCKET_YEARS), Math.floor((minBuckets + maxBuckets) / 2))
  const bucketYears = Math.ceil(span / Math.max(1, targetBuckets))
  return Math.max(MIN_BUCKET_YEARS, Math.min(MAX_BUCKET_YEARS, bucketYears))
}

const BUCKET_CHIP_TITLE = '查看更多'

function parseBucketMemberCount(title: string): number {
  const match = String(title || '').match(/\+(\d+)$/)
  return match ? Number(match[1]) : 0
}

function bucketTitle(laneLabel: string, count: number): string {
  return BUCKET_CHIP_TITLE
}

function anchorYearOfBar(bar: ReturnType<typeof prepareLegacyBar>): number {
  if (typeof bar.peakYear === 'number') return bar.peakYear
  if (typeof bar.startYear === 'number') return bar.startYear
  return 0
}

function placeBucketChips(
  rows: ReturnType<typeof prepareLegacyBar>[][],
  overflow: ReturnType<typeof prepareLegacyBar>[],
  laneKey: string,
  laneLabel: string,
  startYear: number,
  endYear: number,
  sheetWidthRpx: number,
  percentForYear: (year: number) => number,
) {
  if (!overflow.length) return rows
  const span = Math.max(1, endYear - startYear)
  const bucketYears = resolveBucketYears(span, overflow.length)
  const gapPct = CHIP_GAP_RPX / sheetWidthRpx * 100
  const nextRows = rows.map((row) => [...row])
  const rowEnds = nextRows.map((row) => Math.max(0, ...row.map((bar) => bar._rightPct)))

  let cursor = startYear
  let bucketIndex = 0
  while (cursor < endYear) {
    const bucketEnd = Math.min(endYear, cursor + bucketYears)
    const members = overflow.filter((bar) => {
      const y = anchorYearOfBar(bar)
      return y >= cursor && y < bucketEnd
    })
    if (members.length) {
      const countTag = buildOverlayCountTag(laneLabel, members.length)
      const title = BUCKET_CHIP_TITLE
      const chipW = estimateChipWidthRpx(title, countTag)
      const chipPct = chipW / sheetWidthRpx * 100
      const anchorYear = Math.floor((cursor + bucketEnd) / 2)
      const centerPct = percentForYear(anchorYear)
      const edgePct = EDGE_GAP_RPX / sheetWidthRpx * 100
      const maxLeft = 100 - (chipW + EDGE_GAP_RPX) / sheetWidthRpx * 100
      const left = Math.max(edgePct, Math.min(maxLeft, centerPct - chipPct / 2))
      const bucketBar = {
        title,
        chipTag: countTag,
        boxId: `BUCKET_${laneKey}_${bucketIndex}`,
        left: `${left.toFixed(2)}%`,
        width: `${chipPct.toFixed(2)}%`,
        unitLeft: `${left.toFixed(2)}%`,
        unitWidth: `${chipPct.toFixed(2)}%`,
        chipLeft: `${left.toFixed(2)}%`,
        chipWidth: `${chipW}rpx`,
        lineLeftW: '0rpx',
        lineRightL: '0rpx',
        lineRightW: '0rpx',
        priority: 'p3',
        type: 'overflow_bucket',
        timeRange: `${formatHistoryYear(cursor)} — ${formatHistoryYear(bucketEnd)}`,
        startYear: cursor,
        endYear: bucketEnd,
        peakYear: anchorYear,
        heightRpx: CHIP_HEIGHT_RPX,
        _leftPct: left,
        _rightPct: left + chipPct,
        _priorityRank: 3,
        _globalIdNumber: 0,
      } as ReturnType<typeof prepareLegacyBar>

      let assigned = -1
      for (let rowIndex = 0; rowIndex < nextRows.length; rowIndex++) {
        if (rowEnds[rowIndex] + gapPct <= bucketBar._leftPct) {
          assigned = rowIndex
          rowEnds[rowIndex] = bucketBar._rightPct
          nextRows[rowIndex] = [...nextRows[rowIndex], bucketBar].sort((a, b) => a._leftPct - b._leftPct)
          break
        }
      }
      if (assigned === -1) {
        nextRows.push([bucketBar])
        rowEnds.push(bucketBar._rightPct)
      }
      bucketIndex += 1
    }
    cursor = bucketEnd
  }
  return nextRows
}

function collectMatrixBoxIds(swim: { lanes?: SwimLane[] } | null) {
  const ids: string[] = []
  for (const lane of swim?.lanes || []) {
    const fullView = lane.priorityViews?.p3
    const rows = fullView?.collapsedRows || lane.collapsedRows || []
    for (const row of rows) {
      for (const bar of row) {
        if (bar?.boxId) ids.push(bar.boxId)
      }
    }
    for (const bar of fullView?.extraBars || lane.extraBars || []) {
      if (bar?.boxId) ids.push(bar.boxId)
    }
  }
  return Array.from(new Set(ids))
}

function findSwimBar(swim: { lanes?: SwimLane[] } | null, boxId: string): SwimBar | null {
  if (!swim?.lanes?.length || !boxId) return null
  for (const lane of swim.lanes) {
    const rows = lane.collapsedRows || []
    for (const row of rows) {
      for (const bar of row) {
        if (bar?.boxId === boxId) return bar
      }
    }
    for (const bar of lane.extraBars || []) {
      if (bar?.boxId === boxId) return bar
    }
  }
  return null
}

type UnitHero = {
  unit: {
    id: string
    name: string
    rulerName?: string | null
    dynastyName?: string
    crumbText: string
    eraText: string
    startYear: number
    endYear: number
    durationYears: number
    summary: string
  }
  relatedUnits?: { unitId: string; title: string; startYear: number }[]
  nextUnit?: { unitId: string; title: string; startYear: number } | null
}

type SwimBar = {
  title: string
  boxId: string
  left: string
  width: string
  unitLeft: string
  unitWidth: string
  chipLeft: string
  chipWidth: string
  lineLeftW: string
  lineRightL: string
  lineRightW: string
  priority: string
  type: string
  timeRange?: string
  zIndex?: number
  startYear?: number
  endYear?: number
  peakYear?: number
  peakReason?: string
  priorityReason?: string
  entrySource?: string
  globalIdNumber?: number
  topRpx?: number
  heightRpx?: number
  chipTag?: string
}

type CategoryBand = {
  key: string
  label: string
  borderColor: string
  topRpx: number
  heightRpx: number
  readProgressText?: string
  totalCount: number
}

type SwimLaneView = {
  collapsedRows: SwimBar[][]
  hasMore: boolean
  moreCount: number
  moreBarLeft: string
  moreBarWidth: string
  extraBars: SwimBar[]
  rowCount: number
  trackHeightRpx: number
  visibleCount: number
}

type SwimLane = {
  key: string
  label: string
  icon: string
  borderColor: string
  layout: string
  totalCount: number
  readCount?: number | null
  readProgressText?: string
  collapsedRows: SwimBar[][]
  hasMore: boolean
  moreCount: number
  moreBarLeft?: string
  moreBarWidth?: string
  extraBars?: SwimBar[]
  priorityViews?: Record<PriorityLevel, SwimLaneView>
  rowCount?: number
  trackHeightRpx?: number
  visibleCount?: number
  laneToneIndex?: number
  laneColor?: string
  laneHeadBg?: string
  laneTrackBg?: string
  laneHeightRpx?: number
  bandTopRpx?: number
  bandHeightRpx?: number
  moreTopRpx?: number
}

type SwimMatrix = {
  startYear: number
  endYear: number
  endLabel: string
  ticks: { label: string; left: string; edgeStart?: boolean; hideLabel?: boolean; segmentBoundary?: boolean }[]
  gridLines?: { left: string }[]
  timeSegments?: {
    startYear: number
    endYear: number
    startLabel: string
    endLabel: string
    left: string
    width: string
    boxCount: number
    dense: boolean
  }[]
  timeScaleMode?: string
  lanes: SwimLane[]
  concurrentItems: string[]
  sheetWidthRpx: number
  canvasHeightRpx?: number
  canvasPadLeftRpx?: number
  canvasWidthRpx?: number
  categoryBands?: CategoryBand[]
}

function continuationWeight(bar: SwimBar): number {
  if (bar.type !== 'overflow_bucket') return 1
  const count = parseInt(String(bar.chipTag || '').match(/^\d+/)?.[0] || '1', 10)
  return Number.isFinite(count) ? Math.max(1, count) : 1
}

function buildContinuationItems(swim: SwimMatrix): OffscreenHintItem[] {
  const sheetWidthRpx = swim.sheetWidthRpx || 1440
  const padLeftRpx = swim.canvasPadLeftRpx ?? CANVAS_PAD_LEFT_RPX
  const items = (swim.lanes || []).flatMap((lane) =>
    (lane.collapsedRows || []).flatMap((row) =>
      row.map((bar) => {
        const leftPct = parseFloat(String(bar.left || '0').replace('%', ''))
        const chipWidthRpx = parseFloat(String(bar.chipWidth || '0').replace('rpx', ''))
        const topRpx = Number(bar.topRpx || 0)
        const heightRpx = Number(bar.heightRpx || CHIP_HEIGHT_RPX)
        return {
          id: bar.boxId,
          rightRpx:
            padLeftRpx
            + (Number.isFinite(leftPct) ? leftPct : 0) / 100 * sheetWidthRpx
            + (Number.isFinite(chipWidthRpx) ? chipWidthRpx : 0),
          bottomRpx: topRpx + heightRpx / 2,
          weight: continuationWeight(bar),
        }
      }),
    ),
  )
  return dedupeHintItems(items)
}

function percentForYearOnSwim(swim: SwimMatrix, year: number): number {
  const clamped = Math.max(swim.startYear, Math.min(swim.endYear, year))
  const segments = swim.timeSegments || []
  if (segments.length) {
    for (const seg of segments) {
      if (clamped < seg.startYear || clamped > seg.endYear) continue
      const segLeft = parseFloat(String(seg.left).replace('%', ''))
      const segWidth = parseFloat(String(seg.width).replace('%', ''))
      const segSpan = Math.max(1, seg.endYear - seg.startYear)
      return segLeft + ((clamped - seg.startYear) / segSpan) * segWidth
    }
  }
  const span = Math.max(1, swim.endYear - swim.startYear)
  return ((clamped - swim.startYear) / span) * 100
}

function splitIntroParagraphs(intro: string): string[] {
  const text = (intro || '').trim() || '空'
  return text.split(/\n\n+/).map((p) => p.trim()).filter(Boolean)
}

function isDevelopEnv(): boolean {
  try {
    return wx.getAccountInfoSync()?.miniProgram?.envVersion === 'develop'
  } catch {
    return true
  }
}

function warnIfDegradedMock(swim: SwimMatrix) {
  if (!isDegradedMockFallback(swim)) return
  wx.showToast({
    title: `后端未连通(${DEV_LAN_HOST}:${DEV_API_PORT})，仅显示君王`,
    icon: 'none',
    duration: 3500,
  })
}

function tryLoadLocalMock(
  dynastyName: string,
  unitId: string,
): { hero: UnitHero; swim: SwimMatrix } | null {
  const key = normalizeDynastyKey(dynastyName)
  if (!key) return null
  try {
    const swimMatrix = buildSwimMatrixFromMock(key)
    if (!swimMatrix?.lanes?.length) return null
    const hero = buildHeroFromMock(swimMatrix, unitId || key, key)
    return { hero, swim: swimMatrix as SwimMatrix }
  } catch (err) {
    console.warn('[dynasty-detail] local mock failed', err)
    return null
  }
}

/* ── 生成20年间隔时间轴刻度 ── */
const TARGET_TICK_SPACING_RPX = 96
const MIN_LABEL_SPACING_RPX = 104

function niceTickStep(raw: number): number {
  if (raw <= 1) return 1
  if (raw <= 2) return 2
  if (raw <= 5) return 5
  if (raw <= 10) return 10
  if (raw <= 20) return 20
  if (raw <= 25) return 25
  if (raw <= 50) return 50
  if (raw <= 100) return 100
  if (raw <= 200) return 200
  if (raw <= 500) return 500
  return 1000
}

function computeTickStep(span: number, sheetWidthRpx: number): number {
  const yearsPerTickGrid = (TARGET_TICK_SPACING_RPX / Math.max(1, sheetWidthRpx)) * span
  const yearsPerTickLabel = (MIN_LABEL_SPACING_RPX / Math.max(1, sheetWidthRpx)) * span
  return niceTickStep(Math.max(yearsPerTickGrid, yearsPerTickLabel))
}

function roundUpToStep(year: number, step: number): number {
  if (step <= 1) return year
  const rem = ((year % step) + step) % step
  if (rem === 0) return year
  return year + (step - rem)
}

function generateTimelineTicks(startYear: number, endYear: number, originalSheetWidthRpx: number) {
  const span = endYear - startYear
  const newSheetWidthRpx = Math.round(originalSheetWidthRpx)
  const ticks: { label: string; left: string; edgeStart?: boolean; hideLabel?: boolean }[] = []
  const step = computeTickStep(span, newSheetWidthRpx)

  ticks.push({ label: formatHistoryYear(startYear), left: '0%', edgeStart: true, hideLabel: false })

  let tickYear = roundUpToStep(startYear + 1, step)
  while (tickYear < endYear) {
    const left = ((tickYear - startYear) / span) * 100
    const hideLabel = tickYear - startYear < step || endYear - tickYear < step
    ticks.push({ label: formatHistoryYear(tickYear), left: `${left}%`, hideLabel })
    tickYear += step
  }

  // 泳道网格线：从第2个刻度开始，与时间轴刻度对齐
  const gridLines = ticks.filter(t => t.left !== '0%').map(t => ({ left: t.left }))

  return { ticks, endLabel: formatHistoryYear(endYear), sheetWidthRpx: newSheetWidthRpx, gridLines }
}

function visibleLength(value: string): number {
  const trimmed = String(value || '').trim()
  return Array.from(trimmed).length
}

function formatPriorityLabel(priority: string): string {
  const p = String(priority || '').trim().toLowerCase()
  if (!p) return ''
  return p.toUpperCase()
}

function splitTimeRangeLabels(bar: SwimBar | null, fallbackRange: string): { start: string; end: string } {
  if (bar?.startYear != null && bar?.endYear != null) {
    return {
      start: formatHistoryYear(bar.startYear),
      end: formatHistoryYear(bar.endYear),
    }
  }
  const parts = String(fallbackRange || '').split(/\s*[—–-]\s*/)
  if (parts.length >= 2) {
    return { start: parts[0].trim(), end: parts[parts.length - 1].trim() }
  }
  const single = String(fallbackRange || '').trim()
  return { start: single, end: '' }
}

function estimateChipWidthRpx(title: string, chipTag?: string): number {
  const titleLen = visibleLength(title)
  const tag = String(chipTag || '').trim()
  let tagW = 0
  if (tag) {
    tagW = CHIP_TAG_PAD_H_RPX + visibleLength(tag) * CHIP_TAG_RPX_PER_CHAR + CHIP_INNER_GAP_RPX
  }
  const raw = CHIP_PAD_H_RPX + titleLen * CHIP_TITLE_RPX_PER_CHAR + tagW
  return snapRpx(Math.max(CHIP_MIN_RPX, Math.min(CHIP_MAX_RPX, raw)))
}

function chipWidthRpxFromBar(bar: SwimBar): number {
  return estimateChipWidthRpx(bar.title, bar.chipTag)
}

/** 后端仍返回旧固定宽时，按宽度差回推 left，保持峰值年居中 */
function adjustLeftForChipWidth(bar: SwimBar, chipW: number, sheetWidthRpx: number): string {
  const apiMatch = String(bar.chipWidth || '').match(/^(\d+)rpx$/)
  const apiW = apiMatch ? parseInt(apiMatch[1], 10) : chipW
  const leftStr = bar.left || bar.unitLeft || '0%'
  const leftPct = parseFloat(String(leftStr).replace('%', ''))
  if (!Number.isFinite(leftPct) || apiW >= chipW) return leftStr
  const shiftPct = ((chipW - apiW) / 2) / sheetWidthRpx * 100
  return `${Math.max(0, leftPct - shiftPct).toFixed(2)}%`
}

function chipHeightRpx(bar: SwimBar): number {
  return bar.heightRpx || CHIP_HEIGHT_RPX
}

function withBucketChipMeta(bar: SwimBar, laneLabel = ''): SwimBar {
  if (bar.type !== 'overflow_bucket') return bar
  if (bar.title === BUCKET_CHIP_TITLE && bar.chipTag) return bar
  let count = 0
  const tagMatch = String(bar.chipTag || '').match(/^(\d+)位/)
  if (tagMatch) count = Number(tagMatch[1])
  if (!count) count = parseBucketMemberCount(bar.title)
  return {
    ...bar,
    title: BUCKET_CHIP_TITLE,
    chipTag: buildOverlayCountTag(laneLabel, count),
  }
}

function buildOverlayCountTag(label: string, count: number): string {
  const category = String(label || '史略').trim()
  return `${Math.max(0, count)}位${category}`
}

function hasLaneContent(lane: SwimLane): boolean {
  return (lane.totalCount ?? 0) > 0
}

function composeCanvasLayout(swim: SwimMatrix, lanes: SwimLane[]): SwimMatrix {
  const categoryBands: CategoryBand[] = []
  const canvasLanes: SwimLane[] = []
  let cursor = BAND_PAD_RPX
  const sheetWidthRpx = swim.sheetWidthRpx || 1440
  const visibleLanes = lanes.filter(hasLaneContent)

  for (const lane of visibleLanes) {
    const rowCount = Math.max(1, lane.rowCount || lane.collapsedRows?.length || 1)
    const trackHeight = snapRpx(
      LANE_TRACK_PAD_VERTICAL_RPX + rowCount * CHIP_HEIGHT_RPX + (rowCount - 1) * ROW_GAP_RPX,
    )
    const bandHeight = Math.max(MIN_BAND_HEIGHT_RPX, trackHeight)

    const canvasRows: SwimBar[][] = []
    ;(lane.collapsedRows || []).forEach((row, rowIndex) => {
      const topRpx = snapRpx(cursor + BAND_PAD_RPX + rowIndex * (CHIP_HEIGHT_RPX + ROW_GAP_RPX))
      canvasRows.push(
        row.map((bar) => {
          const enriched = withBucketChipMeta(bar, lane.label)
          const chipW = chipWidthRpxFromBar(enriched)
          const left = adjustLeftForChipWidth(enriched, chipW, sheetWidthRpx)
          return {
            ...enriched,
            left,
            topRpx,
            heightRpx: chipHeightRpx(enriched),
            chipWidth: `${chipW}rpx`,
            width: `${(chipW / sheetWidthRpx * 100).toFixed(2)}%`,
          }
        }),
      )
    })

    categoryBands.push({
      key: lane.key,
      label: lane.label,
      borderColor: lane.borderColor,
      topRpx: cursor,
      heightRpx: bandHeight,
      readProgressText: lane.readProgressText || `${lane.readCount ?? 0}/${lane.totalCount ?? 0}`,
      totalCount: lane.totalCount,
    })

    canvasLanes.push({
      ...lane,
      bandTopRpx: cursor,
      bandHeightRpx: bandHeight,
      moreTopRpx: snapRpx(cursor + bandHeight / 2),
      trackHeightRpx: bandHeight,
      collapsedRows: canvasRows.length ? canvasRows : [[]],
    })

    cursor += bandHeight + BAND_GAP_RPX
  }

  return {
    ...swim,
    lanes: canvasLanes,
    categoryBands,
    canvasHeightRpx: snapRpx(Math.max(MIN_BAND_HEIGHT_RPX + BAND_PAD_RPX * 2, cursor + BAND_PAD_RPX)),
    canvasPadLeftRpx: swim.canvasPadLeftRpx ?? CANVAS_PAD_LEFT_RPX,
    canvasWidthRpx: (swim.sheetWidthRpx || 1440) + (swim.canvasPadLeftRpx ?? CANVAS_PAD_LEFT_RPX),
  }
}

function stripLegacyBarFields(bar: ReturnType<typeof prepareLegacyBar>): SwimBar {
  const { _leftPct, _rightPct, _priorityRank, _globalIdNumber, ...rest } = bar
  return rest
}

function enrichApiLaneView(
  lane: SwimLane,
  view: SwimLaneView,
  swim: SwimMatrix,
  sheetWidthRpx: number,
): SwimLaneView {
  const extra = view.extraBars || []
  const hasBuckets = (view.collapsedRows || []).some((row) =>
    row.some((bar) => bar.type === 'overflow_bucket'),
  )
  if (!extra.length || hasBuckets) {
    return view
  }

  const rows = (view.collapsedRows || [[]]).map((row) =>
    row.map((bar) => prepareLegacyBar(bar, sheetWidthRpx)),
  )
  const extraPrepared = extra.map((bar) => prepareLegacyBar(bar, sheetWidthRpx))
  const rowsWithBuckets = placeBucketChips(
    rows.length ? rows : [[]],
    extraPrepared,
    lane.key,
    lane.label,
    swim.startYear,
    swim.endYear,
    sheetWidthRpx,
    (year) => percentForYearOnSwim(swim, year),
  )
  const collapsedRows = rowsWithBuckets.map((row) => row.map(stripLegacyBarFields))
  const bucketCount = collapsedRows.reduce(
    (count, row) => count + row.filter((bar) => bar.type === 'overflow_bucket').length,
    0,
  )
  const individualCount = collapsedRows.reduce(
    (count, row) => count + row.filter((bar) => bar.type !== 'overflow_bucket').length,
    0,
  )

  return {
    ...view,
    collapsedRows,
    hasMore: false,
    rowCount: Math.max(1, collapsedRows.length),
    trackHeightRpx: laneTrackHeight(collapsedRows.length),
    visibleCount: individualCount + bucketCount,
  }
}

function applyPriorityView(swim: SwimMatrix, priority: PriorityLevel): SwimMatrix {
  const sheetWidthRpx = swim.sheetWidthRpx || 1440
  const lanes = (swim.lanes || []).map((lane) => {
    const view = lane.priorityViews?.[priority]
    if (!view) {
      return normalizeLegacyLane(lane, sheetWidthRpx, priority, swim)
    }
    const enriched = enrichApiLaneView(lane, view, swim, sheetWidthRpx)
    return {
      ...lane,
      collapsedRows: enriched.collapsedRows || [[]],
      hasMore: enriched.hasMore,
      moreCount: enriched.moreCount,
      moreBarLeft: enriched.moreBarLeft,
      moreBarWidth: enriched.moreBarWidth,
      extraBars: enriched.extraBars || [],
      rowCount: enriched.rowCount,
      trackHeightRpx: enriched.trackHeightRpx,
      visibleCount: enriched.visibleCount,
    }
  })
  return composeCanvasLayout({ ...swim, sheetWidthRpx }, lanes)
}

function estimateSheetWidth(swim: SwimMatrix): number {
  const base = swim.sheetWidthRpx || 1440
  const maxBars = Math.max(0, ...(swim.lanes || []).map((lane) => {
    const view = lane.priorityViews?.p3
    if (view) return view.visibleCount
    return (lane.collapsedRows || []).reduce((count, row) => count + row.length, 0) + (lane.extraBars || []).length
  }))
  const perRow = Math.max(1, Math.ceil(maxBars / MAX_LANE_ROWS))
  const needed = EDGE_GAP_RPX + perRow * CHIP_MAX_RPX + Math.max(0, perRow - 1) * CHIP_GAP_RPX + MORE_GAP_RPX + MORE_WIDTH_RPX + EDGE_GAP_RPX
  return Math.max(base, Math.min(base * 4, needed))
}

function normalizeLegacyLane(
  lane: SwimLane,
  sheetWidthRpx: number,
  priority: PriorityLevel,
  swim: SwimMatrix,
): SwimLane {
  const allBars = [...(lane.collapsedRows || []).flat(), ...(lane.extraBars || [])]
    .map((bar) => prepareLegacyBar(bar, sheetWidthRpx))
    .sort(compareLegacyBars)
  const maxPriority = priorityRank(priority)
  const candidates = allBars.filter((bar) => priorityRank(bar.priority) <= maxPriority)
  const hiddenByPriority = allBars.filter((bar) => priorityRank(bar.priority) > maxPriority)
  const packed = packLegacyBars(candidates, sheetWidthRpx)
  const extraBars = [...hiddenByPriority, ...packed.extra].sort(compareLegacyBars)
  const rowsWithBuckets = placeBucketChips(
    packed.rows.length ? packed.rows : [[]],
    extraBars,
    lane.key,
    lane.label,
    swim.startYear,
    swim.endYear,
    sheetWidthRpx,
    (year) => percentForYearOnSwim(swim, year),
  )
  const bucketCount = rowsWithBuckets.reduce(
    (count, row) => count + row.filter((bar) => bar.type === 'overflow_bucket').length,
    0,
  )
  const individualCount = rowsWithBuckets.reduce(
    (count, row) => count + row.filter((bar) => bar.type !== 'overflow_bucket').length,
    0,
  )

  return {
    ...lane,
    collapsedRows: rowsWithBuckets.map((row) => row.map(stripLegacyBarFields)),
    hasMore: false,
    moreCount: extraBars.length,
    moreBarLeft: `${moreLeftPct(sheetWidthRpx).toFixed(2)}%`,
    moreBarWidth: lane.moreBarWidth || '12%',
    extraBars,
    rowCount: Math.max(1, rowsWithBuckets.length),
    trackHeightRpx: laneTrackHeight(rowsWithBuckets.length),
    visibleCount: individualCount + bucketCount,
  }
}

function prepareLegacyBar(bar: SwimBar, sheetWidthRpx: number): SwimBar & { _leftPct: number; _rightPct: number; _priorityRank: number; _globalIdNumber: number } {
  const rawLeft = parseFloat(String(bar.left || bar.unitLeft || '0').replace('%', ''))
  const edgePct = 20 / sheetWidthRpx * 100
  const chipW = chipWidthRpxFromBar(bar)
  const chipPct = chipW / sheetWidthRpx * 100
  const maxLeft = 100 - (chipW + EDGE_GAP_RPX) / sheetWidthRpx * 100
  const left = Math.max(edgePct, Math.min(maxLeft, Number.isFinite(rawLeft) ? rawLeft : 0))
  const normalized = {
    ...bar,
    left: `${left.toFixed(2)}%`,
    width: `${chipPct.toFixed(2)}%`,
    chipWidth: bar.chipWidth || `${chipW}rpx`,
    heightRpx: chipHeightRpx(bar),
    _leftPct: left,
    _rightPct: left + chipPct,
    _priorityRank: priorityRank(bar.priority),
    _globalIdNumber: parseGlobalIdNumber(bar.boxId),
  }
  return normalized
}

function packLegacyBars(bars: ReturnType<typeof prepareLegacyBar>[], sheetWidthRpx: number) {
  const rows: ReturnType<typeof prepareLegacyBar>[][] = []
  const extra: ReturnType<typeof prepareLegacyBar>[] = []
  const gapPct = CHIP_GAP_RPX / sheetWidthRpx * 100

  for (const bar of bars) {
    let assigned = -1
    for (let rowIndex = 0; rowIndex < rows.length; rowIndex++) {
      if (canFitRow(rows[rowIndex], bar, gapPct)) {
        assigned = rowIndex
        rows[rowIndex] = [...rows[rowIndex], bar].sort((a, b) => a._leftPct - b._leftPct)
        break
      }
    }
    if (assigned === -1) {
      if (rows.length >= MAX_LANE_ROWS) {
        extra.push(bar)
      } else {
        rows.push([bar])
      }
    }
  }

  return { rows, extra }
}

function canFitRow(row: ReturnType<typeof prepareLegacyBar>[], bar: ReturnType<typeof prepareLegacyBar>, gapPct: number): boolean {
  return row.every((existing) => bar._rightPct + gapPct <= existing._leftPct || existing._rightPct + gapPct <= bar._leftPct)
}

function compareLegacyBars(a: ReturnType<typeof prepareLegacyBar>, b: ReturnType<typeof prepareLegacyBar>): number {
  if (a._priorityRank !== b._priorityRank) return a._priorityRank - b._priorityRank
  if (a._leftPct !== b._leftPct) return a._leftPct - b._leftPct
  return a._globalIdNumber - b._globalIdNumber
}

function priorityRank(priority?: string): number {
  const value = String(priority || 'p3').toLowerCase()
  if (value === 'p0') return 0
  if (value === 'p1') return 1
  if (value === 'p2') return 2
  return 3
}

function parseGlobalIdNumber(boxId?: string): number {
  const match = String(boxId || '').match(/^GLBL_(\d+)$/)
  return match ? Number(match[1]) : Number.MAX_SAFE_INTEGER
}

function moreLeftPct(sheetWidthRpx: number): number {
  return 100 - ((EDGE_GAP_RPX + MORE_WIDTH_RPX) / sheetWidthRpx * 100)
}

function rpxToPx(rpx: number, windowWidth: number): number {
  return Math.round(rpx * (windowWidth / 750))
}

type ChipTooltipPlacement = { left: number; top: number; transform: string; origin: string }

function computeChipTooltipSafeTop(axisPinned: boolean, scrollViewTopPx: number, windowWidth: number): number {
  const axisHeightPx = axisPinned ? rpxToPx(86, windowWidth) + 8 : 0
  return scrollViewTopPx + axisHeightPx + 8
}

function computeChipTooltipSafeBottom(windowHeight: number, windowWidth: number, safeAreaBottom = 0): number {
  return windowHeight - rpxToPx(120, windowWidth) - safeAreaBottom
}

function computeChipTooltipPlacement(
  rect: { top: number; bottom: number; left: number; width: number },
  opts: { safeTop: number; safeBottom: number; windowWidth: number },
): ChipTooltipPlacement {
  const gap = 8
  const minTooltipH = 96
  const centerX = rect.left + rect.width / 2
  const left = Math.max(140, Math.min(opts.windowWidth - 140, centerX))
  const spaceAbove = rect.top - opts.safeTop
  const spaceBelow = opts.safeBottom - rect.bottom
  const showAbove = spaceAbove >= minTooltipH && spaceAbove >= spaceBelow
  if (showAbove) {
    return {
      left,
      top: rect.top - gap,
      transform: 'translate(-50%, -100%)',
      origin: '50% 100%',
    }
  }
  return {
    left,
    top: rect.bottom + gap,
    transform: 'translate(-50%, 0)',
    origin: '50% 0%',
  }
}

function chipTooltipTransformWithScale(baseTransform: string, scale: number): string {
  return `${baseTransform} scale(${scale.toFixed(2)})`
}

function previewIntro(intro: string): { preview: string; canExpand: boolean; paragraphs: string[] } {
  const paragraphs = splitIntroParagraphs(intro)
  if (paragraphs.length <= 1) {
    return { preview: paragraphs[0] || '空', canExpand: false, paragraphs }
  }
  return { preview: paragraphs[0], canExpand: true, paragraphs }
}

Page({
  swimScrollLeft: 0,
  pageUnloaded: false,
  continuationItems: [] as OffscreenHintItem[],
  continuationRatio: 1,
  continuationViewportWidthPx: 0,
  continuationWindowHeightPx: 0,
  continuationCanvasTopPx: 0,
  continuationCanvasHeightPx: 0,
  continuationPageScrollTop: 0,
  continuationGeometryReady: false,
  continuationLastUpdateAt: 0,
  continuationUpdateTimer: null as ReturnType<typeof setTimeout> | null,
  chipTooltipExitTimer: null as ReturnType<typeof setTimeout> | null,
  data: {
    unit: null as UnitHero['unit'] | null,
    dynastyTitle: '',
    navTitle: '',
    heroSubLine: '',
    swim: null as SwimMatrix | null,
    concurrentItems: [] as string[],
    relatedUnits: [] as NonNullable<UnitHero['relatedUnits']>,
    nextUnit: null as UnitHero['nextUnit'] | null,
    introPreview: '',
    introDisplay: '',
    introCanExpand: false,
    introParagraphs: [] as string[],
    showIntroModal: false,
    matrixBoxIds: [] as string[],
    isFav: false,
    favPartial: false,
    favToggling: false,
    headerPadPx: 88,
    scrollTop: 140,
    panelScrollLeft: 0,
    axisMirrorLeft: 0,
    axisPinned: false,
    overlayVisible: false,
    overlayCountTag: '',
    overlayBars: [] as SwimBar[],
    overlayLaneKey: '',
    continuationRightCount: 0,
    continuationBottomCount: 0,
    continuationCanvasActive: false,
    loadError: '',
    priorityOptions: PRIORITY_OPTIONS,
    activePriority: 'p3' as PriorityLevel,
    chipTooltipVisible: false,
    chipTooltipPhase: 'enter' as 'enter' | 'idle' | 'exit',
    chipTooltipHeldId: '',
    chipTooltipTitle: '',
    chipTooltipRange: '',
    chipTooltipTag: '',
    chipTooltipPeakYear: '',
    chipTooltipPeakReason: '',
    chipTooltipPriority: '',
    chipTooltipPriorityReason: '',
    chipTooltipEntrySource: '',
    chipTooltipLaneKey: '',
    chipTooltipStartYear: '',
    chipTooltipEndYear: '',
    chipTooltipLeftPx: 0,
    chipTooltipTopPx: 0,
    chipTooltipBaseTransform: 'translate(-50%, -100%)',
    chipTooltipOrigin: '50% 100%',
    chipTooltipTransform: 'translate(-50%, -100%) scale(0.88)',
  },
  onShow() {
    void this.refreshFavState()
  },
  onUnload() {
    this.pageUnloaded = true
    if (this.continuationUpdateTimer) clearTimeout(this.continuationUpdateTimer)
    if (this.chipTooltipExitTimer) clearTimeout(this.chipTooltipExitTimer)
  },
  onShareAppMessage() {
    const u = this.data.unit
    const t = this.data.dynastyTitle || u?.name || '朝代详情'
    const id = u?.id
    const path = id ? `/pages/dynasty-detail/index?unitId=${encodeURIComponent(id)}` : '/pages/dynasty-detail/index'
    return { title: t, path }
  },
  async onLoad(query: Record<string, string | undefined>) {
    const unitId = query.unitId || query.id
    const dynastyHint = decodeQueryValue(query.dynasty || query.displayName || '')
    if (!unitId && !dynastyHint) return

    const sys = wx.getSystemInfoSync()
    const navH = Math.round(88 * (sys.windowWidth / 750))
    const headerPadPx = (sys.statusBarHeight || 20) + navH
    const tabBarH = Math.round(72 * (sys.windowWidth / 750))
    const scrollTop = headerPadPx + tabBarH
    this.continuationRatio = sys.windowWidth / 750
    this.continuationViewportWidthPx = sys.windowWidth - 48 * this.continuationRatio
    this.continuationWindowHeightPx = sys.windowHeight
    const anchorYear = query.anchorYear ? parseInt(query.anchorYear, 10) : NaN
    const provisionalNavTitle = dynastyHint
      ? (dynastyHint.length <= 4 ? dynastyHint : dynastyHint.slice(0, 4))
      : ''

    this.setData({
      headerPadPx,
      scrollTop,
      navTitle: provisionalNavTitle,
      dynastyTitle: dynastyHint,
    })

    const applyPageData = (
      hero: UnitHero,
      swim: SwimMatrix,
    ) => {
      const unit = hero.unit
      const dynastyTitle = (unit.dynastyName && unit.dynastyName.trim()) || unit.name
      const navTitle = dynastyTitle.length <= 4 ? dynastyTitle : dynastyTitle.slice(0, 4)
      const heroSubLine = `${formatHistoryYear(unit.startYear)}–${formatHistoryYear(unit.endYear)}`
      const activePriority = this.data.activePriority || 'p3'
      const prioritySwim = applyPriorityView(swim, activePriority)
      const matrixBoxIds = collectMatrixBoxIds(prioritySwim)
      const { preview, canExpand, paragraphs } = previewIntro(unit.summary || '')
      this.setData({
        unit,
        dynastyTitle,
        navTitle,
        heroSubLine,
        swim: prioritySwim,
        concurrentItems: prioritySwim.concurrentItems || [],
        relatedUnits: hero.relatedUnits || [],
        nextUnit: hero.nextUnit ?? null,
        matrixBoxIds,
        headerPadPx,
        scrollTop,
        introPreview: preview,
        introDisplay: preview,
        introCanExpand: canExpand,
        introParagraphs: paragraphs,
        loadError: '',
      }, () => {
        this.rebuildContinuationHints(prioritySwim)
      })
      void this.refreshFavState()
      if (!Number.isNaN(anchorYear)) {
        setTimeout(() => this.scrollToAnchorYear(anchorYear, swim), 120)
      }
    }

    if (unitId) {
      try {
        const enc = encodePathSegment(unitId)
        const [heroRes, swimRes] = await Promise.all([
          request<UnitHero>(`/units/${enc}`),
          request<SwimMatrix>(`/units/${enc}/swim-matrix`),
        ])
        applyPageData(heroRes.data, {
          ...swimRes.data,
          gridLines: swimRes.data.gridLines || [],
        })
        return
      } catch (e: any) {
        console.error('[dynasty-detail] API failed', e)
        if (isDevelopEnv() && dynastyHint) {
          const fallback = tryLoadLocalMock(dynastyHint, unitId)
          if (fallback) {
            console.warn('[dynasty-detail] using local mock for', dynastyHint)
            const enhancedSwim = {
              ...fallback.swim,
              ...generateTimelineTicks(
                fallback.swim.startYear,
                fallback.swim.endYear,
                fallback.swim.sheetWidthRpx,
              ),
              timeScaleMode: 'linear',
            }
            applyPageData(fallback.hero, enhancedSwim)
            warnIfDegradedMock(enhancedSwim)
            return
          }
        }
        const msg = e?.message || '加载失败'
        this.setData({
          unit: null,
          swim: null,
          loadError: `无法加载朝代数据（${msg}）。请确认后端已启动且已导入 historical_dynasty / historical_box 数据。`,
        })
        wx.showToast({ title: '加载失败', icon: 'none' })
        return
      }
    }

    if (isDevelopEnv() && dynastyHint) {
      const fallback = tryLoadLocalMock(dynastyHint, '')
      if (fallback) {
        console.warn('[dynasty-detail] using local mock for', dynastyHint)
        const enhancedSwim = {
          ...fallback.swim,
          ...generateTimelineTicks(
            fallback.swim.startYear,
            fallback.swim.endYear,
            fallback.swim.sheetWidthRpx,
          ),
          timeScaleMode: 'linear',
        }
        applyPageData(fallback.hero, enhancedSwim)
        warnIfDegradedMock(enhancedSwim)
        return
      }
    }

    this.setData({ loadError: '缺少朝代 ID，无法加载' })
  },
  rebuildContinuationHints(swim: SwimMatrix) {
    this.continuationItems = buildContinuationItems(swim)
    this.continuationGeometryReady = false
    wx.nextTick(() => {
      if (this.pageUnloaded) return
      wx.createSelectorQuery()
        .in(this)
        .select('.dyn-panel-hscroll')
        .boundingClientRect()
        .select('.dyn-canvas')
        .boundingClientRect()
        .exec((rects: any[]) => {
          if (this.pageUnloaded) return
          const panelRect = rects?.[0]
          const canvasRect = rects?.[1]
          if (!panelRect || !canvasRect) {
            this.setData({
              continuationRightCount: 0,
              continuationBottomCount: 0,
              continuationCanvasActive: false,
            })
            return
          }
          this.continuationViewportWidthPx =
            Number(panelRect.width) || this.continuationViewportWidthPx
          this.continuationCanvasTopPx =
            this.continuationPageScrollTop + Number(canvasRect.top) - this.data.scrollTop
          this.continuationCanvasHeightPx = Number(canvasRect.height) || 0
          this.continuationGeometryReady = true
          this.updateContinuationHints(true)
        })
    })
  },
  scheduleContinuationHintUpdate() {
    const elapsed = Date.now() - this.continuationLastUpdateAt
    if (elapsed >= CONTINUATION_CUE_THROTTLE_MS) {
      this.updateContinuationHints(true)
      return
    }
    if (this.continuationUpdateTimer) clearTimeout(this.continuationUpdateTimer)
    this.continuationUpdateTimer = setTimeout(() => {
      this.continuationUpdateTimer = null
      if (this.pageUnloaded) return
      this.updateContinuationHints(true)
    }, CONTINUATION_CUE_THROTTLE_MS - elapsed)
  },
  updateContinuationHints(force = false) {
    if (this.pageUnloaded) return
    if (!this.continuationGeometryReady || !this.continuationItems.length) {
      if (
        this.data.continuationRightCount
        || this.data.continuationBottomCount
        || this.data.continuationCanvasActive
      ) {
        this.setData({
          continuationRightCount: 0,
          continuationBottomCount: 0,
          continuationCanvasActive: false,
        })
      }
      return
    }
    const now = Date.now()
    if (!force && now - this.continuationLastUpdateAt < CONTINUATION_CUE_THROTTLE_MS) {
      this.scheduleContinuationHintUpdate()
      return
    }
    this.continuationLastUpdateAt = now
    const ratio = Math.max(0.01, this.continuationRatio)
    const visibleRightRpx =
      (this.swimScrollLeft + this.continuationViewportWidthPx) / ratio
    const outerViewportHeightPx = Math.max(
      0,
      this.continuationWindowHeightPx
        - this.data.scrollTop
        - CONTINUATION_CUE_BOTTOM_RESERVE_RPX * ratio,
    )
    const visibleBottomContentPx = this.continuationPageScrollTop + outerViewportHeightPx
    const visibleBottomCanvasRpx =
      (visibleBottomContentPx - this.continuationCanvasTopPx) / ratio
    const canvasBottomPx = this.continuationCanvasTopPx + this.continuationCanvasHeightPx
    const canvasActive =
      this.continuationCanvasTopPx < visibleBottomContentPx
      && canvasBottomPx > this.continuationPageScrollTop
    const rightCount = canvasActive
      ? countOffscreenRight(
        this.continuationItems,
        visibleRightRpx,
        CONTINUATION_CUE_TOLERANCE_RPX,
      )
      : 0
    const bottomCount = canvasActive
      ? countOffscreenBottom(
        this.continuationItems,
        visibleBottomCanvasRpx,
        CONTINUATION_CUE_TOLERANCE_RPX,
      )
      : 0
    if (
      rightCount !== this.data.continuationRightCount
      || bottomCount !== this.data.continuationBottomCount
      || canvasActive !== this.data.continuationCanvasActive
    ) {
      this.setData({
        continuationRightCount: rightCount,
        continuationBottomCount: bottomCount,
        continuationCanvasActive: canvasActive,
      })
    }
  },
  scrollToAnchorYear(anchorYear: number, swim: SwimMatrix) {
    const rpxRatio = wx.getSystemInfoSync().windowWidth / 750
    const padLeftPx = (swim.canvasPadLeftRpx || CANVAS_PAD_LEFT_RPX) * rpxRatio
    const sheetPx = (swim.sheetWidthRpx || 1440) * rpxRatio
    const targetPx = padLeftPx + (percentForYearOnSwim(swim, anchorYear) / 100) * sheetPx
    const bias = wx.getSystemInfoSync().windowWidth * 0.32
    const left = Math.max(0, Math.round(targetPx - bias))
    this.swimScrollLeft = left
    this.setData({ panelScrollLeft: left, axisMirrorLeft: left })
    this.scheduleContinuationHintUpdate()
  },
  onPanelHScroll(e: { scrollLeft: number }) {
    const left = roundScrollLeft(e.scrollLeft)
    this.swimScrollLeft = left
    this.scheduleContinuationHintUpdate()
  },
  onDynastyScroll(e: WechatMiniprogram.ScrollViewScroll) {
    const top = e.detail.scrollTop
    this.continuationPageScrollTop = top
    this.scheduleContinuationHintUpdate()
    let pinned = this.data.axisPinned
    if (!pinned && top > AXIS_PIN_AT) pinned = true
    else if (pinned && top < AXIS_UNPIN_AT) pinned = false
    if (pinned !== this.data.axisPinned) {
      this.setData({
        axisPinned: pinned,
        axisMirrorLeft: this.swimScrollLeft,
      })
    }
    if (this.data.chipTooltipVisible) {
      this.hideChipTooltip()
    }
  },
  onBarTap(e: WechatMiniprogram.BaseEvent) {
    if (this.data.chipTooltipVisible) {
      this.hideChipTooltip()
      return
    }
    const ds = (e.currentTarget as any).dataset || {}
    const boxId = ds.box as string
    if (!boxId) return
    if (ds.type === 'overflow_bucket') {
      this.showBucketOverlay(ds)
      return
    }
    const title = decodeQueryValue(ds.title)
    void request(`/boxes/${encodePathSegment(boxId)}`).catch(() => {})
    navigateTo(ROUTES.boxDetail, { boxId, title })
  },
  showBucketOverlay(ds: Record<string, unknown>) {
    const laneIdx = Number(ds.lane)
    const bucketStart = Number(ds.startYear)
    const bucketEnd = Number(ds.endYear)
    const label = String(ds.label || '')
    const swim = this.data.swim
    if (!swim || Number.isNaN(laneIdx)) return
    const lane = swim.lanes[laneIdx] as SwimLane & { extraBars?: SwimBar[] }
    if (!lane) return
    let bars = lane.extraBars || []
    if (Number.isFinite(bucketStart) && Number.isFinite(bucketEnd)) {
      bars = bars.filter((bar) => {
        const y = bar.peakYear ?? bar.startYear ?? 0
        return y >= bucketStart && y < bucketEnd
      })
    }
    this.openOverlaySheet(lane, bars, label)
  },
  openOverlaySheet(lane: SwimLane & { extraBars?: SwimBar[] }, bars: SwimBar[], label = '') {
    this.setData({
      overlayVisible: true,
      overlayCountTag: buildOverlayCountTag(label || lane.label, bars.length),
      overlayBars: bars,
      overlayLaneKey: lane.key,
    })
  },
  onBarLongPress(e: WechatMiniprogram.BaseEvent) {
    const ds = (e.currentTarget as any).dataset || {}
    const boxId = ds.box as string
    if (!boxId) return
    const bar = findSwimBar(this.data.swim, boxId)
    const peakYearNum = bar?.peakYear
    const peakReason = String(bar?.peakReason || '').trim()
    const priorityReason = String(bar?.priorityReason || '').trim()
    const chipTag = String(bar?.chipTag || '').trim()
    const laneKey = String(ds.laneKey || '').trim()
    const { start: startYearLabel, end: endYearLabel } = splitTimeRangeLabels(bar, bar?.timeRange || ds.range || '')
    const sys = wx.getSystemInfoSync()
    const safeTop = computeChipTooltipSafeTop(this.data.axisPinned, this.data.scrollTop, sys.windowWidth)
    const safeBottom = computeChipTooltipSafeBottom(
      sys.windowHeight,
      sys.windowWidth,
      sys.safeAreaInsets?.bottom || 0,
    )

    const showTooltip = (rect: WechatMiniprogram.BoundingClientRectCallbackResult | null) => {
      let placement: ChipTooltipPlacement
      if (rect && rect.width > 0 && rect.height > 0) {
        placement = computeChipTooltipPlacement(rect, {
          safeTop,
          safeBottom,
          windowWidth: sys.windowWidth,
        })
      } else {
        const touch = (e as any).touches?.[0] || (e as any).changedTouches?.[0]
        const anchorY = touch?.clientY ?? Math.round(sys.windowHeight * 0.45)
        const left = touch?.clientX == null
          ? Math.round(sys.windowWidth / 2)
          : Math.max(140, Math.min(sys.windowWidth - 140, touch.clientX))
        const showAbove = anchorY - safeTop >= 120
        placement = showAbove
          ? { left, top: anchorY - 8, transform: 'translate(-50%, -100%)', origin: '50% 100%' }
          : { left, top: anchorY + 8, transform: 'translate(-50%, 0)', origin: '50% 0%' }
      }
      if (this.chipTooltipExitTimer) {
        clearTimeout(this.chipTooltipExitTimer)
        this.chipTooltipExitTimer = null
      }
      this.setData({
        chipTooltipHeldId: boxId,
        chipTooltipVisible: true,
        chipTooltipPhase: 'enter',
        chipTooltipTitle: bar?.title || ds.title || '',
        chipTooltipStartYear: startYearLabel,
        chipTooltipEndYear: endYearLabel,
        chipTooltipTag: chipTag,
        chipTooltipLaneKey: laneKey,
        chipTooltipPeakYear: peakYearNum == null ? '' : formatHistoryYear(peakYearNum),
        chipTooltipPeakReason: peakReason,
        chipTooltipPriority: formatPriorityLabel(bar?.priority || ''),
        chipTooltipPriorityReason: priorityReason,
        chipTooltipEntrySource: formatEntrySourceLabel(bar?.entrySource || ''),
        chipTooltipLeftPx: placement.left,
        chipTooltipTopPx: placement.top,
        chipTooltipBaseTransform: placement.transform,
        chipTooltipOrigin: placement.origin,
        chipTooltipTransform: chipTooltipTransformWithScale(placement.transform, 0.88),
      })
      setTimeout(() => {
        if (!this.data.chipTooltipVisible || this.data.chipTooltipHeldId !== boxId) return
        this.setData({
          chipTooltipPhase: 'idle',
          chipTooltipTransform: chipTooltipTransformWithScale(placement.transform, 1),
        })
      }, 20)
    }

    wx.createSelectorQuery()
      .in(this)
      .select(`#chip-${boxId}`)
      .boundingClientRect((rect) => showTooltip(rect))
      .exec()
  },
  showMoreOverlay(e: WechatMiniprogram.BaseEvent) {
    const label = (e.currentTarget as any).dataset.label as string
    const laneIdx = Number((e.currentTarget as any).dataset.lane)
    const swim = this.data.swim
    if (!swim) return
    const lane = swim.lanes[laneIdx] as SwimLane & { extraBars?: SwimBar[] }
    if (!lane) return
    const bars = lane.extraBars || []
    this.openOverlaySheet(lane, bars, label)
  },
  onPriorityTap(e: WechatMiniprogram.BaseEvent) {
    const priority = (e.currentTarget as any).dataset.priority as PriorityLevel
    if (!priority || priority === this.data.activePriority) return
    const swim = this.data.swim
    if (!swim) return
    const nextSwim = applyPriorityView(swim, priority)
    this.setData({
      activePriority: priority,
      swim: nextSwim,
      overlayVisible: false,
    }, () => {
      this.rebuildContinuationHints(nextSwim)
    })
    this.hideChipTooltip()
  },
  hideOverlay() {
    this.setData({ overlayVisible: false })
  },
  hideChipTooltip() {
    if (!this.data.chipTooltipVisible) return
    if (this.data.chipTooltipPhase === 'exit') return
    const baseTransform = this.data.chipTooltipBaseTransform || 'translate(-50%, -100%)'
    this.setData({
      chipTooltipPhase: 'exit',
      chipTooltipTransform: chipTooltipTransformWithScale(baseTransform, 0.88),
    })
    if (this.chipTooltipExitTimer) clearTimeout(this.chipTooltipExitTimer)
    this.chipTooltipExitTimer = setTimeout(() => {
      this.chipTooltipExitTimer = null
      if (this.data.chipTooltipPhase !== 'exit') return
      this.setData({
        chipTooltipVisible: false,
        chipTooltipHeldId: '',
        chipTooltipPhase: 'enter',
      })
    }, 190)
  },
  onChipTooltipTransitionEnd() {
    if (this.data.chipTooltipPhase !== 'exit') return
    if (this.chipTooltipExitTimer) {
      clearTimeout(this.chipTooltipExitTimer)
      this.chipTooltipExitTimer = null
    }
    this.setData({
      chipTooltipVisible: false,
      chipTooltipHeldId: '',
      chipTooltipPhase: 'enter',
    })
  },
  goUnit(e: WechatMiniprogram.BaseEvent) {
    const id = (e.currentTarget as any).dataset.id as string
    navigateTo(ROUTES.dynastyDetail, { unitId: id })
  },
  goNext() {
    const n = this.data.nextUnit
    if (!n?.unitId) return
    navigateTo(ROUTES.dynastyDetail, { unitId: n.unitId, dynasty: n.title })
  },
  openIntro() {
    if (!this.data.introCanExpand) return
    this.setData({ showIntroModal: true, introModalTitle: (this.data.dynastyTitle || '') + '·朝代简介' })
  },
  closeIntro() {
    this.setData({ showIntroModal: false })
  },
  noop() {},
  async refreshFavState() {
    const boxIds = this.data.matrixBoxIds
    if (!boxIds.length || !hasToken()) {
      this.setData({ isFav: false, favPartial: false })
      return
    }
    const favorited = await fetchFavoritedBoxIdSet()
    const st = computeUnitFavoriteState(boxIds, favorited)
    this.setData({ isFav: st.allFavorited, favPartial: st.anyFavorited && !st.allFavorited })
  },
  async onFavoriteTap() {
    if (this.data.favToggling || !hasToken()) {
      if (!hasToken()) promptLoginForFavorite()
      return
    }
    const boxIds = this.data.matrixBoxIds
    if (!boxIds.length) {
      wx.showToast({ title: '当前朝代暂无史略可收藏', icon: 'none' })
      return
    }
    const favorited = await fetchFavoritedBoxIdSet()
    const st = computeUnitFavoriteState(boxIds, favorited)
    const nextFav = !st.allFavorited
    this.setData({ favToggling: true })
    try {
      await setBoxesFavorited(boxIds, nextFav)
      await this.refreshFavState()
      wx.showToast({ title: nextFav ? '已收藏本朝史略' : '已取消收藏', icon: 'success' })
    } catch (e: unknown) {
      wx.showToast({ title: e instanceof Error ? e.message : '操作失败', icon: 'none' })
    } finally {
      this.setData({ favToggling: false })
    }
  },
  onShareTap() {
    promptContentShareUnavailable()
  },
})
