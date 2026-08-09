const protoPage = require('../../behaviors/proto-page.js')
const { APP_DISPLAY_NAME } = require('../../native-utils/brand-assets.js')
const { navBarPx } = require('../../native-utils/matrix/layout.js')
const { computePageTopPadPx } = require('../../native-utils/nav-metrics')
const { CIV_TABS, buildRows, initialCiv, buildAllExpanded, toggleDynastyExpanded, isDynastyExpanded } = require('../../native-utils/matrix/mock-home-matrix.js')
const { fetchHomeMatrixData } = require('../../native-utils/matrix/matrix-cloud.js')
const { hasToken, request } = require('../../native-utils/api.js')
const { isCivSwitchEnabled, toastCivLocked } = require('../../native-utils/feature-flags.js')
const { trySilentWxLogin } = require('../../native-utils/wx-auth.js')
const { collapsedForCiv, hasRestorableViewport, mergePersistPayload, mergeRemoteHomeState, stripViewportFields, updateCollapsedForCiv } = require('../../native-utils/home-state.js')
const { mergeRemoteLoadResult, isViewportReadCurrent } = require('../../native-utils/home-state-coordinator.js')
const { createRemoteStateSaveQueue } = require('../../native-utils/remote-state-save-queue.js')
const { buildNavFromRows, findActiveNavIndex, invalidateHomeEmperorCountCache } = require('../../native-utils/matrix/dynasty-nav-data.js')
const {
  CIV_CODE_BY_SLUG,
  CIV_SLUG_BY_CODE,
  OVERVIEW_CIV_SPOTS,
  OVERVIEW_SPOT_TO_MATRIX_SLUG,
  buildDynastyUnitMap,
  resolveNavigationUnitId,
} = require('./matrix-adapter.js')

const DEFAULT_OVERVIEW_MAP = '/images/world-history-dynasty-map.png'

function allCivTextItems() {
  return CIV_TABS.map((t, i) => ({ id: t.id, name: t.name, realIdx: i }))
}

function allCivPickerItems() {
  return CIV_TABS.map((t, i) => Object.assign({}, t, { realIdx: i }))
}
const HOME_MATRIX_STATE_PATH = '/me/home-matrix-state'
const HOME_MATRIX_STATE_LOCAL_KEY = 'homeMatrixState'
const HOME_STATE_SAVE_DELAY = 400
const { formatHistoryYear } = require('../../native-utils/year-format')

// ─────────────────────────────────────────────────────────────────────────────
// 【旧版】横向滑动模式常量（stackMode=false 时使用）
// ─────────────────────────────────────────────────────────────────────────────
const CIV_CARD_W_RPX   = 130
const CIV_CARD_GAP_RPX = 16
const CIV_TAB_BAR_RPX  = 180
/** 底部 custom-tab-bar 高度 + 安全区，矩阵滚动留白（保证末段色块完整露出） */
const CUSTOM_TAB_BAR_RPX = 112
const MATRIX_SCROLL_BOTTOM_EXTRA_RPX = 32

function calcMatrixScrollBottomPad(screenW, safeAreaBottomPx) {
  const ratio = screenW / 750
  const safeRpx = Math.max(0, (safeAreaBottomPx || 0) / ratio)
  return Math.ceil(CUSTOM_TAB_BAR_RPX + safeRpx + MATRIX_SCROLL_BOTTOM_EXTRA_RPX)
}

const N = CIV_TABS.length  // 18

/** 时间轴列宽（rpx），与 index.scss 中 .matrix-time-col 保持一致 */
const MAJOR_NODE_KEYS = new Set(['夏','商','西周','秦','西汉','两晋','隋','唐','宋','元','明','清'])

const MATRIX_TIME_COL_RPX = 84
/** index.scss .matrix-time-col 左右内边距合计（8 + 4） */
const TIME_COL_PAD_LR_RPX = 12
/** index.scss .time-h-line--edge 刻度线宽（左右各一条） */
const TIME_EDGE_TICK_RPX = 8
/** index.scss .time-year 左右 padding 合计（2 + 2） */
const TIME_YEAR_PAD_RPX = 4
const HX_LABEL_FONT_MAX = 16
const HX_LABEL_FONT_MIN = 9
const YEAR_FONT_MAX = 14
const YEAR_FONT_MIN = 10
/** 与 .time-year 的 letter-spacing 保持一致，供自适应字号估算 */
const YEAR_LETTER_SPACING_RPX = 0.5

/** 按列宽估算朝代名可用字号（放不下则逐级缩小） */
function fitHxLabelFontSize(label, expandable) {
  if (!label) return HX_LABEL_FONT_MAX
  const len = [...String(label)].length
  const arrowRpx = expandable ? 14 : 0
  const gapRpx = expandable ? 3 : 0
  const avail = MATRIX_TIME_COL_RPX - arrowRpx - gapRpx - 4
  for (let fs = HX_LABEL_FONT_MAX; fs >= HX_LABEL_FONT_MIN; fs--) {
    if (len * fs * 1.05 <= avail) return fs
  }
  return HX_LABEL_FONT_MIN
}

/** 年份（含「-」与数字）自适应字号 */
function fitYearFontSize(year) {
  if (!year) return YEAR_FONT_MAX
  const s = String(year)
  let units = 0
  for (const ch of s) {
    units += (ch >= '0' && ch <= '9') ? 0.66 : 1
  }
  const spacingExtra = Math.max(0, s.length - 1) * YEAR_LETTER_SPACING_RPX
  // 按真实布局估算可用宽度：列内边距 + 两侧刻度线 + 文字自身 padding
  const avail = MATRIX_TIME_COL_RPX - TIME_COL_PAD_LR_RPX - 2 * TIME_EDGE_TICK_RPX - TIME_YEAR_PAD_RPX - spacingExtra
  for (let fs = YEAR_FONT_MAX; fs >= YEAR_FONT_MIN; fs--) {
    if (units * fs * 1.1 <= avail) return fs
  }
  return YEAR_FONT_MIN
}

function enrichMatrixRows(rows) {
  return (rows || []).map(row => Object.assign({}, row, {
    hxFontSize:   row.hxLabel ? fitHxLabelFontSize(row.hxLabel, row.expandable) : 0,
    yearFontSize: fitYearFontSize(row.year),
    isMajorNode:  !!(row.hxLabel && MAJOR_NODE_KEYS.has(row.hxDynastyKey)),
  }))
}

function expandedFromCollapsed(civId, collapsedKeys) {
  const expanded = buildAllExpanded(civId)
  ;(collapsedKeys || []).forEach(key => {
    const k = String(key || '').trim()
    if (k) delete expanded[k]
  })
  return expanded
}

function collapsedFromExpanded(civId, expandedDynasties) {
  const allExpanded = buildAllExpanded(civId)
  return Object.keys(allExpanded).filter(key => !expandedDynasties || !expandedDynasties[key])
}

function resolveStateCivId(state) {
  const raw = String((state && (state.civilizationCode || state.civId || state.activeCiv)) || '').trim()
  if (!raw) return initialCiv
  if (CIV_TABS.some(c => c.id === raw)) return raw
  const upper = raw.toUpperCase()
  return CIV_SLUG_BY_CODE[upper] || initialCiv
}

function civilizationCodeForCivId(civId) {
  return CIV_CODE_BY_SLUG[civId] || String(civId || initialCiv).toUpperCase()
}

function isPlainMap(value) { return Boolean(value) && typeof value === 'object' && !Array.isArray(value) }
function isValidTimestamp(value) { return typeof value === 'string' && value.trim() && Number.isFinite(Date.parse(value)) }
function normalizeCollapsedMap(value) {
  if (!isPlainMap(value)) return {}
  return Object.keys(value).reduce((result, rawId) => {
    const id = String(rawId || '').trim()
    if (!id || !Array.isArray(value[rawId])) return result
    return Object.assign({}, result, { [id]: value[rawId].map(k => String(k || '').trim()).filter(Boolean) })
  }, {})
}
function normalizeTimestampMap(value) {
  if (!isPlainMap(value)) return {}
  return Object.keys(value).reduce((result, rawId) => {
    const id = String(rawId || '').trim()
    const stamp = value[rawId]
    return id && isValidTimestamp(stamp) ? Object.assign({}, result, { [id]: stamp.trim() }) : result
  }, {})
}

function normalizeHomeState(raw) {
  const data = (raw && raw.data) || raw || {}
  const collapsed = Array.isArray(data.collapsedDynastyKeys)
    ? data.collapsedDynastyKeys.map(k => String(k || '').trim()).filter(Boolean)
    : []
  return {
    civilizationCode: String(data.civilizationCode || '').trim(),
    civId: resolveStateCivId(data),
    lastDynastyKey: String(data.lastDynastyKey || '').trim(),
    collapsedDynastyKeys: collapsed,
    collapsedDynastyKeysByCiv: normalizeCollapsedMap(data.collapsedDynastyKeysByCiv),
    collapsedDynastyUpdatedAtByCiv: normalizeTimestampMap(data.collapsedDynastyUpdatedAtByCiv),
    lastScrollTopPx: data.lastScrollTopPx == null ? null : Number(data.lastScrollTopPx),
    lastNavActiveIdx: data.lastNavActiveIdx == null ? null : Number(data.lastNavActiveIdx),
    updatedAt: isValidTimestamp(data.updatedAt) ? data.updatedAt.trim() : '',
  }
}

function readLocalHomeState() {
  try {
    const raw = wx.getStorageSync(HOME_MATRIX_STATE_LOCAL_KEY)
    return raw && typeof raw === 'object' ? normalizeHomeState(raw) : null
  } catch {
    return null
  }
}

function writeLocalHomeState(state) {
  try {
    wx.setStorageSync(HOME_MATRIX_STATE_LOCAL_KEY, state)
    debugHomeState('写入本地 Storage', state)
  } catch (err) {
    console.warn('[home-state] 写入本地失败', err)
  }
}

function isHomeMatrixApiMissing(err) {
  const detail = err && err.detail
  if (!detail || detail.status !== 404) return false
  return String(detail.url || '').includes('home-matrix-state')
}

function debugHomeState(label, state) {
  try {
    if (wx.getAccountInfoSync().miniProgram.envVersion !== 'develop') return
    console.info('[home-state]', label, state || '(空)')
  } catch {
    // ignore
  }
}

function hasMeaningfulHomeState(state) {
  if (!state) return false
  return Boolean(
    hasRestorableViewport(state) ||
    (Array.isArray(state.collapsedDynastyKeys) && state.collapsedDynastyKeys.length) ||
    state.updatedAt
  )
}

function homeStateForSession(rawState) {
  const state = rawState ? normalizeHomeState(rawState) : null
  if (!state) return null
  return hasToken() ? state : stripViewportFields(state)
}

function shouldRestoreViewport(state) {
  return hasToken() && hasRestorableViewport(state)
}

