import { hasToken, request } from '../../native-utils/api'
import { encodePathSegment } from '../../native-utils/encode-path-segment'
import {
  favoriteUnit,
  fetchFavoritedUnitIdSet,
  promptLoginForUnitFavorite,
  unfavoriteUnit,
} from '../../native-utils/favorite-unit'
import { ROUTES, navigateTo } from '../../native-utils/router'
import { decodeQueryValue } from '../../native-utils/query-value'
import { formatHistoryYear, formatHistoryYearToken } from '../../native-utils/year-format'
import { formatDetailSourceLabel, formatEntrySourceLabel } from '../../native-utils/entry-source-label'
import { buildSharePosterSheetState } from '../../native-utils/share-poster-open'
import { resolveSelectionBarAnchor } from '../../native-utils/selection-bar-position'
import {
  parseCivilizationFromCrumb,
  requireLoginForCorrection,
  submitCorrection,
} from '../../native-utils/correction'
import {
  formatApiErrorDetail,
  formatApiRequestError,
  formatDynastyLoadError,
  formatEmptySwimError,
  formatUserFacingError,
} from '../../native-utils/load-error-message'
import {
  isCivSwitchEnabled,
  isHuaxiaUnitId,
  loadFeatureFlags,
  toastCivLocked,
} from '../../native-utils/feature-flags'
import { resolveDetailUnitIds } from '../home/matrix-adapter'
import { isDevtoolsClient, isDevelopEnv } from '../../native-utils/runtime-env'
import {
  countOffscreenBottom,
  countOffscreenRight,
  dedupeHintItems,
  type OffscreenHintItem,
} from '../../native-utils/offscreen-hints'
import { categoryRailColor } from '../../native-utils/chip-badge-tokens'
import { PRD_CATEGORY_KEYS } from '../../native-utils/format'
const {
  buildSwimMatrixFromMock,
  buildHeroFromMock,
  normalizeDynastyKey,
  isDegradedMockFallback,
} = require('./swim-local-fallback')

type PriorityLevel = 'p0' | 'p1' | 'p2' | 'p3'

const PRIORITY_OPTIONS: { value: PriorityLevel; label: string }[] = [
  { value: 'p0', label: '极简' },
  { value: 'p1', label: '简略' },
  { value: 'p2', label: '丰富' },
  { value: 'p3', label: '详尽' },
]

function priorityLabel(priority: PriorityLevel): string {
  const hit = PRIORITY_OPTIONS.find((item) => item.value === priority)
  return hit?.label || '详尽'
}

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
/** 时间轴行 / 吸顶占位块高度（与 dyn-panel-axis-spacer 一致） */
const PANEL_AXIS_BLOCK_RPX = 86
/** 外框吸顶解绑滞后（px），仅防临界抖动，不能大到露出「过冲再弹回」 */
const AXIS_PIN_HYSTERESIS_PX = 2
const CONTINUATION_CUE_THROTTLE_MS = 120
const CONTINUATION_CUE_TOLERANCE_RPX = 16
const CONTINUATION_CUE_BOTTOM_RESERVE_RPX = 48

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
/** 与后端 UnitSwimMatrixService 一致：君王/诸侯锚定在在位起始年 */
const ANCHOR_AT_START_LANE_KEYS = new Set(['junji', 'zhuhou'])

function parseBucketMemberCount(title: string): number {
  const match = String(title || '').match(/\+(\d+)$/)
  return match ? Number(match[1]) : 0
}

function bucketTitle(laneLabel: string, count: number): string {
  return BUCKET_CHIP_TITLE
}

function usesAnchorAtStart(laneKey?: string): boolean {
  return ANCHOR_AT_START_LANE_KEYS.has(String(laneKey || '').trim())
}