/** 合并本地与服务端状态，避免服务端空 scroll 覆盖本地有效 viewport */
function mergeHomeStates(local, remote) {
  const l = local ? normalizeHomeState(local) : null
  const r = remote ? normalizeHomeState(remote) : null
  if (!l && !r) return null
  if (!l) return r
  if (!r) return l

  const lScroll = l.lastScrollTopPx != null ? l.lastScrollTopPx : 0
  const rScroll = r.lastScrollTopPx != null ? r.lastScrollTopPx : 0
  let viewport = l
  if (rScroll > lScroll) {
    viewport = r
  } else if (lScroll > rScroll) {
    viewport = l
  } else if (r.updatedAt && l.updatedAt && r.updatedAt >= l.updatedAt) {
    viewport = r
  }

  const lCollapsed = l.collapsedDynastyKeys || []
  const rCollapsed = r.collapsedDynastyKeys || []
  let collapsed = lCollapsed
  if (r.updatedAt && l.updatedAt) {
    collapsed = r.updatedAt >= l.updatedAt ? rCollapsed : lCollapsed
  } else if (rCollapsed.length > lCollapsed.length) {
    collapsed = rCollapsed
  }

  const mergedCollapsedState = mergeRemoteHomeState(l, r)
  return normalizeHomeState({
    ...mergedCollapsedState,
    civilizationCode: viewport.civilizationCode || r.civilizationCode || l.civilizationCode,
    civId: viewport.civId || l.civId || r.civId,
    lastDynastyKey: lScroll > 0 ? l.lastDynastyKey : (rScroll > 0 ? r.lastDynastyKey : ''),
    lastScrollTopPx: lScroll > 0 ? lScroll : (rScroll > 0 ? rScroll : 0),
    lastNavActiveIdx: lScroll > 0
      ? l.lastNavActiveIdx
      : (rScroll > 0 ? r.lastNavActiveIdx : null),
    collapsedDynastyKeys: collapsedForCiv(mergedCollapsedState, viewport.civId || l.civId || r.civId) || collapsed,
    updatedAt: r.updatedAt || l.updatedAt,
  })
}

function findNavIndexByDynastyKey(key, navItems) {
  const k = String(key || '').trim()
  if (!k || !navItems || !navItems.length) return -1
  return navItems.findIndex(item => item.key === k || item.label === k)
}

function findMatrixRowKeyForDynasty(dynastyKey, matrixRows) {
  const k = String(dynastyKey || '').trim()
  if (!k || !matrixRows || !matrixRows.length) return ''
  const row = matrixRows.find(r =>
    r.hxDynastyKey === k || r.dynastyKey === k || r.hxLabel === k
  )
  return row && row.key ? row.key : ''
}

function findMatrixRowByKey(rowKey, matrixRows) {
  const k = String(rowKey || '').trim()
  if (!k || !matrixRows || !matrixRows.length) return null
  return matrixRows.find(r => r.key === k) || null
}

/** 矩阵重绘后，按 tS / 轴标注 / 朝代键找回对应时间轴行 */
function findMatrixRowAfterReload(anchor, matrixRows) {
  if (!anchor || !matrixRows || !matrixRows.length) return null
  if (anchor.key) {
    const byKey = matrixRows.find(r => r.key === anchor.key)
    if (byKey) return byKey
  }
  if (anchor.tS != null) {
    const byTsLabel = matrixRows.find(r => r.tS === anchor.tS && r.hxLabel === anchor.hxLabel)
    if (byTsLabel) return byTsLabel
    const byTsDynasty = matrixRows.find(r => r.tS === anchor.tS && r.dynastyKey === anchor.dynastyKey)
    if (byTsDynasty) return byTsDynasty
    const byTs = matrixRows.find(r => r.tS === anchor.tS)
    if (byTs) return byTs
  }
  if (anchor.dynastyKey) {
    return matrixRows.find(r =>
      (r.dynastyKey === anchor.dynastyKey || r.hxDynastyKey === anchor.dynastyKey) && r.hxLabel
    ) || null
  }
  return null
}

function scrollTopPxForRow(row, ratio, insetPx) {
  if (!row || row.y == null) return 0
  const inset = insetPx != null ? insetPx : 8
  return Math.max(0, Math.round(row.y * (ratio || 0.5)) - inset)
}

/** 收展后 scrollTop：保持点击行在视口中的相对位置不变 */
function resolveToggleTargetScroll(viewport, clickedRow, anchorRow, ratio, maxScroll) {
  const r = ratio || 0.5
  const scrollBefore = Math.max(0, Math.round((viewport && viewport.scrollBefore) || 0))
  let target = scrollBefore

  if (anchorRow && viewport && viewport.hasVisualOffset && viewport.offsetInView != null && !Number.isNaN(viewport.offsetInView)) {
    target = Math.round(anchorRow.y * r - viewport.offsetInView)
  } else if (anchorRow && clickedRow && clickedRow.y != null && anchorRow.y != null) {
    target = scrollBefore + Math.round((anchorRow.y - clickedRow.y) * r)
  }

  return Math.max(0, Math.min(maxScroll, target))
}

/** 收展后滚动：优先匹配色块/容器顶缘，其次导航 yPx、时间轴行 */
function blockMatchesDynastyScrollKey(block, dynastyKey) {
  if (!block || !dynastyKey) return false
  const key = String(dynastyKey).trim()
  if (block.containerId === key) return true
  if (block.entryId === `container_span_${key}`) return true
  if (block.dynasty === key || block.displayName === key) return true
  if (key === '宋' && (block.dynasty === '北宋' || block.displayName === '北宋')) return true
  if (key === '两晋' && (block.dynasty === '西晋' || block.dynasty === '东晋')) return true
  return false
}

function resolveDynastyScrollTopPx(dynastyKey, ctx) {
  const key = String(dynastyKey || '').trim()
  if (!key) return 0
  const ratio = ctx.ratio || 0.5
  const blocks = ctx.matrixBlocks || []
  const navItems = ctx.navItems || []
  const rows = ctx.matrixRows || []
  const scrollInsetPx = ctx.scrollInsetPx != null ? ctx.scrollInsetPx : 8

  const matchedBlocks = blocks.filter(b => blockMatchesDynastyScrollKey(b, key))
  if (matchedBlocks.length) {
    const topRpx = Math.min(...matchedBlocks.map(b => b.top))
    return Math.max(0, Math.round(topRpx * ratio) - scrollInsetPx)
  }

  const navItem = navItems.find(item => item.key === key || item.label === key)
  if (navItem && navItem.yPx > 0) {
    return Math.max(0, navItem.yPx - scrollInsetPx)
  }

  const row = rows.find(r =>
    r.hxDynastyKey === key || r.dynastyKey === key || r.hxLabel === key
  )
  if (row) {
    return Math.max(0, Math.round((row.y || 0) * ratio) - scrollInsetPx)
  }

  return 0
}

function buildLoopItems(civIndex) {
  const activeLoopIdx = civIndex + N
  return [...CIV_TABS, ...CIV_TABS, ...CIV_TABS].map((t, i) => {
    const rawDist = Math.abs(i - activeLoopIdx)
    const dist    = Math.min(rawDist, N - rawDist)
    const scale   = Math.max(0.70, 1.00 - dist * 0.10)
    const opacity = dist === 0 ? 1.00 : Math.max(0.45, 1.00 - dist * 0.18 + 0.04)
    return {
      id:        t.id,
      img:       t.img,
      name:      t.name,
      realIdx:   i % N,
      loopIdx:   i,
      cardStyle: `transform:scale(${scale.toFixed(2)});opacity:${opacity.toFixed(2)};`
    }
  })
}

function calcCivScroll(realIdx, screenW) {
  const r       = screenW / 750
  const cardW   = CIV_CARD_W_RPX   * r
  const gap     = CIV_CARD_GAP_RPX * r
  const step    = cardW + gap
  const loopIdx = realIdx + N
  const center  = loopIdx * step + cardW / 2
  return Math.max(0, center - screenW / 2)
}

// ─────────────────────────────────────────────────────────────────────────────
// 【新版】层叠卡片模式常量（stackMode=true 时使用）
// ─────────────────────────────────────────────────────────────────────────────
const STACK_UI_SCALE   = 0.7   // 图片 Tab 整体等比缩小 30%
const STACK_CARD_W_RPX = Math.round(148 * STACK_UI_SCALE)  // 104
/** 与 COS 文明卡素材比例 468×546 对齐，避免 aspectFill 裁切错位 */
const STACK_CARD_H_RPX = Math.round(STACK_CARD_W_RPX * 546 / 468)
/** 文明 Tab PNG 视觉圆角（实测 COS 素材，宽 468） */
const CIV_TAB_ASSET_W = 468
const CIV_TAB_RADIUS_TOP_PX = 100
const CIV_TAB_RADIUS_BOTTOM_PX = 139

function civPickerCardRadius(cardW) {
  const rt = Math.round(cardW * CIV_TAB_RADIUS_TOP_PX / CIV_TAB_ASSET_W)
  const rb = Math.round(cardW * CIV_TAB_RADIUS_BOTTOM_PX / CIV_TAB_ASSET_W)
  return `${rt}rpx ${rt}rpx ${rb}rpx ${rb}rpx`
}
const STACK_STEP_RPX   = Math.round(166 * STACK_UI_SCALE)  // 116
const STACK_BAR_RPX    = Math.round(210 * STACK_UI_SCALE)  // 147
const STACK_LAYER_SHIFT_PX = Math.round(22 * STACK_UI_SCALE)  // 15
const STACK_DEPTH_Y_RPX    = Math.round(4 * STACK_UI_SCALE)   // 3
const TEXT_BAR_RPX     = 88    // 文字 Tab 栏高（文字高 + 上下 padding）
const CIV_TEXT_TAB_BAR_RPX = TEXT_BAR_RPX
const STACK_MAX_D      = 4     // 最多展示左右各 4 张

// 文字 Tab 常量（向下滑动后展示）
const TEXT_ITEM_W_RPX  = 72
const TEXT_ITEM_GAP_RPX = 10
const CIV_ALL_BTN_RESERVE_RPX = 112

/** 浮层文明卡相对列宽缩放（0.7 = 缩小 30%） */
const CIV_PICKER_CARD_SCALE = 0.7

/** 浮层 18 张文明卡（4×5）一屏展示时的卡片与面板高度 */
function calcCivPickerMetrics(windowHeight, headerPadPx, screenW) {
  const COLS = 4
  const ROWS = Math.ceil(CIV_TABS.length / COLS)
  const GAP = 16
  const PAD = 24
  const BACKDROP_MIN_RPX = 24
  const ratio = screenW / 750
  const availRpx = Math.max(600, (windowHeight - headerPadPx) / ratio - BACKDROP_MIN_RPX)
  const colW = (750 - PAD * 2 - GAP * (COLS - 1)) / COLS
  const cardH = Math.floor((availRpx - PAD * 2 - GAP * (ROWS - 1)) / ROWS)
  const cardWBase = Math.min(Math.floor(colW), Math.round(cardH * STACK_CARD_W_RPX / STACK_CARD_H_RPX))
  const cardW = Math.round(cardWBase * CIV_PICKER_CARD_SCALE)
  const cardHFinal = Math.round(cardW * STACK_CARD_H_RPX / STACK_CARD_W_RPX)
  const sheetH = PAD * 2 + ROWS * cardHFinal + GAP * (ROWS - 1)
  return {
    civPickerCardW: cardW,
    civPickerCardH: cardHFinal,
    civPickerSheetH: sheetH,
    civPickerCardRadius: civPickerCardRadius(cardW),
  }
}

function calcTextScroll(civIndex, screenW) {
  const r    = screenW / 750
  const step = (TEXT_ITEM_W_RPX + TEXT_ITEM_GAP_RPX) * r
  const mid  = civIndex * step + TEXT_ITEM_W_RPX * r / 2
  const visibleW = screenW - CIV_ALL_BTN_RESERVE_RPX * r
  return Math.max(0, mid - visibleW / 2)
}

/**
 * 生成层叠卡片样式列表（长度固定 N=18，DOM 不销毁重建 → CSS transition 持续生效）
 */
function buildStackItems(civIndex, screenW) {
  if (!screenW) {
    return CIV_TABS.map((t, i) => ({ id: t.id, img: t.img, name: t.name, realIdx: i, cardStyle: 'opacity:0;position:absolute;' }))
  }
  const ratio    = screenW / 750
  const cardW_px = STACK_CARD_W_RPX * ratio
  const step_px  = STACK_STEP_RPX   * ratio
  const baseLeft = (screenW / 2 - cardW_px / 2).toFixed(1)

  return CIV_TABS.map((t, realIdx) => {
    let rawD = realIdx - civIndex
    if (rawD >  N / 2) rawD -= N
    if (rawD < -N / 2) rawD += N
    const d    = rawD
    const absd = Math.abs(d)
    const vis  = absd <= STACK_MAX_D

    const scale   = vis ? +(Math.max(0.66, 1.0 - absd * 0.085)).toFixed(3) : 0
    // 未选中卡片整体透明度 +4%，选中保持 1.0
    const baseOp  = vis ? Math.max(0.0, 1.0 - absd * 0.18) : 0
    const opacity = vis ? +(absd === 0 ? 1.0 : Math.min(1, baseOp + 0.04)).toFixed(2) : 0
    const zIndex  = vis ? (30 - absd * 4) : 0
    const txPx    = vis ? (d * step_px).toFixed(1) : (d >= 0 ? '1500' : '-1500')

    const cardStyle =
      `position:absolute;left:${baseLeft}px;z-index:${zIndex};` +
      `transform:translate3d(${txPx}px,0,0) scale(${scale});` +
      `opacity:${opacity};`

    return { id: t.id, img: t.img, name: t.name, realIdx, cardStyle }
  })
}

// ─── 首页仅保留文字 Tab（图片 Tab 已移除）────────────────────────────
const STACK_MODE = false

/** 生成 Tab 双层样式（避免 WXML 属性里写 `<` 导致编译失败白屏） */
function buildTabLayerStyles(tabAlpha) {
  const a = tabAlpha || 0
  const stackZ = a < 0.5 ? 2 : 1
  const textZ  = a >= 0.5 ? 2 : 1
  const pe     = a < 0.08 ? 'none' : 'auto'
  return {
    tabAlpha:        a,
    stackLayerStyle:
      `opacity:${(1 - a).toFixed(2)};transform:translateY(${(0 - a * STACK_LAYER_SHIFT_PX).toFixed(1)}px);z-index:${stackZ};`,
    textLayerStyle:
      `opacity:${a.toFixed(2)};transform:translateY(${((1 - a) * 14).toFixed(1)}px);pointer-events:${pe};z-index:${textZ};`,
  }
}