function anchorYearOfBar(bar: Pick<SwimBar, 'startYear' | 'peakYear'>, laneKey?: string): number {
  if (usesAnchorAtStart(laneKey)) {
    if (typeof bar.startYear === 'number') return bar.startYear
    if (typeof bar.peakYear === 'number') return bar.peakYear
    return 0
  }
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
  let bucketRowIndex = -1

  let cursor = startYear
  let bucketIndex = 0
  while (cursor < endYear) {
    const bucketEnd = Math.min(endYear, cursor + bucketYears)
    const members = overflow.filter((bar) => {
      const y = anchorYearOfBar(bar, laneKey)
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
      if (bucketRowIndex === -1) {
        for (let rowIndex = 0; rowIndex < nextRows.length; rowIndex++) {
          if (rowEnds[rowIndex] + gapPct <= bucketBar._leftPct) {
            assigned = rowIndex
            rowEnds[rowIndex] = bucketBar._rightPct
            nextRows[rowIndex] = [...nextRows[rowIndex], bucketBar].sort((a, b) => a._leftPct - b._leftPct)
            break
          }
        }
      } else if (rowEnds[bucketRowIndex] + gapPct <= bucketBar._leftPct) {
        assigned = bucketRowIndex
        rowEnds[bucketRowIndex] = bucketBar._rightPct
        nextRows[bucketRowIndex] = [...nextRows[bucketRowIndex], bucketBar]
          .sort((a, b) => a._leftPct - b._leftPct)
      }
      if (assigned === -1) {
        if (bucketRowIndex === -1) {
          bucketRowIndex = nextRows.length
          nextRows.push([bucketBar])
          rowEnds.push(bucketBar._rightPct)
        } else {
          rowEnds[bucketRowIndex] = Math.max(rowEnds[bucketRowIndex], bucketBar._rightPct)
          nextRows[bucketRowIndex] = [...nextRows[bucketRowIndex], bucketBar]
            .sort((a, b) => a._leftPct - b._leftPct)
        }
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
  detailSource?: string
  civilizationName?: string
  dynastyName?: string
  regimeName?: string
  emperorName?: string
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
  concurrentTabs?: ConcurrentTab[]
  sheetWidthRpx: number
  canvasHeightRpx?: number
  panelSheetHeightRpx?: number
  canvasPadLeftRpx?: number
  canvasWidthRpx?: number
  categoryBands?: CategoryBand[]
}

type ConcurrentTab = {
  label: string
  civilizationName: string
  dynastyId: string
}

function parseConcurrentLabel(label: string): { civ: string; title: string } {
  const sep = label.indexOf('·')
  if (sep < 0) return { civ: '', title: String(label || '').trim() }
  return { civ: label.slice(0, sep).trim(), title: label.slice(sep + 1).trim() }
}

function isHuaxiaCivName(civ: string): boolean {
  return String(civ || '').trim() === '华夏'
}

function resolveConcurrentTabs(
  swim: SwimMatrix,
  currentUnitId: string,
  heroCivLine: string,
  dynastyTitle: string,
): ConcurrentTab[] {
  if (swim.concurrentTabs?.length) return swim.concurrentTabs
  const selfLabel = `${heroCivLine || '华夏'}·${dynastyTitle}`
  return (swim.concurrentItems || []).map((label) => {
    const parsed = parseConcurrentLabel(label)
    const civ = parsed.civ || heroCivLine || '华夏'
    const title = parsed.title || label
    const isSelf = label === selfLabel || (civ === heroCivLine && title === dynastyTitle)
    const dynastyId = isSelf
      ? currentUnitId
      : (resolveDetailUnitIds('', title)[0] || '')
    return { label, civilizationName: civ, dynastyId }
  })
}

function resolveActiveConcurrentIndex(
  tabs: ConcurrentTab[],
  unitId: string,
  selfLabel: string,
): number {
  const byId = tabs.findIndex((tab) => tab.dynastyId && tab.dynastyId === unitId)
  if (byId >= 0) return byId
  const byLabel = tabs.findIndex((tab) => tab.label === selfLabel)
  if (byLabel >= 0) return byLabel
  return 0
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

function slimSwimMatrixForView(swim: SwimMatrix): SwimMatrix {
  return {
    ...swim,
    lanes: (swim.lanes || []).map((lane) => {
      const { priorityViews, ...rest } = lane
      return rest
    }),
  }
}

function warnIfDegradedMock(swim: SwimMatrix) {
  if (!isDegradedMockFallback(swim)) return
  wx.showToast({
    title: '朝代数据加载失败，仅显示本地君王数据',
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

  // 泳道网格线：与时间轴刻度对齐，起点/终点也各自补一条，避免边界处刻度与网格线脱节
  const gridLines = [
    { left: '0%' },
    ...ticks.filter(t => t.left !== '0%').map(t => ({ left: t.left })),
    { left: '100%' },
  ]

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

function formatCoordinateLabel(raw: unknown): string {
  return String(raw ?? '').trim()
}

function formatCoordinatePath(bar: SwimBar | null | undefined): string {
  return [
    formatCoordinateLabel(bar?.civilizationName),
    formatCoordinateLabel(bar?.dynastyName),
    formatCoordinateLabel(bar?.regimeName),
    formatCoordinateLabel(bar?.emperorName),
  ]
    .filter(Boolean)
    .join('・')
}

function formatPeakSummary(year: string, reason: string): string {
  const y = String(year ?? '').trim()
  const r = String(reason ?? '').trim()
  if (y && r) return `${y}，${r}`
  return y || r
}

function splitTimeRangeLabels(bar: SwimBar | null, fallbackRange: string): { start: string; end: string } {
  if (bar?.startYear != null && bar?.endYear != null) {
    return {
      start: formatHistoryYear(bar.startYear),
      end: formatHistoryYear(bar.endYear),
    }
  }
  const parts = String(fallbackRange || '').split(/\s*[—–]\s*/)
  if (parts.length >= 2) {
    return {
      start: formatHistoryYearToken(parts[0]),
      end: formatHistoryYearToken(parts[parts.length - 1]),
    }
  }
  const single = formatHistoryYearToken(String(fallbackRange || '').trim())
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
  if ((lane.totalCount ?? 0) > 0) return true
  if ((lane.visibleCount ?? 0) > 0) return true
  const rows = lane.collapsedRows || []
  return rows.some((row) => (row || []).length > 0)
}

function orderSwimLanes(lanes: SwimLane[]): SwimLane[] {
  const byKey = new Map(lanes.map((lane) => [lane.key, lane]))
  return PRD_CATEGORY_KEYS
    .map((key) => byKey.get(key))
    .filter((lane): lane is SwimLane => !!lane)
}

function resolveCanvasHeightRpx(categoryBands: CategoryBand[]): number {
  if (!categoryBands.length) {
    return snapRpx(MIN_BAND_HEIGHT_RPX + BAND_PAD_RPX * 2)
  }
  const last = categoryBands[categoryBands.length - 1]
  return snapRpx(last.topRpx + last.heightRpx + BAND_PAD_RPX)
}

function composeCanvasLayout(swim: SwimMatrix, lanes: SwimLane[]): SwimMatrix {
  const categoryBands: CategoryBand[] = []
  const canvasLanes: SwimLane[] = []
  let cursor = BAND_PAD_RPX
  const sheetWidthRpx = swim.sheetWidthRpx || 1440
  const visibleLanes = orderSwimLanes(lanes)

  for (const lane of visibleLanes) {
    const contentRows = lane.collapsedRows || []
    const hasRows = contentRows.some((row) => (row || []).length > 0)
    const rowCount = Math.max(1, hasRows ? contentRows.length : 1)
    const trackHeight = snapRpx(
      LANE_TRACK_PAD_VERTICAL_RPX + rowCount * CHIP_HEIGHT_RPX + (rowCount - 1) * ROW_GAP_RPX,
    )
    const bandHeight = Math.max(MIN_BAND_HEIGHT_RPX, trackHeight)

    const canvasRows: SwimBar[][] = []
    if (hasRows) {
      contentRows.forEach((row, rowIndex) => {
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
    } else {
      canvasRows.push([])
    }

    categoryBands.push({
      key: lane.key,
      label: lane.label,
      // 类目色固定映射（视觉规范 v3）：前端为准，覆盖后端旧色值
      borderColor: categoryRailColor(lane.key, lane.borderColor),
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

  const canvasHeightRpx = resolveCanvasHeightRpx(categoryBands)
  const panelSheetHeightRpx = snapRpx(PANEL_AXIS_BLOCK_RPX + canvasHeightRpx)

  return {
    ...swim,
    lanes: canvasLanes,
    categoryBands,
    canvasHeightRpx,
    panelSheetHeightRpx,
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

function isOverflowBucketBar(bar: SwimBar): boolean {
  return bar.type === 'overflow_bucket'
}

function normalizeLegacyLane(
  lane: SwimLane,
  sheetWidthRpx: number,
  priority: PriorityLevel,
  swim: SwimMatrix,
): SwimLane {
  const allBars = [...(lane.collapsedRows || []).flat(), ...(lane.extraBars || [])]
    .filter((bar) => !isOverflowBucketBar(bar))
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
    totalCount: lane.totalCount ?? individualCount + bucketCount,
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
  // 吸顶条无顶 padding，高度≈外框 70rpx + 底 padding 12rpx
  const axisHeightPx = axisPinned ? rpxToPx(PANEL_AXIS_BLOCK_RPX, windowWidth) : 0
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

function heroCivilizationLine(crumbText: string): string {
  const normalized = String(crumbText || '').trim().replace(/[·・]/g, ' · ')
  const civ = parseCivilizationFromCrumb(normalized)
  if (civ) return civ
  return normalized.split(' · ')[0]?.trim() || ''
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
  swimSource: null as SwimMatrix | null,
  pageUnloaded: false,
  _loadQuery: null as Record<string, string | undefined> | null,
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
  /** 外框顶边对齐吸顶线时的 page scrollTop；<0 表示尚未测得 */
  axisPinOffsetPx: -1,
  axisPinMeasureTimer: null as ReturnType<typeof setTimeout> | null,
  data: {
    unit: null as UnitHero['unit'] | null,
    dynastyTitle: '',
    navTitle: '',
    heroSubLine: '',
    heroCivLine: '',
    swim: null as SwimMatrix | null,
    concurrentItems: [] as string[],
    concurrentTabs: [] as ConcurrentTab[],
    activeConcurrentIndex: 0,
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
    loadErrorDetail: '',
    loading: true,
    priorityOptions: PRIORITY_OPTIONS,
    activePriority: 'p3' as PriorityLevel,
    activePriorityLabel: priorityLabel('p3'),
    priorityMenuVisible: false,
    priorityMenuTopPx: 0,
    priorityMenuRightPx: 24,
    chipTooltipVisible: false,
    chipTooltipPhase: 'enter' as 'enter' | 'idle' | 'exit',
    chipTooltipHeldId: '',
    chipTooltipTitle: '',
    chipTooltipRange: '',
    chipTooltipTag: '',
    chipTooltipPeakSummary: '',
    chipTooltipPriority: '',
    chipTooltipPrioritySummary: '',
    chipTooltipEntrySource: '',
    chipTooltipDetailSource: '',
    chipTooltipCoordinate: '',
    chipTooltipLaneKey: '',
    chipTooltipStartYear: '',
    chipTooltipEndYear: '',
    chipTooltipReignLabel: '',
    chipTooltipLeftPx: 0,
    chipTooltipTopPx: 0,
    chipTooltipBaseTransform: 'translate(-50%, -100%)',
    chipTooltipOrigin: '50% 100%',
    chipTooltipTransform: 'translate(-50%, -100%) scale(0.88)',
    correctionVisible: false,
    dictionaryVisible: false,
    dictionaryQuery: '',
    correctionSubmitting: false,
    correctionBoxId: '',
    correctionBoxTitle: '',
    correctionCivilizationName: '',
    correctionDynastyName: '',
    selectionBarVisible: false,
    selectionBarLeft: 0,
    selectionBarTop: 0,
    selectionBarPlacement: 'above' as 'above' | 'below',
    selectionBarText: '',
    selectionMountKey: 1,
    sharePosterVisible: false,
    sharePosterQuote: '',
    sharePosterSourceLine1: '',
    sharePosterSourceLine2: '',
    sharePosterUserName: '历史读者',
    sharePosterUserAvatar: '',
    sharePosterExcerptDate: '',
    civSwitchEnabled: true,
  },
  onShow() {
    void this.refreshFavState()
  },
  onUnload() {
    this.pageUnloaded = true
    this.swimSource = null
    if (this.continuationUpdateTimer) clearTimeout(this.continuationUpdateTimer)
    if (this.chipTooltipExitTimer) clearTimeout(this.chipTooltipExitTimer)
    if (this.axisPinMeasureTimer) clearTimeout(this.axisPinMeasureTimer)
  },
  onShareAppMessage() {
    const u = this.data.unit
    const t = this.data.dynastyTitle || u?.name || '朝代详情'
    const id = u?.id
    const path = id ? `/pages/dynasty-detail/index?unitId=${encodeURIComponent(id)}` : '/pages/dynasty-detail/index'
    return { title: t, path }
  },
  async onLoad(query: Record<string, string | undefined>) {
    this._loadQuery = query
    await loadFeatureFlags()
    await this.loadDynastyPage(query)
  },
  async retryLoad() {
    if (!this._loadQuery) return
    this.setData({ loading: true, loadError: '', loadErrorDetail: '' })
    await this.loadDynastyPage(this._loadQuery)
  },
  copyLoadError() {
    const text = this.data.loadErrorDetail || this.data.loadError
    if (!text) return
    wx.setClipboardData({
      data: text,
      success: () => wx.showToast({ title: '已复制错误信息', icon: 'success' }),
    })
  },
  async loadDynastyPage(query: Record<string, string | undefined>) {
    const rawUnitId = query.unitId || query.id || ''
    const dynastyHint = decodeQueryValue(query.dynasty || query.displayName || '')
    const unitCandidates = resolveDetailUnitIds(rawUnitId, dynastyHint)
    const civSwitchEnabled = isCivSwitchEnabled()
    this.setData({ civSwitchEnabled })

    if (!civSwitchEnabled) {
      const idsToCheck = unitCandidates.length
        ? unitCandidates
        : (rawUnitId ? [rawUnitId] : [])
      const blocked = idsToCheck.some((id) => id && !isHuaxiaUnitId(id))
      if (blocked) {
        toastCivLocked()
        this.setData({ loading: false, loadError: '该内容筹备中，敬请期待' })
        setTimeout(() => wx.navigateBack(), 1200)
        return
      }
    }

    if (!unitCandidates.length && !dynastyHint) {
      this.setData({ loading: false, loadError: '缺少朝代参数，无法加载' })
      return
    }

    const sys = wx.getSystemInfoSync()
    const navH = Math.round(88 * (sys.windowWidth / 750))
    const headerPadPx = (sys.statusBarHeight || 20) + navH
    const tabBarH = Math.round(72 * (sys.windowWidth / 750))
    // 有并发 Tab 时吸顶线 = Tab 底；无 Tab 时 = 导航底（不再预留空白）
    const scrollTop = headerPadPx
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
      loading: true,
      loadError: '',
      loadErrorDetail: '',
    })

    const finishLoading = (patch: Record<string, unknown>) => {
      this.setData({ ...patch, loading: false })
    }

    const applyPageData = (
      hero: UnitHero,
      swim: SwimMatrix,
    ) => {
      try {
        const unit = hero.unit
        const dynastyTitle = (unit.dynastyName && unit.dynastyName.trim()) || unit.name
        const navTitle = dynastyTitle.length <= 4 ? dynastyTitle : dynastyTitle.slice(0, 4)
        const heroSubLine = `${formatHistoryYear(unit.startYear)}–${formatHistoryYear(unit.endYear)}`
        const heroCivLine = heroCivilizationLine(unit.crumbText)
        const activePriority = this.data.activePriority || 'p3'
        this.swimSource = swim
        const prioritySwim = applyPriorityView(swim, activePriority)
        const swimForView = slimSwimMatrixForView(prioritySwim)
        const matrixBoxIds = collectMatrixBoxIds(swim)
        const hasVisibleContent = (prioritySwim.lanes || []).some(hasLaneContent)
        const { preview, canExpand, paragraphs } = previewIntro(unit.summary || '')
        const concurrentTabs = resolveConcurrentTabs(prioritySwim, unit.id, heroCivLine, dynastyTitle)
        const selfConcurrentLabel = `${heroCivLine || '华夏'}·${dynastyTitle}`
        const activeConcurrentIndex = resolveActiveConcurrentIndex(concurrentTabs, unit.id, selfConcurrentLabel)
        const concurrentItems = concurrentTabs.map((tab) => tab.label)
        const contentTopPx = headerPadPx + (concurrentTabs.length > 0 ? tabBarH : 0)
        this.axisPinOffsetPx = -1
        if (!hasVisibleContent) {
          finishLoading({
            unit,
            dynastyTitle,
            navTitle,
            heroSubLine,
            heroCivLine,
            swim: null,
            concurrentItems: [],
            concurrentTabs: [],
            activeConcurrentIndex: 0,
            relatedUnits: hero.relatedUnits || [],
            nextUnit: hero.nextUnit ?? null,
            matrixBoxIds: [],
            headerPadPx,
            scrollTop: headerPadPx,
            introPreview: preview,
            introDisplay: preview,
            introCanExpand: canExpand,
            introParagraphs: paragraphs,
            loadError: formatEmptySwimError(isDevelopEnv()),
            loadErrorDetail: '',
          })
          return
        }
        this.setData({
          unit,
          dynastyTitle,
          navTitle,
          heroSubLine,
          heroCivLine,
          swim: swimForView,
          concurrentItems,
          concurrentTabs,
          activeConcurrentIndex,
          relatedUnits: hero.relatedUnits || [],
          nextUnit: hero.nextUnit ?? null,
          matrixBoxIds,
          headerPadPx,
          scrollTop: contentTopPx,
          axisPinned: false,
          axisMirrorLeft: 0,
          introPreview: preview,
          introDisplay: preview,
          introCanExpand: canExpand,
          introParagraphs: paragraphs,
          loadError: '',
          loadErrorDetail: '',
          loading: false,
        }, () => {
          this.rebuildContinuationHints(prioritySwim)
          this.scheduleMeasureAxisPinOffset()
        })
        void this.refreshFavState()
        if (!Number.isNaN(anchorYear)) {
          setTimeout(() => this.scrollToAnchorYear(anchorYear, swim), 120)
        }
      } catch (processErr: unknown) {
        throw processErr instanceof Error ? processErr : new Error(String(processErr))
      }
    }

    const tryApplyLocalMock = (mockHint: string, resolvedUnitId: string) => {
      if (!isDevtoolsClient()) return false
      const fallback = tryLoadLocalMock(mockHint, resolvedUnitId)
      if (!fallback) return false
      console.warn('[dynasty-detail] using local mock for', mockHint)
      const enhancedSwim = {
        ...fallback.swim,
        ...generateTimelineTicks(
          fallback.swim.startYear,
          fallback.swim.endYear,
          fallback.swim.sheetWidthRpx,
        ),
        timeScaleMode: 'linear' as const,
      }
      applyPageData(fallback.hero, enhancedSwim)
      warnIfDegradedMock(enhancedSwim)
      return true
    }

    let resolvedMockHint = dynastyHint
    let lastError: unknown = null
    const triedIds = unitCandidates.length ? unitCandidates : ['']

    for (const candidateId of triedIds) {
      if (!candidateId) continue
      try {
        const enc = encodePathSegment(candidateId)
        const heroRes = await request<UnitHero>(`/units/${enc}`)
        resolvedMockHint =
          dynastyHint ||
          heroRes.data.unit.dynastyName?.trim() ||
          heroRes.data.unit.name?.trim() ||
          ''
        try {
          const swimRes = await request<SwimMatrix>(`/units/${enc}/swim-matrix`)
          applyPageData(heroRes.data, {
            ...swimRes.data,
            gridLines: swimRes.data.gridLines || [],
          })
          return
        } catch (swimErr: unknown) {
          console.error('[dynasty-detail] swim-matrix failed', candidateId, swimErr)
          lastError = swimErr
          if (isDevtoolsClient() && resolvedMockHint && tryApplyLocalMock(resolvedMockHint, candidateId)) {
            return
          }
        }
      } catch (e: unknown) {
        console.error('[dynasty-detail] API failed', candidateId, e)
        lastError = e
      }
    }

    if (isDevtoolsClient() && dynastyHint && tryApplyLocalMock(dynastyHint, rawUnitId || triedIds[0] || '')) {
      return
    }

    const detail = formatApiErrorDetail(lastError, {
      unitId: rawUnitId,
      candidates: triedIds.join(', '),
      dynasty: dynastyHint,
    })
    finishLoading({
      unit: null,
      swim: null,
      loadError: formatDynastyLoadError(lastError, isDevelopEnv()),
      loadErrorDetail: detail,
    })
    wx.showToast({ title: '加载失败', icon: 'none' })
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
  /**
   * 测量时间轴外框（.dyn-axis-pin-anchor）顶边相对 scroll-view 内容顶端的偏移。
   * 吸顶条件：pageScrollTop >= 该偏移（外框碰到 Tab/导航底）。
   */
  measureAxisPinOffset() {
    if (this.pageUnloaded || !this.data.swim) return
    wx.createSelectorQuery()
      .in(this)
      .select('.dynasty-scroll')
      .boundingClientRect()
      .select('.dyn-axis-pin-anchor')
      .boundingClientRect()
      .select('.dynasty-scroll')
      .scrollOffset()
      .exec((rects: any[]) => {
        if (this.pageUnloaded) return
        const scrollRect = rects?.[0]
        const anchorRect = rects?.[1]
        const scrollOffset = rects?.[2]
        if (!scrollRect || !anchorRect || !scrollOffset) return
        const offset = Math.max(
          0,
          Math.round(
            Number(scrollOffset.scrollTop || 0) +
              Number(anchorRect.top) -
              Number(scrollRect.top),
          ),
        )
        if (offset === this.axisPinOffsetPx) {
          this.applyAxisPinForScroll(this.continuationPageScrollTop)
          return
        }
        this.axisPinOffsetPx = offset
        this.applyAxisPinForScroll(this.continuationPageScrollTop)
      })
  },
  scheduleMeasureAxisPinOffset() {
    if (this.pageUnloaded) return
    wx.nextTick(() => {
      if (this.pageUnloaded) return
      this.measureAxisPinOffset()
    })
    if (this.axisPinMeasureTimer) clearTimeout(this.axisPinMeasureTimer)
    // 英雄区/字体二次布局后再测一次，避免阈值偏大导致外框钻进 Tab 后才钉住
    this.axisPinMeasureTimer = setTimeout(() => {
      this.axisPinMeasureTimer = null
      this.measureAxisPinOffset()
    }, 120)
  },
  applyAxisPinForScroll(top: number) {
    const offset = this.axisPinOffsetPx
    if (offset < 0) return
    let pinned = this.data.axisPinned
    if (!pinned && top >= offset) pinned = true
    else if (pinned && top < offset - AXIS_PIN_HYSTERESIS_PX) pinned = false
    if (pinned !== this.data.axisPinned) {
      this.setData({
        axisPinned: pinned,
        axisMirrorLeft: this.swimScrollLeft,
      })
    }
  },
  onDynastyScroll(e: WechatMiniprogram.ScrollViewScroll) {
    const top = e.detail.scrollTop
    this.continuationPageScrollTop = top
    this.scheduleContinuationHintUpdate()
    this.applyAxisPinForScroll(top)
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
        const y = anchorYearOfBar(bar, lane.key)
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
        chipTooltipReignLabel: (laneKey === 'junji' || laneKey === 'zhuhou') ? '在位' : '',
        chipTooltipTag: chipTag,
        chipTooltipLaneKey: laneKey,
        chipTooltipPeakSummary: formatPeakSummary(
          peakYearNum == null ? '' : formatHistoryYear(peakYearNum),
          peakReason,
        ),
        chipTooltipPriority: formatPriorityLabel(bar?.priority || ''),
        chipTooltipPrioritySummary: formatPeakSummary(
          formatPriorityLabel(bar?.priority || ''),
          priorityReason,
        ),
        chipTooltipEntrySource: formatEntrySourceLabel(bar?.entrySource || ''),
        chipTooltipDetailSource: formatDetailSourceLabel(bar?.detailSource || ''),
        chipTooltipCoordinate: formatCoordinatePath(bar),
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
    const ds = (e.currentTarget as WechatMiniprogram.IAnyObject).dataset as { priority?: string }
    const priority = String(ds.priority || '').trim() as PriorityLevel
    if (!priority || !PRIORITY_OPTIONS.some((item) => item.value === priority)) return
    if (priority === this.data.activePriority) {
      this.setData({ priorityMenuVisible: false })
      return
    }
    const swim = this.swimSource
    if (!swim) return
    const nextSwim = applyPriorityView(swim, priority)
    this.setData({
      activePriority: priority,
      activePriorityLabel: priorityLabel(priority),
      priorityMenuVisible: false,
      swim: slimSwimMatrixForView(nextSwim),
      overlayVisible: false,
    }, () => {
      this.rebuildContinuationHints(nextSwim)
    })
    this.hideChipTooltip()
  },
  togglePriorityMenu() {
    const nextOpen = !this.data.priorityMenuVisible
    if (!nextOpen) {
      this.setData({ priorityMenuVisible: false })
      return
    }
    this.hideChipTooltip()
    wx.createSelectorQuery()
      .in(this)
      .select('.unit-hero-priority-wrap')
      .boundingClientRect()
      .exec((res) => {
        const rect = res?.[0] as WechatMiniprogram.BoundingClientRectCallbackResult | undefined
        const sys = wx.getSystemInfoSync()
        const top = rect ? Math.round(rect.bottom + 4) : this.data.scrollTop + 100
        const right = rect ? Math.max(8, Math.round(sys.windowWidth - rect.right)) : 24
        this.setData({
          priorityMenuVisible: true,
          priorityMenuTopPx: top,
          priorityMenuRightPx: right,
        })
      })
  },
  closePriorityMenu() {
    if (this.data.priorityMenuVisible) {
      this.setData({ priorityMenuVisible: false })
    }
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
    const ds = (e.currentTarget as WechatMiniprogram.IAnyObject).dataset as {
      id: string
      dynasty?: string
    }
    navigateTo(ROUTES.dynastyDetail, {
      unitId: ds.id,
      dynasty: ds.dynasty || '',
    })
  },
  onConcurrentTabTap(e: WechatMiniprogram.BaseEvent) {
    const index = Number((e.currentTarget as WechatMiniprogram.IAnyObject).dataset?.index)
    if (!Number.isFinite(index) || index < 0) return
    if (index === this.data.activeConcurrentIndex) return

    const tab = this.data.concurrentTabs[index]
    if (!tab) return

    const isHuaxia = isHuaxiaCivName(tab.civilizationName) || isHuaxiaUnitId(tab.dynastyId)
    if (!isCivSwitchEnabled() && !isHuaxia) {
      toastCivLocked()
      return
    }

    const { title } = parseConcurrentLabel(tab.label)
    const targetId = tab.dynastyId || resolveDetailUnitIds('', title)[0] || ''
    if (!targetId) {
      wx.showToast({ title: '暂未收录该朝代', icon: 'none' })
      return
    }
    if (!isCivSwitchEnabled() && !isHuaxiaUnitId(targetId)) {
      toastCivLocked()
      return
    }

    navigateTo(ROUTES.dynastyDetail, {
      unitId: targetId,
      dynasty: title,
    })
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
    const unitId = String(this.data.unit?.id || '').trim()
    if (!unitId || !hasToken()) {
      this.setData({ isFav: false, favPartial: false })
      return
    }
    const favorited = await fetchFavoritedUnitIdSet()
    this.setData({ isFav: favorited.has(unitId), favPartial: false })
  },
  async onFavoriteTap() {
    if (this.data.favToggling || !hasToken()) {
      if (!hasToken()) promptLoginForUnitFavorite()
      return
    }
    const unitId = String(this.data.unit?.id || '').trim()
    if (!unitId) {
      wx.showToast({ title: '当前朝代无法收藏', icon: 'none' })
      return
    }
    const nextFav = !this.data.isFav
    this.setData({ favToggling: true })
    try {
      if (nextFav) {
        await favoriteUnit(unitId)
      } else {
        await unfavoriteUnit(unitId)
      }
      await this.refreshFavState()
      wx.showToast({ title: nextFav ? '已收藏本朝' : '已取消收藏', icon: 'success' })
    } catch (e: unknown) {
      wx.showToast({
        title: formatApiRequestError(e) || formatUserFacingError(e, isDevelopEnv(), '收藏失败，请稍后重试'),
        icon: 'none',
      })
    } finally {
      this.setData({ favToggling: false })
    }
  },
  hideSelectionBar() {
    this.setData({
      selectionBarVisible: false,
      selectionBarText: '',
    })
    this.clearDetailSelection()
  },
  clearDetailSelection() {
    for (const selector of ['#dynastyIntroSelection', '#dynastyModalSelection']) {
      wx.createSelectorQuery()
        .in(this)
        .select(selector)
        .context((res) => {
          const ctx = (res as WechatMiniprogram.IAnyObject)?.context as { removeSelection?: () => void } | null
          ctx?.removeSelection?.()
        })
        .exec()
    }
  },
  onDetailSelectionChange(e: WechatMiniprogram.CustomEvent) {
    const detail = (e.detail || {}) as {
      isCollapsed?: boolean
      selectedString?: string
      firstRangeRect?: { left?: number; top?: number; width?: number; height?: number }
    }
    const selected = String(detail.selectedString || '').trim()
    if (detail.isCollapsed || !selected) {
      this.hideSelectionBar()
      return
    }
    const anchor = resolveSelectionBarAnchor(detail.firstRangeRect, {
      left: this.data.selectionBarLeft,
      top: this.data.selectionBarTop,
      placement: this.data.selectionBarPlacement,
    })
    this.setData({
      selectionBarVisible: true,
      selectionBarText: selected,
      selectionBarLeft: anchor.left,
      selectionBarTop: anchor.top,
      selectionBarPlacement: anchor.placement,
    })
  },
  async onSelectionShare() {
    const text = this.data.selectionBarText
    this.hideSelectionBar()
    if (!text) return
    wx.showLoading({ title: '生成海报…', mask: true })
    try {
      const dynastyTitle = this.data.dynastyTitle || '朝代'
      const unit = this.data.unit
      const civ = unit ? parseCivilizationFromCrumb(unit.crumbText) : ''
      const sourceLine1 = `/${[civ, dynastyTitle, '朝代简介'].filter(Boolean).join('・')}`
      const posterState = await buildSharePosterSheetState(text, sourceLine1, '')
      this.setData(posterState)
    } catch {
      wx.hideLoading()
      wx.showToast({ title: '海报生成失败', icon: 'none' })
    }
  },
  closeSharePoster() {
    wx.hideLoading()
    this.setData({ sharePosterVisible: false })
  },
  onSelectionCopy() {
    const text = this.data.selectionBarText
    this.hideSelectionBar()
    if (!text) return
    wx.setClipboardData({
      data: text,
      success: () => wx.showToast({ title: '已复制', icon: 'success' }),
    })
  },
  onSelectionQuery() {
    const text = this.data.selectionBarText
    this.hideSelectionBar()
    if (!text) return
    this.clearDetailSelection()
    this.setData({
      dictionaryVisible: true,
      dictionaryQuery: text,
    })
  },
  closeDictionary() {
    this.setData({ dictionaryVisible: false, dictionaryQuery: '' })
    this.clearDetailSelection()
  },
  onSelectionCorrection() {
    const text = this.data.selectionBarText
    this.hideSelectionBar()
    if (!text) return
    requireLoginForCorrection(() => {
      const unit = this.data.unit
      const civilizationName = unit ? parseCivilizationFromCrumb(unit.crumbText) : ''
      this.setData({
        correctionVisible: true,
        correctionSubmitting: false,
        correctionBoxId: this.data.matrixBoxIds[0] || '',
        correctionBoxTitle: `${this.data.dynastyTitle} · 朝代简介`,
        correctionCivilizationName: civilizationName,
        correctionDynastyName: this.data.dynastyTitle,
      })
    })
  },
  onChipTooltipCardTap() {},
  onChipCorrectionTap() {
    const boxId = this.data.chipTooltipHeldId
    if (!boxId) return
    requireLoginForCorrection(() => {
      const unit = this.data.unit
      const civilizationName = unit ? parseCivilizationFromCrumb(unit.crumbText) : ''
      this.setData({
        chipTooltipVisible: false,
        chipTooltipHeldId: '',
        correctionVisible: true,
        correctionSubmitting: false,
        correctionBoxId: boxId,
        correctionBoxTitle: this.data.chipTooltipTitle,
        correctionCivilizationName: civilizationName,
        correctionDynastyName: this.data.dynastyTitle,
      })
    })
  },
  closeCorrection() {
    this.setData({ correctionVisible: false, correctionSubmitting: false })
  },
  async onCorrectionSubmit(e: WechatMiniprogram.CustomEvent) {
    const reason = String((e.detail as { reason?: string })?.reason || '')
    const boxId = this.data.correctionBoxId
    if (!boxId || this.data.correctionSubmitting) return
    this.setData({ correctionSubmitting: true })
    try {
      await submitCorrection({
        boxId,
        sourceType: 'dynasty_canvas',
        reason,
      })
      wx.showToast({ title: '提交成功，感谢反馈', icon: 'success' })
      this.setData({ correctionVisible: false, correctionSubmitting: false })
    } catch (err: unknown) {
      this.setData({ correctionSubmitting: false })
      wx.showToast({
        title: formatUserFacingError(err, isDevelopEnv(), '提交失败，请稍后重试'),
        icon: 'none',
      })
    }
  },
})