Page({
  behaviors: [protoPage],

  data: {
    appDisplayName: APP_DISPLAY_NAME,
    mode:              'immersive',
    civSpots:          OVERVIEW_CIV_SPOTS,
    overviewMapUrl:    DEFAULT_OVERVIEW_MAP,
    dynastyUnitMap:    {},
    stackMode:         STACK_MODE,
    // 层叠卡片模式数据
    civStackItems:     [],
    // 文字 Tab 数据（向下滑动后展示）
    civTextItems:      allCivTextItems(),
    civSwitchEnabled:  true,
    civTextScrollLeft: 0,
    // 图片→文字渐变进度（0=图片，1=文字），由 onMatrixScroll 驱动
    tabAlpha:          1,
    stackLayerStyle:   '',
    textLayerStyle:    '',
    tabAreaH:          CIV_TEXT_TAB_BAR_RPX,
    civSwitching:      false,
    scrollRatio:       0.5,
    statusBarPx:       20,
    windowHeightPx:    667,
    // 横向滑动模式数据（stackMode=false 时使用）
    civTabsLoop:       [],
    loopN:             N,
    civScrollLeft:     0,
    civScrollAnim:     false,
    // 公共数据
    civIndex:          0,
    activeCiv:         initialCiv,
    matrixRows:        [],
    matrixBlocks:      [],
    matrixScrollTop:   0,
    matrixScrollIntoView: '',
    matrixScrollLock:  false,
    matrixBodyOffset:  0,
    navItems:          [],
    navActiveIdx:      -1,
    navActive:         false,
    navHudVisible:     false,
    navHudFading:     false,
    navDragActive: false,
    navHudTitle:       '',
    navHudSub:         '',
    navHudYear:        '',
    navHudEmp:        '',
    navHudLeft:        0,
    navHudTop:         0,
    matrixOverlays:    [],
    matrixSubCards:    [],
    matrixContainerHits: [],
    matrixTotalH:      0,
    matrixScrollBottomPad: 200,
    scrollAreaTop:     0,
    matrixHeight:      600,
    headerPadPx:       88,
    pageTopPadPx:      88,
    expandedDynasties: {},
    matrixDataLoading: true,
    civPickerOpen:     false,
    civPickerItems:    CIV_TABS.map((t, i) => Object.assign({}, t, { realIdx: i })),
    civPickerCardW:    156,
    civPickerCardH:    177,
    civPickerSheetH:   960,
    civPickerCardRadius: civPickerCardRadius(156),
  },

  onLoad() {
    const defaultExpanded = buildAllExpanded(initialCiv)
    let sw = 375
    let statusBar = 20
    let windowHeight = 667
    let safeBottomPx = 0
    try {
      const sys = wx.getSystemInfoSync()
      sw = sys.windowWidth
      statusBar = sys.statusBarHeight || 20
      windowHeight = sys.windowHeight
      if (sys.safeArea && sys.screenHeight) {
        safeBottomPx = Math.max(0, sys.screenHeight - sys.safeArea.bottom)
      }
    } catch (e) {}

    this._screenW = sw
    this._statusBarH = statusBar
    this._windowHeight = windowHeight
    this._ratio = sw / 750
    this._navPx = navBarPx()
    this._pendingExpanded = defaultExpanded
    this._homeStateGeneration = 0
    this._homeStateDisposed = false
    this._remoteHomeStateSaveQueue = createRemoteStateSaveQueue(payload => request(HOME_MATRIX_STATE_PATH, {
      method: 'PUT', auth: true, data: payload,
    }).catch(err => {
      if (isHomeMatrixApiMissing(err)) { this._homeMatrixRemoteUnavailable = true; return }
      const msg = String(err && err.message || '')
      if (msg !== 'UNAUTHORIZED') console.warn('[home] home matrix state save failed', err)
    }))

    const navPx = navBarPx()
    const headerPadPx = statusBar + navPx
    const pageTopPadPx = computePageTopPadPx({ windowWidth: sw, statusBarHeight: statusBar })
    const tabBarPx = CIV_TEXT_TAB_BAR_RPX * (sw / 750)
    const scrollAreaTop = headerPadPx + tabBarPx
    const matrixHeight = Math.max(200, windowHeight - scrollAreaTop)
    const matrixScrollBottomPad = calcMatrixScrollBottomPad(sw, safeBottomPx)
    const pickerMetrics = calcCivPickerMetrics(windowHeight, headerPadPx, sw)
    const cachedLocal = homeStateForSession(readLocalHomeState())
    this._cachedHomeState = cachedLocal
    const bootCiv = cachedLocal && cachedLocal.civId ? cachedLocal.civId : initialCiv
    const bootCivIndex = Math.max(0, CIV_TABS.findIndex(c => c.id === bootCiv))
    const bootExpanded = cachedLocal
      ? expandedFromCollapsed(bootCiv, collapsedForCiv(cachedLocal, bootCiv) || cachedLocal.collapsedDynastyKeys)
      : defaultExpanded
    if (hasToken() && cachedLocal && cachedLocal.lastScrollTopPx > 0) {
      this._lastScrollTop = cachedLocal.lastScrollTopPx
    }
    if (hasToken() && cachedLocal && cachedLocal.lastDynastyKey) {
      this._lastDynastyKey = cachedLocal.lastDynastyKey
    }
    if (hasToken() && cachedLocal && cachedLocal.lastNavActiveIdx != null && cachedLocal.lastNavActiveIdx >= 0) {
      this._lastNavActiveIdx = cachedLocal.lastNavActiveIdx
    }

    this.setData(Object.assign({
      activeCiv:         bootCiv,
      civIndex:          bootCivIndex,
      expandedDynasties: bootExpanded,
      tabAreaH:          CIV_TEXT_TAB_BAR_RPX,
      civStackItems:     [],
      civTabsLoop:       buildLoopItems(bootCivIndex),
      civScrollLeft:     calcCivScroll(bootCivIndex, sw),
      civTextScrollLeft: calcTextScroll(bootCivIndex, sw),
      civScrollAnim:     false,
      scrollAreaTop,
      matrixHeight,
      matrixScrollBottomPad,
      scrollRatio:       sw / 750,
      statusBarPx:       statusBar,
      windowHeightPx:    windowHeight,
      matrixRows:        [],
      matrixBlocks:      [],
      matrixSubCards:    [],
      matrixContainerHits: [],
      matrixOverlays:    [],
      matrixTotalH:      0,
      headerPadPx,
      pageTopPadPx,
    }, buildTabLayerStyles(0), pickerMetrics))

    this._tabAlpha = 0
    this._preloadCivImages()
    this._lastScrollTop = this._lastScrollTop || 0
    this._skipShowRefresh = true
    this._homeStateLoaded = false
    this._restoringHomeState = false
    this._homeStatePromise = this._loadHomeMatrixState()
    this._matrixDataPromise = this._refreshMatrixData()
    this._gridDataPromise = this._loadGridData()
    wx.nextTick(() => this._syncTabAlphaFromDom())
  },

  _applyCivSwitchFlag(enabled) {
    const civSwitchEnabled = enabled !== false
    this.setData({ civSwitchEnabled })
    // 内容仍停在华夏，Tab 栏完整展示供预热；非华夏点击由 _selectCiv 弹 Toast
    if (!civSwitchEnabled && this.data.activeCiv !== initialCiv) {
      this._selectCiv(initialCiv, 0, { silent: true })
    }
  },

  _loadGridData() {
    return request('/home/grid').then(res => {
      const data = (res && res.data) || {}
      const flags = data.flags || {}
      this._applyCivSwitchFlag(flags.civSwitchEnabled)
      const overview = data.overview || {}
      const mapUrl = String(overview.mapImageUrl || '').trim() || DEFAULT_OVERVIEW_MAP
      const dynastyUnitMap = buildDynastyUnitMap(data.cells || [])
      this._dynastyUnitMap = dynastyUnitMap

      // 用后端 tabImageUrl（含 cache-bust）覆盖浮层/总览配图，保证文明 CODE ↔ 图 一一对应
      const civs = Array.isArray(data.civilizations) ? data.civilizations : []
      const urlBySlug = {}
      civs.forEach(c => {
        const code = String((c && c.code) || '').trim().toUpperCase()
        const slug = CIV_SLUG_BY_CODE[code]
        const url = String((c && c.tabImageUrl) || '').trim()
        if (slug && url) urlBySlug[slug] = url
      })
      CIV_TABS.forEach(t => {
        if (urlBySlug[t.id]) t.img = urlBySlug[t.id]
      })
      const civPickerItems = allCivPickerItems()
      const civSpots = (this.data.civSpots || OVERVIEW_CIV_SPOTS).map(spot => {
        const matrixSlug = OVERVIEW_SPOT_TO_MATRIX_SLUG[spot.id] || spot.id
        const img = urlBySlug[matrixSlug] || spot.img
        return Object.assign({}, spot, { img })
      })

      this.setData({
        overviewMapUrl: mapUrl,
        dynastyUnitMap,
        civPickerItems,
        civSpots,
        civTabsLoop: buildLoopItems(this.data.civIndex || 0),
      })
      this._preloadCivImages()
    }).catch(err => {
      console.warn('[home] grid load failed', err)
      this._dynastyUnitMap = {}
    })
  },

  _loadHomeMatrixState() {
    const requestGeneration = this._homeStateGeneration || 0
    const localState = this._cachedHomeState || readLocalHomeState()
    debugHomeState('启动读取本地', localState)
    if (this._homeMatrixRemoteUnavailable) {
      return Promise.resolve(localState)
    }
    const ensureToken = hasToken() ? Promise.resolve(true) : trySilentWxLogin()
    return ensureToken.then(ok => {
      if (!ok || !hasToken()) {
        return homeStateForSession(localState)
      }
      return request(HOME_MATRIX_STATE_PATH, { auth: true }).then(res => {
        const remoteState = normalizeHomeState(res && res.data ? res.data : null)
        const latestLocal = this._cachedHomeState || readLocalHomeState()
        const coordinated = mergeRemoteLoadResult(latestLocal, remoteState, requestGeneration, this._homeStateGeneration || 0)
        const merged = mergeHomeStates(latestLocal, coordinated.state)
        if (merged && hasMeaningfulHomeState(merged)) {
          writeLocalHomeState(homeStateForSession(merged))
          this._cachedHomeState = homeStateForSession(merged)
        }
        if (!coordinated.shouldApplyUi) {
          this._homeStateLoadStale = true
          return null
        }
        return homeStateForSession(merged || latestLocal || remoteState)
      }).catch(err => {
        if (isHomeMatrixApiMissing(err)) {
          this._homeMatrixRemoteUnavailable = true
          console.info('[home-state] 本地后端未部署 /me/home-matrix-state，仅使用本地 Storage（键名 homeMatrixState）')
          return homeStateForSession(localState)
        }
        const msg = String(err && err.message || '')
        if (msg !== 'UNAUTHORIZED') {
          console.warn('[home] home matrix state load failed', err)
        }
        return homeStateForSession(localState)
      })
    }).catch(() => homeStateForSession(localState))
  },

  /** 拉取首页矩阵源数据（冷启动 / 无缓存兜底时调用；切 tab 回来不走这里） */
  _refreshMatrixData() {
    this.setData({ matrixDataLoading: true })
    return fetchHomeMatrixData().then(info => {
      const app = getApp()
      if (app && app.globalData) app.globalData.matrixDataSource = info.source
      this.setData({ matrixDataLoading: false })
      return info
    })
  },

  _preloadCivImages() {
    try {
      if (wx.preloadAssets) {
        wx.preloadAssets({
          data: CIV_TABS.map(t => ({ type: 'image', src: t.img }))
        })
      }
    } catch (e) {}
  },

  onReady() {
    let windowHeight = 667
    let statusBar = this._statusBarH || 20
    let sw = this._screenW || 375
    let safeBottomPx = 0
    try {
      const sys = wx.getSystemInfoSync()
      windowHeight = sys.windowHeight
      statusBar = sys.statusBarHeight || 20
      sw = sys.windowWidth
      if (sys.safeArea && sys.screenHeight) {
        safeBottomPx = Math.max(0, sys.screenHeight - sys.safeArea.bottom)
      }
      this._screenW = sw
      this._statusBarH = statusBar
      this._windowHeight = windowHeight
      this._ratio = sw / 750
    } catch (e) {}

    const navPx = this._navPx || navBarPx()
    const headerPadPx = statusBar + navPx
    const pageTopPadPx = computePageTopPadPx({ windowWidth: sw, statusBarHeight: statusBar })
    const tabBarPx = CIV_TEXT_TAB_BAR_RPX * (sw / 750)
    const scrollAreaTop = headerPadPx + tabBarPx
    const matrixHeight = Math.max(200, windowHeight - scrollAreaTop)
    const matrixScrollBottomPad = calcMatrixScrollBottomPad(sw, safeBottomPx)
    this.setData(Object.assign({
      scrollAreaTop,
      matrixHeight,
      matrixScrollBottomPad,
      tabAreaH: CIV_TEXT_TAB_BAR_RPX,
      scrollRatio:    sw / 750,
      statusBarPx:    statusBar,
      windowHeightPx: windowHeight,
      civStackItems:  buildStackItems(this.data.civIndex, sw),
      headerPadPx,
      pageTopPadPx,
    }, calcCivPickerMetrics(windowHeight, headerPadPx, sw)))

    const loadAfterData = (homeState) => {
      this._readyLoaded = true
      if (this._homeStateLoadStale) {
        this._homeStateLoaded = true
        this._loadMatrix(this.data.activeCiv, this.data.expandedDynasties)
        return
      }
      const state = homeState || this._cachedHomeState || readLocalHomeState()
      this._applyInitialHomeMatrixState(state)
    }
    if (this._matrixDataPromise || this._homeStatePromise) {
      Promise.all([
        (this._matrixDataPromise || Promise.resolve()).catch(err => {
          console.warn('[home] matrix data load failed before ready', err)
          return null
        }),
        this._homeStatePromise || Promise.resolve(null),
      ]).then(([, homeState]) => loadAfterData(homeState)).catch(() => loadAfterData(null))
    } else {
      loadAfterData(null)
    }
  },

  /** 读取 scroll-view 真实 scrollTop（bindscroll 在部分机型上不可靠） */
  _readMatrixScrollTop(callback) {
    const fallback = Math.max(0, Math.round(this._lastScrollTop || 0))
    const navItems = this.data.navItems || []
    const navIdx = this.data.navActiveIdx
    const navTop = navIdx >= 0 && navItems[navIdx] && navItems[navIdx].yPx > 0
      ? Math.round(navItems[navIdx].yPx)
      : 0
    const finish = typeof callback === 'function' ? callback : function() {}
    try {
      wx.createSelectorQuery().in(this).select('#matrixScroll').scrollOffset(res => {
        const domTop = res && res.scrollTop != null ? Math.max(0, Math.round(res.scrollTop)) : 0
        finish(domTop > 0 ? domTop : (fallback > 0 ? fallback : navTop))
      }).exec()
    } catch {
      finish(fallback > 0 ? fallback : navTop)
    }
  },

  /** 构建并注入矩阵行（失败时降级为收起态） */
  _loadMatrix(civId, expandedDynasties, onReady, opts) {
    const done = typeof onReady === 'function' ? onReady : null
    const preserveScrollTop = opts && opts.preserveScrollTop != null
      ? Math.max(0, Math.round(opts.preserveScrollTop))
      : null
    try {
      const layout = buildRows(civId, expandedDynasties || {})
      if (!layout.rows || !layout.rows.length) {
        console.error('[home-matrix] buildRows returned empty for', civId)
      }
      invalidateHomeEmperorCountCache()
      const patch = {
        matrixRows:       enrichMatrixRows(layout.rows     || []),
        // Phase 1/2: initialize nav data from rows
        navItems:         layout.rows
          ? buildNavFromRows(layout.rows, this._ratio || 0.5, civId).navItems
          : this.data.navItems,
        matrixBlocks:     layout.blocks     || [],
        matrixOverlays:   layout.overlays     || [],
        matrixSubCards:   layout.subCards   || [],
        matrixContainerHits: layout.containerHits || [],
        matrixTotalH:     layout.totalH     || 0,
        civScrollAnim: true,
      }
      if (preserveScrollTop != null) {
        patch.navDragActive = true
        patch.matrixScrollTop = preserveScrollTop
      }
      this.setData(patch, () => {
        this._cacheNavRect()
        if (done) done()
      })
    } catch (err) {
      console.error('[home-matrix] _loadMatrix failed', err)
      try {
        const layout = buildRows(civId, {})
        invalidateHomeEmperorCountCache()
        const fallbackPatch = {
          matrixRows:       enrichMatrixRows(layout.rows     || []),
        // Phase 1/2: initialize nav data from rows
        navItems:         layout.rows
          ? buildNavFromRows(layout.rows, this._ratio || 0.5, civId).navItems
          : this.data.navItems,
          matrixBlocks:     layout.blocks     || [],
          matrixOverlays:   layout.overlays     || [],
          matrixSubCards:   layout.subCards   || [],
          matrixContainerHits: layout.containerHits || [],
          matrixTotalH:     layout.totalH     || 0,
          expandedDynasties: {},
        }
        if (preserveScrollTop != null) {
          fallbackPatch.navDragActive = true
          fallbackPatch.matrixScrollTop = preserveScrollTop
        }
        this.setData(fallbackPatch, () => {
          this._cacheNavRect()
          if (done) done()
        })
      } catch (err2) {
        console.error('[home-matrix] fallback load failed', err2)
        if (done) done()
      }
    }
  },

  _applyInitialHomeMatrixState(homeState) {
    this._homeStateLoaded = true
    const state = homeState ? normalizeHomeState(homeState) : null
    this._cachedHomeState = state
    const activeCiv = state ? state.civId : this.data.activeCiv
    const civIndex = Math.max(0, CIV_TABS.findIndex(c => c.id === activeCiv))
    const resolvedCiv = CIV_TABS[civIndex] ? CIV_TABS[civIndex].id : initialCiv
    const expandedDynasties = state
      ? expandedFromCollapsed(resolvedCiv, collapsedForCiv(state, resolvedCiv) || state.collapsedDynastyKeys)
      : (this._pendingExpanded || this.data.expandedDynasties || buildAllExpanded(resolvedCiv))
    const sw = this._screenW || 375

    this.setData({
      activeCiv: resolvedCiv,
      civIndex,
      expandedDynasties,
      civTextScrollLeft: calcTextScroll(civIndex, sw),
      civTabsLoop: buildLoopItems(civIndex),
      civScrollLeft: calcCivScroll(civIndex, sw),
      civScrollAnim: false,
    })
    this._lastDynastyKey = state && state.lastDynastyKey ? state.lastDynastyKey : ''
    this._loadMatrix(resolvedCiv, expandedDynasties, () => {
      this._waitForMatrixLayout(() => {
        if (shouldRestoreViewport(state)) {
          this._restoreViewportFromState(state)
        } else {
          this._scrollToTop()
        }
        this.setData({ civScrollAnim: true })
      })
    })
  },

  /** 等待矩阵布局完成后再恢复滚动，避免 scroll-top 对空内容无效 */
  _waitForMatrixLayout(callback, attempt) {
    const tryCount = attempt != null ? attempt : 0
    const ready = this.data.matrixTotalH > 0 && (this.data.navItems || []).length > 0
    if (ready || tryCount >= 24) {
      setTimeout(callback, ready ? 100 : 0)
      return
    }
    setTimeout(() => this._waitForMatrixLayout(callback, tryCount + 1), 50)
  },

  _restoreViewportFromState(state) {
    const normalized = normalizeHomeState(state)
    debugHomeState('准备恢复滚动', normalized)
    if (!hasRestorableViewport(normalized)) {
      this._scrollToTop()
      return
    }

    const navItems = this.data.navItems || []
    const matrixRows = this.data.matrixRows || []
    const ratio = this._ratio || 0.5
    const maxScroll = Math.max(0, this.data.matrixTotalH * ratio - this.data.matrixHeight)
    let navIdx = -1
    let navItem = null
    let scrollTop = 0
    let rowKey = ''

    if (normalized.lastNavActiveIdx != null && normalized.lastNavActiveIdx >= 0 && normalized.lastNavActiveIdx < navItems.length) {
      navIdx = normalized.lastNavActiveIdx
      navItem = navItems[navIdx]
    }
    if (!navItem && normalized.lastDynastyKey) {
      navIdx = findNavIndexByDynastyKey(normalized.lastDynastyKey, navItems)
      navItem = navIdx >= 0 ? navItems[navIdx] : null
    }

    if (normalized.lastScrollTopPx === 0) {
      scrollTop = 0
      navIdx = -1
      navItem = null
    } else if (normalized.lastScrollTopPx != null && normalized.lastScrollTopPx > 0) {
      scrollTop = normalized.lastScrollTopPx
    } else if (navItem && navItem.yPx > 0) {
      scrollTop = navItem.yPx
    } else if (normalized.lastDynastyKey) {
      rowKey = findMatrixRowKeyForDynasty(normalized.lastDynastyKey, matrixRows)
      const row = matrixRows.find(r =>
        r.key === rowKey ||
        r.hxDynastyKey === normalized.lastDynastyKey ||
        r.dynastyKey === normalized.lastDynastyKey ||
        r.hxLabel === normalized.lastDynastyKey
      )
      scrollTop = row ? Math.round((row.y || 0) * ratio) : 0
      if (!navItem) {
        navIdx = findActiveNavIndex(scrollTop, navItems)
        navItem = navIdx >= 0 ? navItems[navIdx] : null
      }
    }

    scrollTop = Math.max(0, Math.min(maxScroll, scrollTop))
    if (navItem && navItem.key) {
      this._lastDynastyKey = navItem.key
    } else if (normalized.lastDynastyKey) {
      this._lastDynastyKey = normalized.lastDynastyKey
    }
    if (navIdx < 0 && navItem) {
      navIdx = findNavIndexByDynastyKey(navItem.key, navItems)
    }
    if (!rowKey && normalized.lastDynastyKey) {
      rowKey = findMatrixRowKeyForDynasty(normalized.lastDynastyKey, matrixRows)
    }

    this._applyProgrammaticScroll({
      scrollTop,
      navIdx,
      scrollIntoView: rowKey ? ('ts_' + rowKey) : '',
      isRestore: true,
    })
  },

  /** 程序化滚动：冷启动用 scroll-into-view + scroll-top，不先滚到顶部 */
  _applyProgrammaticScroll(opts) {
    const scrollTop = Math.max(0, Math.round(opts.scrollTop || 0))
    const navIdx = opts.navIdx != null ? opts.navIdx : -1
    const scrollIntoView = String(opts.scrollIntoView || '').trim()
    const lockMs = opts.isRestore ? 1200 : 120

    this._restoringHomeState = !!opts.isRestore
    this._lastScrollTop = scrollTop
    this._scrollTopNonce = (this._scrollTopNonce || 0) + 1

    const applyTarget = () => {
      const patch = {
        navDragActive: true,
        matrixScrollTop: scrollTop,
        navActiveIdx: navIdx,
      }
      if (scrollIntoView) patch.matrixScrollIntoView = scrollIntoView
      this.setData(patch, () => {
        if (scrollIntoView) {
          setTimeout(() => this.setData({ matrixScrollIntoView: '' }), 200)
        }
        if (opts.isRestore) {
          this._verifyScrollRestore(scrollTop, navIdx, scrollIntoView, 0)
        } else {
          this._releaseProgrammaticScrollLock(lockMs)
        }
      })
    }

    if (opts.isRestore && scrollTop > 0) {
      this.setData({ navDragActive: true, matrixScrollIntoView: '' }, () => {
        setTimeout(applyTarget, 150)
      })
      return
    }

    this.setData({ navDragActive: true, matrixScrollTop: 0, matrixScrollIntoView: '' }, () => {
      setTimeout(applyTarget, opts.isRestore ? 120 : 20)
    })
  },

  _verifyScrollRestore(expectedTop, navIdx, scrollIntoView, attempt) {
    const that = this
    wx.createSelectorQuery().in(this).select('#matrixScroll').scrollOffset(function(res) {
      const current = res && res.scrollTop != null ? res.scrollTop : 0
      const diff = Math.abs(current - expectedTop)
      if (diff > 12 && attempt < 8) {
        that._scrollMatrixToPx(expectedTop, function() {
          setTimeout(function() {
            that._verifyScrollRestore(expectedTop, navIdx, scrollIntoView, attempt + 1)
          }, 120)
        })
        return
      }
      that._lastScrollTop = current > 0 ? current : expectedTop
      that._restoringHomeState = false
      that.setData({
        navDragActive: false,
        matrixScrollLock: false,
        matrixScrollTop: that._lastScrollTop,
        navActiveIdx: navIdx,
      })
    }).exec()
  },

  _scrollToTop() {
    const navIdx = findActiveNavIndex(0, this.data.navItems || [])
    this._applyProgrammaticScroll({ scrollTop: 0, navIdx, isRestore: true })
  },

  _scrollToDynastyStart(dynastyKey) {
    const key = String(dynastyKey || '').trim()
    if (!key) return
    const ratio = this._ratio || 0.5
    const rawTop = resolveDynastyScrollTopPx(key, {
      ratio,
      matrixBlocks: this.data.matrixBlocks || [],
      navItems: this.data.navItems || [],
      matrixRows: this.data.matrixRows || [],
    })
    if (rawTop <= 0) return
    const maxScroll = Math.max(0, this.data.matrixTotalH * ratio - this.data.matrixHeight)
    const scrollTop = Math.max(0, Math.min(maxScroll, rawTop))
    const navIdx = findNavIndexByDynastyKey(key, this.data.navItems || [])
    this._lastDynastyKey = key
    if (navIdx >= 0) this._lastNavActiveIdx = navIdx
    this._applyProgrammaticScroll({
      scrollTop,
      navIdx: navIdx >= 0 ? navIdx : this.data.navActiveIdx,
      isRestore: true,
    })
  },

  /** 收展前读取：scrollTop + 点击行相对视口顶部的偏移（px） */
  _readToggleViewportSnapshot(rowKey, clickedRow, callback) {
    const ratio = this._ratio || 0.5
    const finish = typeof callback === 'function' ? callback : function() {}
    const rowSelector = rowKey ? ('#ts_' + rowKey) : ''
    const query = wx.createSelectorQuery().in(this)
    query.select('#matrixScroll').scrollOffset()
    query.select('#matrixScroll').boundingClientRect()
    if (rowSelector) query.select(rowSelector).boundingClientRect()

    query.exec(res => {
      const scrollOffset = (res && res[0]) || {}
      const svRect = (res && res[1]) || {}
      const rowRect = rowSelector ? ((res && res[2]) || {}) : null

      let offsetInView = null
      let hasVisualOffset = false
      if (rowRect && svRect && rowRect.top != null && svRect.top != null) {
        offsetInView = rowRect.top - svRect.top
        hasVisualOffset = true
      }

      // 微信 scrollOffset 离开首屏后常为 0；用「行 y + 视口偏移」反推真实 scrollTop
      let scrollBefore = 0
      if (hasVisualOffset && clickedRow && clickedRow.y != null) {
        scrollBefore = Math.max(0, Math.round(clickedRow.y * ratio - offsetInView))
      } else {
        const domScroll = scrollOffset.scrollTop != null ? Math.round(scrollOffset.scrollTop) : 0
        const cachedScroll = Math.max(0, Math.round(this._lastScrollTop || 0))
        scrollBefore = domScroll > 0 ? domScroll : cachedScroll
      }

      finish({ scrollBefore, offsetInView, hasVisualOffset })
    })
  },

  _scrollMatrixToPx(scrollTop, done) {
    const top = Math.max(0, Math.round(scrollTop || 0))
    const finish = typeof done === 'function' ? done : function() {}
    const applyFallback = () => {
      const nudge = top > 0 ? top + 1 : 1
      this.setData({
        matrixScrollLock: true,
        navDragActive: true,
        matrixScrollIntoView: '',
        matrixScrollTop: nudge,
      }, () => {
        this.setData({ matrixScrollTop: top }, () => finish(false))
      })
    }

    try {
      wx.createSelectorQuery()
        .in(this)
        .select('#matrixScroll')
        .node()
        .exec(res => {
          const node = res && res[0] && res[0].node
          if (node && typeof node.scrollTo === 'function') {
            node.scrollTo({ top, animated: false })
            this._lastScrollTop = top
            this.setData({ matrixScrollTop: top })
            finish(true)
            return
          }
          applyFallback()
        })
    } catch {
      applyFallback()
    }
  },

  /** 收展：更新矩阵并恢复 scroll，保持点击行在视口中的位置 */
  _applyMatrixTogglePreserveViewport(matrixPatch, viewport, clickedRow, anchorRow, navIdx, ratio) {
    const maxScroll = Math.max(0, (matrixPatch.matrixTotalH || 0) * ratio - this.data.matrixHeight)
    const targetScroll = resolveToggleTargetScroll(viewport, clickedRow, anchorRow, ratio, maxScroll)
    const resolvedNavIdx = navIdx >= 0 ? navIdx : this.data.navActiveIdx
    const nudgeTop = targetScroll > 0 ? targetScroll + 1 : 1

    this._restoringHomeState = true
    this._lastScrollTop = targetScroll

    this.setData(Object.assign({}, matrixPatch, {
      navActiveIdx: resolvedNavIdx,
      matrixScrollLock: true,
      navDragActive: true,
      matrixScrollIntoView: '',
      matrixBodyOffset: 0,
      matrixScrollTop: nudgeTop,
    }), () => {
      this._cacheNavRect()
      this.setData({ matrixScrollTop: targetScroll }, () => {
        this._verifyToggleScrollRestore(targetScroll, resolvedNavIdx, 0)
      })
    })
  },

  /** 收展滚动校验：读回真实 scrollTop，未到位则用 _scrollMatrixToPx 重试（同冷启动 _verifyScrollRestore 模式） */
  _verifyToggleScrollRestore(expectedTop, navIdx, attempt) {
    const that = this
    wx.createSelectorQuery().in(this).select('#matrixScroll').scrollOffset(function(res) {
      const current = res && res.scrollTop != null ? res.scrollTop : 0
      const diff = Math.abs(current - expectedTop)
      // expectedTop 为 0 时读回的 0 不可信（首屏 scrollOffset 本就恒 0），直接按既定值收尾
      if (expectedTop > 0 && diff > 12 && attempt < 8) {
        that._scrollMatrixToPx(expectedTop, function() {
          setTimeout(function() {
            that._verifyToggleScrollRestore(expectedTop, navIdx, attempt + 1)
          }, 120)
        })
        return
      }
      that._lastScrollTop = current > 0 ? current : expectedTop
      that._restoringHomeState = false
      that.setData({
        matrixScrollLock: false,
        navDragActive: false,
        matrixBodyOffset: 0,
        matrixScrollTop: that._lastScrollTop,
        navActiveIdx: navIdx >= 0 ? navIdx : that.data.navActiveIdx,
      })
      that._updateNavHighlight(that._lastScrollTop)
      that._writeHomeViewportState(true)
    }).exec()
  },

  _releaseProgrammaticScrollLock(lockMs) {
    const delay = lockMs != null ? lockMs : 120
    if (this._homeStateScrollTimer) clearTimeout(this._homeStateScrollTimer)
    this._homeStateScrollTimer = setTimeout(() => {
      this._restoringHomeState = false
      this.setData({ navDragActive: false })
      this._homeStateScrollTimer = null
    }, delay)
  },

  /** 文字 Tab 固定展示，矩阵滚动不再切换 Tab 形态 */

  // ─── 导航高亮更新 ──────────────────────────────────────────────
  _updateNavHighlight(scrollTopPx) {
    const activeIdx = findActiveNavIndex(scrollTopPx, this.data.navItems)
    if (activeIdx !== this.data.navActiveIdx) {
      this.setData({ navActiveIdx: activeIdx })
    }
    const item = activeIdx >= 0 ? (this.data.navItems || [])[activeIdx] : null
    if (item && item.key) {
      this._lastDynastyKey = item.key
      this._lastNavActiveIdx = activeIdx
    }
  },

  /** 退出前读取 scroll-view 真实 scrollTop，避免缓存滞后 */
  _syncScrollTopFromDom(done, token) {
    const start = token || { civId: this.data.activeCiv || initialCiv, generation: this._homeStateGeneration || 0 }
    const finish = typeof done === 'function' ? done : function() {}
    try {
      wx.createSelectorQuery().in(this).select('#matrixScroll').scrollOffset(res => {
        const current = { civId: this.data.activeCiv || initialCiv, generation: this._homeStateGeneration || 0 }
        const isCurrent = isViewportReadCurrent(start, current)
        if (isCurrent && res && res.scrollTop != null && !this._restoringHomeState) {
          this._lastScrollTop = res.scrollTop
          this._updateNavHighlight(res.scrollTop)
        }
        finish(isCurrent)
      }).exec()
    } catch {
      finish(false)
    }
  },

  _scheduleHomeMatrixStateSave(immediate) {
    if (this._restoringHomeState && !immediate) return
    if (this._homeStateSaveTimer) {
      clearTimeout(this._homeStateSaveTimer)
      this._homeStateSaveTimer = null
    }
    if (immediate) {
      this._persistHomeViewportState(true)
      return
    }
    this._homeStateSaveTimer = setTimeout(() => {
      this._homeStateSaveTimer = null
      this._persistHomeViewportState(true)
    }, HOME_STATE_SAVE_DELAY)
  },

  _saveHomeMatrixState() {
    this._persistHomeViewportState(false)
  },

  /** 写入本地缓存；有登录态时同步服务端 */
  _persistHomeViewportState(syncRemote) {
    const token = { civId: this.data.activeCiv || initialCiv, generation: this._homeStateGeneration || 0 }
    this._syncScrollTopFromDom(() => {
      const current = { civId: this.data.activeCiv || initialCiv, generation: this._homeStateGeneration || 0 }
      if (isViewportReadCurrent(token, current)) this._writeHomeViewportState(syncRemote)
    }, token)
  },

  _writeHomeViewportState(syncRemote) {
    const activeCiv = this.data.activeCiv || initialCiv
    const navItems = this.data.navItems || []
    const scrollTopPx = Math.max(0, Math.round(this._lastScrollTop || 0))
    const navIdx = this.data.navActiveIdx != null && this.data.navActiveIdx >= 0
      ? this.data.navActiveIdx
      : findActiveNavIndex(scrollTopPx, navItems)
    const rawPayload = {
      civilizationCode: civilizationCodeForCivId(activeCiv),
      civId: activeCiv,
      lastDynastyKey: this._lastDynastyKey || this._currentDynastyKeyFromScroll() || '',
      collapsedDynastyKeys: collapsedFromExpanded(activeCiv, this.data.expandedDynasties || {}),
      lastScrollTopPx: scrollTopPx,
      lastNavActiveIdx: navIdx >= 0 ? navIdx : null,
      updatedAt: new Date().toISOString(),
    }
    const existing = this._cachedHomeState || readLocalHomeState()
    const mergedPayload = mergePersistPayload(existing, rawPayload)
    const payload = normalizeHomeState(updateCollapsedForCiv(
      mergedPayload,
      activeCiv,
      rawPayload.collapsedDynastyKeys,
      rawPayload.updatedAt,
    ))
    const persisted = hasToken() ? payload : stripViewportFields(payload)
    writeLocalHomeState(persisted)
    this._cachedHomeState = persisted
    if (!syncRemote || !hasToken() || this._homeMatrixRemoteUnavailable) return
    const remotePayload = {
      civilizationCode: payload.civilizationCode,
      lastDynastyKey: payload.lastDynastyKey,
      collapsedDynastyKeys: payload.collapsedDynastyKeys,
      lastScrollTopPx: payload.lastScrollTopPx,
    }
    this._remoteHomeStateSaveQueue.enqueue(remotePayload)
  },

  _currentDynastyKeyFromScroll() {
    const activeIdx = findActiveNavIndex(this._lastScrollTop || 0, this.data.navItems || [])
    const item = activeIdx >= 0 ? (this.data.navItems || [])[activeIdx] : null
    return item && item.key ? item.key : ''
  },

  _applyTabAlphaFromScroll() {},

  _syncTabAlphaFromDom() {},

  onShow() {
    const tab = typeof this.getTabBar === 'function' ? this.getTabBar() : null
    if (tab && typeof tab.setSelected === 'function') tab.setSelected(0)

    const app = getApp()
    const pending = app.globalData && app.globalData.pendingCiv
    if (pending && pending !== this.data.activeCiv) {
      const idx = CIV_TABS.findIndex(c => c.id === pending)
      if (idx >= 0) {
        if (this.data.mode !== 'immersive') this.setData({ mode: 'immersive' })
        this._selectCiv(CIV_TABS[idx].id, idx)
      }
      app.globalData.pendingCiv = null
    }

    // 页面重新显示时，按实际滚动位置恢复图片 Tab 显隐（避免停在文字 Tab 无法回到图片）
    if (!this._skipShowRefresh) {
      this._syncTabAlphaFromDom()
    }

    if (this._skipShowRefresh) {
      this._skipShowRefresh = false
      return
    }

    // 切 tab / 从子页返回：页面实例仍在，矩阵 DOM 与滚动位置应保留。
    // 不整表 _loadMatrix、不恢复视口（避免闪到唐朝等过期锚点）。
    // 仅冷启动竞态（尚未 ready）或矩阵被清空时才兜底重建。
    const hasMatrix = (this.data.matrixRows || []).length > 0
    if (this._readyLoaded && hasMatrix) {
      return
    }

    this._refreshMatrixData().then(() => {
      if (!this._readyLoaded) return
      const restoreState = homeStateForSession(this._cachedHomeState || readLocalHomeState())
      this._loadMatrix(this.data.activeCiv, this.data.expandedDynasties, () => {
        if (shouldRestoreViewport(restoreState)) {
          this._restoreViewportFromState(restoreState)
        }
      })
    })
  },

  onUnload() {
    if (this._matrixLoadTimer) clearTimeout(this._matrixLoadTimer)
    if (this._civSwitchTimer) clearTimeout(this._civSwitchTimer)
    if (this._homeStateSaveTimer) clearTimeout(this._homeStateSaveTimer)
    if (this._homeStateScrollTimer) clearTimeout(this._homeStateScrollTimer)
    this._persistHomeViewportState(true)
    this._homeStateDisposed = true
    if (this._remoteHomeStateSaveQueue) this._remoteHomeStateSaveQueue.dispose()
  },

  onHide() {
    this._persistHomeViewportState(true)
  },

  // ── 用路径更新 civStackItems 的每个 cardStyle，保留 DOM 节点让 CSS transition 生效
  _applyStackStyles(civIndex, sw) {
    const newItems = buildStackItems(civIndex, sw)
    const updates  = {}
    newItems.forEach((item, i) => {
      updates[`civStackItems[${i}].cardStyle`] = item.cardStyle
    })
    this.setData(updates)
  },

  _selectCiv(activeCiv, civIndex, options) {
    const silent = options && options.silent
    if (!isCivSwitchEnabled()) {
      if (activeCiv !== initialCiv || civIndex !== 0) {
        if (!silent) toastCivLocked()
        return
      }
    }
    if (civIndex === this.data.civIndex && activeCiv === this.data.activeCiv) return
    this._homeStateGeneration = (this._homeStateGeneration || 0) + 1
    const previousCiv = this.data.activeCiv || initialCiv
    const previousCollapsed = collapsedFromExpanded(previousCiv, this.data.expandedDynasties || {})
    const previousState = normalizeHomeState(updateCollapsedForCiv(
      this._cachedHomeState || readLocalHomeState() || {},
      previousCiv,
      previousCollapsed,
      new Date().toISOString(),
    ))
    writeLocalHomeState(previousState)
    this._cachedHomeState = previousState
    const cachedCollapsed = collapsedForCiv(this._cachedHomeState || readLocalHomeState(), activeCiv)
    const expandedDynasties = cachedCollapsed == null
      ? buildAllExpanded(activeCiv)
      : expandedFromCollapsed(activeCiv, cachedCollapsed)
    const sw = (this._screenW) || 375

    if (this._matrixLoadTimer) clearTimeout(this._matrixLoadTimer)

    this.setData({
      activeCiv,
      civIndex,
      expandedDynasties,
      civSwitching:      true,
      civTextScrollLeft: calcTextScroll(civIndex, sw),
      civTabsLoop:       buildLoopItems(civIndex),
      civScrollLeft:     calcCivScroll(civIndex, sw),
      civScrollAnim:     true,
    })

    if (this._civSwitchTimer) clearTimeout(this._civSwitchTimer)
    this._civSwitchTimer = setTimeout(() => {
      this.setData({ civSwitching: false })
    }, 340)

    this._matrixLoadTimer = setTimeout(() => {
      this._loadMatrix(activeCiv, expandedDynasties)
      this._lastDynastyKey = this._currentDynastyKeyFromScroll()
      this._scheduleHomeMatrixStateSave()
    }, 300)
  },

  onCivTap(e) {
    // 如果触摸有明显位移（说明是滑动），忽略 tap 防止重复触发
    if (this._wasSwiped) { this._wasSwiped = false; return }
    const realIdx = Number(e.currentTarget.dataset.ri)
    if (isNaN(realIdx) || realIdx < 0 || realIdx >= N) return
    this._selectCiv(CIV_TABS[realIdx].id, realIdx)
  },

  // ── 图片 Tab 左右滑动切换文明（在外层容器捕获，避免文字层拦截）
  onStackTouchStart(e) {
    this._swipeStartX = e.touches[0].clientX
    this._swipeStartY = e.touches[0].clientY
    this._swipeTime   = Date.now()
    this._wasSwiped   = false
  },

  onStackTouchEnd(e) {
    if (this._swipeStartX == null) return
    const dx  = e.changedTouches[0].clientX - this._swipeStartX
    const dy  = e.changedTouches[0].clientY - this._swipeStartY
    const dt  = Date.now() - this._swipeTime
    this._swipeStartX = null

    // 仅在图片模式、水平滑动足够大、垂直偏移不超过水平的 1.5 倍时触发切换
    const isHSwipe = Math.abs(dx) > 40 && Math.abs(dy) < Math.abs(dx) * 1.5 && dt < 500
    if (isHSwipe && (this._tabAlpha || 0) < 0.6) {
      const delta  = dx < 0 ? 1 : -1
      const newIdx = ((this.data.civIndex + delta) + N) % N
      const target = CIV_TABS[newIdx]
      if (!isCivSwitchEnabled() && target.id !== initialCiv) {
        toastCivLocked()
        return
      }
      this._wasSwiped  = true
      this._selectCiv(target.id, newIdx)
    }
  },

  // 矩阵滚动：图片 Tab 渐隐 → 文字 Tab 渐现（跟手更新 opacity / 位移）
  /** 矩阵触摸移动：nav 激活时配合 scroll-view 原生 touchmove 处理索引拖动 */
  onMatrixTouchMove(e) {
    var touch = e.touches && e.touches[0]
    if (!touch) return
    // 只处理右侧 50px 范围内的触摸（nav 区域）
    var rightZone = this._navRightZoneEdge !== undefined ? this._navRightZoneEdge : (wx.getSystemInfoSync().windowWidth - 50)
    if (touch.clientX < rightZone) return
    // 不在 nav 区域内的触摸直接放行（由 scroll-view 原生滚动处理）
    if (!this._navTouched) return

    // 长按计时器未触发（< 400ms）→ 不做任何事，只有长按 400ms 才能激活
    if (this._navLongPressTimer) {
      return
    }

    // 导航栏未激活时不处理
    if (!this.data.navActive && !this._navPendingActivation) return

    // 导航已激活，更新位置
    if (!this._navMoved) {
      this._navMoved = true
      this._navWasDrag = true
      this._isNavDragging = true
      if (this._navAutoDismissTimer) {
        clearTimeout(this._navAutoDismissTimer)
        this._navAutoDismissTimer = null
      }
    }
    this._updateNavFromTouch(e)
  },


  onMatrixScroll(e) {
    const detailTop = e && e.detail ? e.detail.scrollTop : 0
    this._lastMatrixScrollDetail = detailTop
    if (!this._restoringHomeState && detailTop >= 0) {
      this._lastScrollTop = detailTop
    } else if (detailTop > 0 || !this._lastScrollTop) {
      this._lastScrollTop = detailTop
    }
    const scrollTop = this._lastScrollTop
    this._applyTabAlphaFromScroll(scrollTop)
    if (!this._restoringHomeState) {
      this._homeStateGeneration = (this._homeStateGeneration || 0) + 1
      this._updateNavHighlight(scrollTop)
      this._scheduleHomeMatrixStateSave()
    }
    // nav 已收起但 navDragActive 仍锁定 → 用户手动滚动时释放（恢复 / 收展期间不可打断）
    if (!this._restoringHomeState && !this.data.matrixScrollLock && this.data.navDragActive && !this.data.navActive && !this._navPendingActivation) {
      this.setData({ navDragActive: false })
    }
    // 用户手动滚动时收起导航栏（非 drag 状态）
    if (this.data.navActive && !this._navMoved && !this._isNavDragging) {
      this.setData({ navActive: false })
      this._hideNavHud()
    }
  },

  // 滚动结束后从 DOM 读取真实位置再保存（enhanced scroll-view 的 detail.scrollTop 可能不准）
  onMatrixScrollEnd(e) {
    if (this._restoringHomeState) return
    const detailTop = e && e.detail && e.detail.scrollTop != null ? e.detail.scrollTop : null
    if (detailTop != null) {
      this._lastScrollTop = detailTop
      if (!this.data.matrixScrollLock && !this.data.navDragActive
        && (this.data.matrixScrollTop || 0) !== detailTop) {
        this.setData({ matrixScrollTop: detailTop })
      }
    }
    this._syncScrollTopFromDom(isCurrent => {
      if (!isCurrent) return
      this._applyTabAlphaFromScroll(this._lastScrollTop, true)
      this._updateNavHighlight(this._lastScrollTop)
      this._writeHomeViewportState(true)
    })
  },

  // ─── 导航索引点击跳转 ──────────────────────────────────────────
  _findRowKeyForDynasty(dynastyKey) {
    const rows = this.data.matrixRows || []
    const row = rows.find(r => r.hxDynastyKey === dynastyKey)
    return row ? row.key : null
  },



  // ─── 时间轴触摸：长按 400ms 激活导航栏，短按穿透到收起展开 ──
  onTimeColTouchStart(e) {
    // 时间列不再处理导航交互，保留为空
  },

  onTimeColTouchMove(e) {
    // 时间列不再处理导航交互
  },


  onTimeColTouchEnd(e) {
    // 时间列不再处理导航交互
  },




  // ─── 导航索引触摸（Phase 3 拖动预留） ─────────────────────────
  /** 缓存导航器位置，供拖动手势映射使用 */
  _cacheNavRect() {
    var that = this
    wx.createSelectorQuery()
      .select('.dynasty-nav')
      .boundingClientRect(function(rect) {
        if (rect) that._navRect = rect
      })
      .exec()
  },

  /** 拖动结束后吸附到最近朝代起始位置 */
  _snapNav() {
    if (this._isNavDragging) return
    var scrollTop = this._lastScrollTop || 0
    var navItems = this.data.navItems
    if (!navItems || !navItems.length) return
    var nearest = null
    var minDist = Infinity
    navItems.forEach(function(item) {
      var dist = Math.abs(item.yPx - scrollTop)
      if (dist < minDist) {
        minDist = dist
        nearest = item
      }
    })
    if (nearest && nearest.yPx >= 0) {
      // Snap：通过 scroll-top 吸附到朝代起点
      this.setData({
        matrixScrollTop: nearest.yPx,
        navDragActive: true,
      })
      if (this._navSnapTimer) clearTimeout(this._navSnapTimer)
      var that = this
      this._navSnapTimer = setTimeout(function() {
        that.setData({ navDragActive: false })
        that._navSnapTimer = null
      }, 50)
    }
  },

  onNavTouchStart(e) {
    // 只处理右侧 50px 范围内的触摸（nav 区域）
    var touch = e.touches && e.touches[0]
    if (!touch) return
    var sysInfo = wx.getSystemInfoSync()
    var navZoneRightEdge = sysInfo.windowWidth - 50
    if (touch.clientX < navZoneRightEdge) return
    // 清理自动收起计时器
    if (this._navAutoDismissTimer) {
      clearTimeout(this._navAutoDismissTimer)
      this._navAutoDismissTimer = null
    }
    if (this._navLongPressTimer) {
      clearTimeout(this._navLongPressTimer)
      this._navLongPressTimer = null
    }
    this._navTouched = true
    this._navLastActiveIdx = -1
    this._navWasDrag = false
    this._navMoved = false
    this._isNavDragging = false
    this._navPendingActivation = false
    this._navTouchStartY = touch.clientY
    this._navRightZoneEdge = navZoneRightEdge
    // 长按 400ms 激活导航栏
    var that = this
    this._navLongPressTimer = setTimeout(function() {
      that._navLongPressTimer = null
      that._navPendingActivation = true
      // 激活时默认高亮当前视口顶部的朝代
      var scrollTopPx = that._lastScrollTop || 0
      var navItems = that.data.navItems || []
      var activeIdx = (typeof findActiveNavIndex === 'function')
        ? findActiveNavIndex(scrollTopPx, navItems)
        : -1
      if (activeIdx < 0 || activeIdx >= navItems.length) activeIdx = 0
      that._navLastActiveIdx = activeIdx
      that.setData({
        navActive: true,
        navActiveIdx: activeIdx,
        matrixScrollTop: scrollTopPx,
        navDragActive: true,
      })
      that._showNavHud(navItems[activeIdx])
      that._cacheNavRect()
      that._isNavDragging = true
      that._navMoved = false
      that._navTouched = true
      that._navWasDrag = false
    }, 400)
  },

  onNavTouchMove(e) {
    // 只有长按 400ms 激活后才能拖动
    if (!this.data.navActive && !this._navPendingActivation) return

    // 计时器未触发 → 不做任何事
    if (this._navLongPressTimer) return

    // 首次移动标记
    if (!this._navMoved) {
      this._navMoved = true
      this._navWasDrag = true
      this._isNavDragging = true
      if (this._navAutoDismissTimer) {
        clearTimeout(this._navAutoDismissTimer)
        this._navAutoDismissTimer = null
      }
    }
    this._updateNavFromTouch(e)
  },

  onNavTouchEnd(e) {
    this._navTouched = false

    if (this._navLongPressTimer) {
      // 短按（< 400ms），计时器未触发 → 不做任何事
      clearTimeout(this._navLongPressTimer)
      this._navLongPressTimer = null
      return
    }

    if (this.data.navActive) {
      // 手指松开 → 立即收起导航栏，无需 3s 延迟
      this._isNavDragging = false
      const idx = this.data.navActiveIdx
      const item = idx >= 0 ? (this.data.navItems || [])[idx] : null
      if (item && item.key) {
        this._lastDynastyKey = item.key
        this._lastNavActiveIdx = idx
        if (item.yPx >= 0) this._lastScrollTop = item.yPx
        this._persistHomeViewportState(true)
      }
      this._navLastActiveIdx = -1
      this.setData({ navActive: false })
      this._hideNavHud()
      this._navMoved = false
    }
  },

  _handleNavTap(e) {
    // 单次点击：通过 scroll-top 跳转，不显示 HUD
    if (!this._navRect) return
    var touch = e && e.changedTouches && e.changedTouches[0]
    if (!touch) return
    var relY = touch.clientY - this._navRect.top
    var ratio = Math.max(0, Math.min(1, relY / this._navRect.height))
    var totalHPx = this.data.matrixTotalH * this._ratio
    var scrollTop = Math.round(ratio * totalHPx)
    var maxScroll = Math.max(0, totalHPx - this.data.matrixHeight)
    scrollTop = Math.max(0, Math.min(maxScroll, scrollTop))
    this.setData({ matrixScrollTop: scrollTop, navDragActive: true })
    // 短暂激活后释放（利用 scroll-top 完成一次性跳转）
    if (this._navTapTimer) clearTimeout(this._navTapTimer)
    var that = this
    this._navTapTimer = setTimeout(function() {
      that.setData({ navDragActive: false })
      that._navTapTimer = null
    }, 50)
  },

  _updateNavFromTouch(e) {
    const touch = e.touches && e.touches[0]
    if (!touch) return
    // 直接用 scrollAreaTop / matrixHeight 计算位置（避免 _navRect 缓存过期）
    var navTop = this.data.scrollAreaTop || 0
    var navH = this.data.matrixHeight || 600
    if (!navH) return
    var relY = touch.clientY - navTop
    // 触摸位置对应 navItems 索引
    var navItems = this.data.navItems
    if (!navItems || !navItems.length) return
    var ratio = Math.max(0, Math.min(1, (relY - navH * 0.25) / (navH * 0.50)))
    var idx = Math.round(ratio * (navItems.length - 1))
    idx = Math.max(0, Math.min(navItems.length - 1, idx))
    var item = navItems[idx]
    if (!item || item.yPx < 0) return
    // 如果朝代没有变化则不处理（每次只切换一个朝代）
    if (idx === this._navLastActiveIdx && this._navLastActiveIdx >= 0) return
    this._navLastActiveIdx = idx
    // 直接 snap 到该朝代的 yPx 位置（第一个卡片在屏幕顶部）
    var maxScroll = Math.max(0, this.data.matrixTotalH * this._ratio - this.data.matrixHeight)
    var snapTop = Math.max(0, Math.min(maxScroll, item.yPx))
    this.setData({
      matrixScrollTop: snapTop,
      navDragActive: true,
    })
    this._lastScrollTop = snapTop
    this._lastDynastyKey = item.key
    this._lastNavActiveIdx = idx
    // 更新高亮和 HUD
    this.setData({ navActiveIdx: idx })
    this._showNavHud(navItems[idx])
    this._persistHomeViewportState(true)
  },

  // ─── HUD 显示/隐藏 ─────────────────────────────────────────────
  _showNavHud(item) {
    if (!item) return
    const label = item.label
    const start = item.start
    const idx = this.data.navItems.indexOf(item)
    const next = idx >= 0 && idx < this.data.navItems.length - 1
      ? this.data.navItems[idx + 1]
      : null
    const endYear = next ? next.start : ''
    const yearStr = formatHistoryYear(start) + (endYear !== '' && endYear != null ? ' — ' + formatHistoryYear(endYear) : '')
    const empCount = item.emperorCount || 0
    const scrollAreaTop = this.data.scrollAreaTop
    // HUD 固定在左上区域（时间列右侧，与导航栏位置无关）
    const hudTop = scrollAreaTop + 12
    const ratio = this._ratio || 0.5
    // 时间列宽度 84rpx，HUD 放在其右侧
    const timeColW = Math.round(84 * ratio)
    const hudLeft = timeColW + 10
    this.setData({
      navHudVisible: true,
      navHudFading: false,
      navHudTitle:   label,
      navHudYear:    yearStr,
      navHudEmp:     empCount > 0 ? empCount + ' 位帝王' : '',
      navHudTop:     hudTop,
      navHudLeft:    hudLeft,
    })
  },

  _hideNavHud() {
    if (this._navHudTimer) {
      clearTimeout(this._navHudTimer)
      this._navHudTimer = null
    }
    // 先触发 opacity 过渡，250ms 后再隐藏 DOM
    this.setData({ navHudFading: true })
    this._navHudTimer = setTimeout(() => {
      this.setData({ navHudVisible: false, navHudFading: false })
      this._navHudTimer = null
    }, 250)
  },

  _clearNavHudTimer() {
    if (this._navHudTimer) {
      clearTimeout(this._navHudTimer)
      this._navHudTimer = null
    }
  },



  // 用户手动滑到边缘时，无动画静默跳回中间段（实现环形效果）
  // 阈值设计：跳转后的新位置不再触发阈值，避免连锁跳转
  //   sectionW ≈ 18 × (130+16) × ratio = 18 × 146 × 0.5 = 1314px（375px 设备）
  //   跳前 sl < 0.4×sectionW(≈526)  → 跳至 sl + sectionW（≈526+1314=1840，不再超 2.0×sectionW）
  //   跳前 sl > 2.0×sectionW(≈2628) → 跳至 sl - sectionW（≈2629-1314=1315，不再低于 0.4×sectionW）
  onCivScrollEnd(e) {
    try {
      const sys      = wx.getSystemInfoSync()
      const r        = sys.windowWidth / 750
      const step     = (CIV_CARD_W_RPX + CIV_CARD_GAP_RPX) * r
      const sectionW = N * step
      const sl       = e.detail.scrollLeft

      if (sl < sectionW * 0.4) {
        this.setData({ civScrollAnim: false, civScrollLeft: sl + sectionW }, () => {
          this.setData({ civScrollAnim: true })
        })
      } else if (sl > sectionW * 2.0) {
        this.setData({ civScrollAnim: false, civScrollLeft: sl - sectionW }, () => {
          this.setData({ civScrollAnim: true })
        })
      }
    } catch (e) {}
  },

  goOverview() {
    this.setData({ mode: 'overview', civPickerOpen: false })
  },

  goMatrix() {
    this.setData({ mode: 'immersive' })
    wx.nextTick(() => this._syncTabAlphaFromDom())
  },

  onSpotTap(e) {
    const { id } = e.currentTarget.dataset
    if (id) this._enterCivFromOverview(id)
  },

  onCivCardTap(e) {
    const id = e.currentTarget.dataset.id
    if (id) this._enterCivFromOverview(id)
  },

  _enterCivFromOverview(spotId) {
    const matrixSlug = OVERVIEW_SPOT_TO_MATRIX_SLUG[spotId] || spotId
    if (!isCivSwitchEnabled() && matrixSlug !== initialCiv) {
      toastCivLocked()
      return
    }
    const idx = CIV_TABS.findIndex(c => c.id === matrixSlug)
    if (idx < 0) return
    const app = getApp()
    if (app && app.globalData) app.globalData.pendingCiv = null
    this.setData({ mode: 'immersive' }, () => {
      this._selectCiv(CIV_TABS[idx].id, idx)
      wx.nextTick(() => this._syncTabAlphaFromDom())
    })
  },

  onToggleCivPicker() {
    this.setData({ civPickerOpen: !this.data.civPickerOpen })
  },

  onCivPickerClose() {
    if (!this.data.civPickerOpen) return
    this.setData({ civPickerOpen: false })
  },

  onCivPickerSelect(e) {
    const realIdx = Number(e.currentTarget.dataset.ri)
    if (isNaN(realIdx) || realIdx < 0 || realIdx >= N) return
    this.setData({ civPickerOpen: false })
    this._selectCiv(CIV_TABS[realIdx].id, realIdx)
  },

  preventMove() {},

  onCardTap(e) {
    const ds = e.currentTarget.dataset || {}
    this._openEntityDetail(ds)
  },

  onMiniTap(e) {
    const ds = e.currentTarget.dataset || {}
    this._openEntityDetail(ds)
  },

  _openEntityDetail(ds) {
    const containerId = ds.containerId || ''
    const dynasty = ds.dynasty || ds.displayName || ''
    const person = ds.person || ''
    if (!dynasty && !person && !ds.entityId && !containerId) return

    const map = this._dynastyUnitMap || this.data.dynastyUnitMap || {}
    const unitId = resolveNavigationUnitId({
      entityType: ds.entityType,
      entityId: ds.entityId,
      legacyId: ds.legacyId,
      dynastyId: ds.dynastyId,
      person,
      dynasty,
      displayName: ds.displayName,
      containerId,
    }, map)

    if (unitId) {
      let url = `/pages/dynasty-detail/index?unitId=${encodeURIComponent(unitId)}`
      const CONTAINER_LABELS = new Set([
        '春秋', '战国', '南北朝', '五代十国', '金', '辽', '元', '清', '三国',
      ])
      const label = CONTAINER_LABELS.has(containerId)
        ? containerId
        : (dynasty || ds.displayName || person)
      if (label) {
        url += `&dynasty=${encodeURIComponent(String(label))}`
      }
      const anchorYear = ds.anchorYear
      if (anchorYear != null && anchorYear !== '') {
        url += `&anchorYear=${encodeURIComponent(String(anchorYear))}`
      }
      wx.navigateTo({ url })
      return
    }

    const q = person || dynasty
    wx.navigateTo({ url: `/pages/search/index?q=${encodeURIComponent(String(q || ''))}` })
  },

  // 展开/收起华夏某朝代（点击时间轴朝代名旁箭头触发）
  onDynastyToggle(e) {
    if (this._navPendingActivation) {
      this._navPendingActivation = false
      return
    }
    const dynastyKey = e.currentTarget.dataset.dynasty
    if (!dynastyKey) return
    const anchorRowKey = e.currentTarget.dataset.rowKey || ''
    const civTab = CIV_TABS[this.data.civIndex]
    const civName = civTab ? civTab.name : '华夏'
    const civId = this.data.activeCiv || initialCiv
    const ratio = this._ratio || 0.5
    const prevRows = this.data.matrixRows || []

    const clickedRow = findMatrixRowByKey(anchorRowKey, prevRows)
      || prevRows.find(r => r.dynastyKey === dynastyKey && r.hxLabel)
    const anchor = clickedRow
      ? { key: clickedRow.key, tS: clickedRow.tS, hxLabel: clickedRow.hxLabel, dynastyKey: clickedRow.dynastyKey }
      : { dynastyKey }

    this._readToggleViewportSnapshot(anchorRowKey, clickedRow, viewport => {
      const expanded = toggleDynastyExpanded(dynastyKey, this.data.expandedDynasties, civName)

      let layout
      try {
        layout = buildRows(civId, expanded)
      } catch (err) {
        console.error('[home-matrix] onDynastyToggle buildRows failed', err)
        return
      }

      invalidateHomeEmperorCountCache()
      const matrixRows = enrichMatrixRows(layout.rows || [])
      const navItems = matrixRows.length
        ? buildNavFromRows(matrixRows, ratio, civId).navItems
        : (this.data.navItems || [])

      const anchorRow = findMatrixRowAfterReload(anchor, matrixRows)
      const navIdx = findNavIndexByDynastyKey(dynastyKey, navItems)

      this._homeStateGeneration = (this._homeStateGeneration || 0) + 1
      this._lastDynastyKey = dynastyKey

      this._applyMatrixTogglePreserveViewport({
        expandedDynasties: expanded,
        matrixRows,
        navItems,
        matrixBlocks: layout.blocks || [],
        matrixOverlays: layout.overlays || [],
        matrixSubCards: layout.subCards || [],
        matrixContainerHits: layout.containerHits || [],
        matrixTotalH: layout.totalH || 0,
        civScrollAnim: true,
      }, viewport, clickedRow, anchorRow, navIdx, ratio)
    })
  },
  noop() {}
})
