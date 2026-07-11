const protoPage = require('../../behaviors/proto-page.js')
const { navBarPx } = require('../../native-utils/matrix/layout.js')
const { CIV_TABS, buildRows, initialCiv, buildAllExpanded, toggleDynastyExpanded } = require('../../native-utils/matrix/mock-home-matrix.js')
const { fetchHomeMatrixData } = require('../../native-utils/matrix/matrix-cloud.js')
const { hasToken, request } = require('../../native-utils/api.js')
const { trySilentWxLogin } = require('../../native-utils/wx-auth.js')
const { buildNavFromRows, findActiveNavIndex } = require('../../native-utils/matrix/dynasty-nav-data.js')
const {
  CIV_CODE_BY_SLUG,
  CIV_SLUG_BY_CODE,
  OVERVIEW_CIV_SPOTS,
  OVERVIEW_SPOT_TO_MATRIX_SLUG,
  buildDynastyUnitMap,
  resolveNavigationUnitId,
} = require('./matrix-adapter.js')

const DEFAULT_OVERVIEW_MAP = '/images/world-history-dynasty-map.png'
const HOME_MATRIX_STATE_PATH = '/me/home-matrix-state'
const HOME_MATRIX_STATE_LOCAL_KEY = 'homeMatrixState'
const HOME_STATE_SAVE_DELAY = 400

/** 历史年份展示：公元前用 -XX */
function formatHistoryYear(y) {
  if (!Number.isFinite(y)) return ''
  if (y === 0) return '公元0'
  if (y < 0) return '-' + Math.abs(y)
  return String(y)
}

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

/** 时间轴列宽（rpx），与 home-matrix.wxss 中 .matrix-time-col 保持一致 */
const MAJOR_NODE_KEYS = new Set(['夏','商','西周','秦','西汉','西晋','隋','唐','北宋','元','明','清'])

const MATRIX_TIME_COL_RPX = 84
const HX_LABEL_FONT_MAX = 16
const HX_LABEL_FONT_MIN = 9
const YEAR_FONT_MAX = 14
const YEAR_FONT_MIN = 10
/** 与 .time-year 的 letter-spacing 保持一致，供自适应字号估算 */
const YEAR_LETTER_SPACING_RPX = 2

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
    units += (ch >= '0' && ch <= '9') ? 0.62 : 1
  }
  const spacingExtra = Math.max(0, s.length - 1) * YEAR_LETTER_SPACING_RPX
  const avail = MATRIX_TIME_COL_RPX - 8 - spacingExtra
  for (let fs = YEAR_FONT_MAX; fs >= YEAR_FONT_MIN; fs--) {
    if (units * fs * 1.06 <= avail) return fs
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
    lastScrollTopPx: data.lastScrollTopPx == null ? null : Number(data.lastScrollTopPx),
    lastNavActiveIdx: data.lastNavActiveIdx == null ? null : Number(data.lastNavActiveIdx),
    updatedAt: String(data.updatedAt || '').trim(),
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
    state.lastDynastyKey ||
    (state.lastNavActiveIdx != null && state.lastNavActiveIdx >= 0) ||
    (state.lastScrollTopPx != null && state.lastScrollTopPx > 0) ||
    (Array.isArray(state.collapsedDynastyKeys) && state.collapsedDynastyKeys.length) ||
    state.updatedAt
  )
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
  } else if (lScroll <= 0 && rScroll <= 0 && r.lastDynastyKey && !l.lastDynastyKey) {
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

  return normalizeHomeState({
    civilizationCode: viewport.civilizationCode || r.civilizationCode || l.civilizationCode,
    civId: viewport.civId || l.civId || r.civId,
    lastDynastyKey: viewport.lastDynastyKey || r.lastDynastyKey || l.lastDynastyKey,
    lastScrollTopPx: lScroll > 0 ? lScroll : (rScroll > 0 ? rScroll : (viewport.lastScrollTopPx != null ? viewport.lastScrollTopPx : null)),
    lastNavActiveIdx: l.lastNavActiveIdx != null ? l.lastNavActiveIdx : r.lastNavActiveIdx,
    collapsedDynastyKeys: collapsed,
    updatedAt: r.updatedAt || l.updatedAt,
  })
}

/** 保存时合并：折叠/朝代变更不应把有效 scrollTop 覆盖成 0 */
function mergePersistPayload(existing, next) {
  const prev = existing ? normalizeHomeState(existing) : null
  const cur = normalizeHomeState(next)
  if (!prev) return cur

  const prevScroll = prev.lastScrollTopPx > 0 ? prev.lastScrollTopPx : 0
  const curScroll = cur.lastScrollTopPx > 0 ? cur.lastScrollTopPx : 0
  const scrollTop = curScroll > 0 ? curScroll : prevScroll

  const prevNav = prev.lastNavActiveIdx != null && prev.lastNavActiveIdx >= 0 ? prev.lastNavActiveIdx : null
  const curNav = cur.lastNavActiveIdx != null && cur.lastNavActiveIdx >= 0 ? cur.lastNavActiveIdx : null
  const navIdx = curScroll > 0
    ? (curNav != null ? curNav : prevNav)
    : (curNav != null ? curNav : prevNav)

  let dynastyKey = cur.lastDynastyKey || prev.lastDynastyKey || ''
  if (curScroll > 0 && cur.lastDynastyKey) {
    dynastyKey = cur.lastDynastyKey
  } else if (curScroll <= 0 && prevScroll > 0 && prev.lastDynastyKey) {
    dynastyKey = prev.lastDynastyKey
  }

  return normalizeHomeState(Object.assign({}, cur, {
    lastScrollTopPx: scrollTop,
    lastNavActiveIdx: navIdx,
    lastDynastyKey: dynastyKey,
  }))
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
const STACK_CARD_H_RPX = Math.round(168 * STACK_UI_SCALE)  // 118
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
  return { civPickerCardW: cardW, civPickerCardH: cardHFinal, civPickerSheetH: sheetH }
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
    mode:              'immersive',
    civSpots:          OVERVIEW_CIV_SPOTS,
    overviewMapUrl:    DEFAULT_OVERVIEW_MAP,
    dynastyUnitMap:    {},
    stackMode:         STACK_MODE,
    // 层叠卡片模式数据
    civStackItems:     [],
    // 文字 Tab 数据（向下滑动后展示）
    civTextItems:      CIV_TABS.map((t, i) => ({ id: t.id, name: t.name, realIdx: i })),
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
    matrixTotalH:      0,
    matrixScrollBottomPad: 200,
    scrollAreaTop:     0,
    matrixHeight:      600,
    headerPadPx:       88,
    expandedDynasties: {},
    matrixDataLoading: true,
    civPickerOpen:     false,
    civPickerItems:    CIV_TABS.map((t, i) => Object.assign({}, t, { realIdx: i })),
    civPickerCardW:    156,
    civPickerCardH:    177,
    civPickerSheetH:   960,
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

    const navPx = navBarPx()
    const headerPadPx = statusBar + navPx
    const tabBarPx = CIV_TEXT_TAB_BAR_RPX * (sw / 750)
    const scrollAreaTop = headerPadPx + tabBarPx
    const matrixHeight = Math.max(200, windowHeight - scrollAreaTop)
    const matrixScrollBottomPad = calcMatrixScrollBottomPad(sw, safeBottomPx)
    const pickerMetrics = calcCivPickerMetrics(windowHeight, headerPadPx, sw)
    const cachedLocal = readLocalHomeState()
    this._cachedHomeState = cachedLocal
    const bootCiv = cachedLocal && cachedLocal.civId ? cachedLocal.civId : initialCiv
    const bootCivIndex = Math.max(0, CIV_TABS.findIndex(c => c.id === bootCiv))
    const bootExpanded = cachedLocal
      ? expandedFromCollapsed(bootCiv, cachedLocal.collapsedDynastyKeys)
      : defaultExpanded
    if (cachedLocal && cachedLocal.lastScrollTopPx > 0) {
      this._lastScrollTop = cachedLocal.lastScrollTopPx
    }
    if (cachedLocal && cachedLocal.lastDynastyKey) {
      this._lastDynastyKey = cachedLocal.lastDynastyKey
    }
    if (cachedLocal && cachedLocal.lastNavActiveIdx != null && cachedLocal.lastNavActiveIdx >= 0) {
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
      matrixOverlays:    [],
      matrixTotalH:      0,
    }, buildTabLayerStyles(0), pickerMetrics))

    this._tabAlpha = 0
    this._preloadCivImages()
    this._lastScrollTop = 0
    this._skipShowRefresh = true
    this._homeStateLoaded = false
    this._restoringHomeState = false
    this._homeStatePromise = this._loadHomeMatrixState()
    this._matrixDataPromise = this._refreshMatrixData()
    this._gridDataPromise = this._loadGridData()
    wx.nextTick(() => this._syncTabAlphaFromDom())
  },

  _loadGridData() {
    return request('/home/grid').then(res => {
      const data = (res && res.data) || {}
      const overview = data.overview || {}
      const mapUrl = String(overview.mapImageUrl || '').trim() || DEFAULT_OVERVIEW_MAP
      const dynastyUnitMap = buildDynastyUnitMap(data.cells || [])
      this._dynastyUnitMap = dynastyUnitMap
      this.setData({ overviewMapUrl: mapUrl, dynastyUnitMap })
    }).catch(err => {
      console.warn('[home] grid load failed', err)
      this._dynastyUnitMap = {}
    })
  },

  _loadHomeMatrixState() {
    const localState = readLocalHomeState()
    debugHomeState('启动读取本地', localState)
    if (this._homeMatrixRemoteUnavailable) {
      return Promise.resolve(localState)
    }
    const ensureToken = hasToken() ? Promise.resolve(true) : trySilentWxLogin()
    return ensureToken.then(ok => {
      if (!ok || !hasToken()) {
        return localState
      }
      return request(HOME_MATRIX_STATE_PATH, { auth: true }).then(res => {
        const remoteState = normalizeHomeState(res && res.data ? res.data : null)
        const merged = mergeHomeStates(localState, remoteState)
        if (merged && hasMeaningfulHomeState(merged)) {
          writeLocalHomeState(merged)
          return merged
        }
        return localState || remoteState
      }).catch(err => {
        if (isHomeMatrixApiMissing(err)) {
          this._homeMatrixRemoteUnavailable = true
          console.info('[home-state] 本地后端未部署 /me/home-matrix-state，仅使用本地 Storage（键名 homeMatrixState）')
          return localState
        }
        const msg = String(err && err.message || '')
        if (msg !== 'UNAUTHORIZED') {
          console.warn('[home] home matrix state load failed', err)
        }
        return localState
      })
    }).catch(() => localState)
  },

  /** 每次进入首页：云函数拉取王朝 / 帝王数据 */
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
    }, calcCivPickerMetrics(windowHeight, headerPadPx, sw)))

    const loadAfterData = (homeState) => {
      this._readyLoaded = true
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

  /** 构建并注入矩阵行（失败时降级为收起态） */
  _loadMatrix(civId, expandedDynasties, onReady) {
    const done = typeof onReady === 'function' ? onReady : null
    try {
      const layout = buildRows(civId, expandedDynasties || {})
      if (!layout.rows || !layout.rows.length) {
        console.error('[home-matrix] buildRows returned empty for', civId)
      }
      this.setData({
        matrixRows:       enrichMatrixRows(layout.rows     || []),
        // Phase 1/2: initialize nav data from rows
        navItems:         layout.rows
          ? buildNavFromRows(layout.rows, this._ratio || 0.5).navItems
          : this.data.navItems,
        matrixBlocks:     layout.blocks     || [],
        matrixOverlays:   layout.overlays     || [],
        matrixSubCards:   layout.subCards   || [],
        matrixTotalH:     layout.totalH     || 0,
        civScrollAnim: true,
      }, () => {
        this._cacheNavRect()
        if (done) done()
      })
    } catch (err) {
      console.error('[home-matrix] _loadMatrix failed', err)
      try {
        const layout = buildRows(civId, {})
        this.setData({
          matrixRows:       enrichMatrixRows(layout.rows     || []),
        // Phase 1/2: initialize nav data from rows
        navItems:         layout.rows
          ? buildNavFromRows(layout.rows, this._ratio || 0.5).navItems
          : this.data.navItems,
          matrixBlocks:     layout.blocks     || [],
          matrixOverlays:   layout.overlays     || [],
          matrixSubCards:   layout.subCards   || [],
          matrixTotalH:     layout.totalH     || 0,
          expandedDynasties: {},
        }, () => {
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
      ? expandedFromCollapsed(resolvedCiv, state.collapsedDynastyKeys)
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
        if (state && hasMeaningfulHomeState(state)) {
          this._restoreViewportFromState(state)
        } else if (!state) {
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
    if (!hasMeaningfulHomeState(normalized)) {
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

    if (normalized.lastScrollTopPx != null && normalized.lastScrollTopPx > 0) {
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
        navActiveIdx: navIdx >= 0 ? navIdx : this.data.navActiveIdx,
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
      if (diff > 12 && attempt < 6) {
        const patch = {
          navDragActive: true,
          matrixScrollTop: expectedTop + (attempt % 2 ? 1 : 0),
          navActiveIdx: navIdx >= 0 ? navIdx : that.data.navActiveIdx,
        }
        if (attempt >= 3 && scrollIntoView) {
          patch.matrixScrollIntoView = scrollIntoView
        }
        that.setData(patch, () => {
          if (patch.matrixScrollIntoView) {
            setTimeout(() => that.setData({ matrixScrollIntoView: '' }), 200)
          }
          setTimeout(function() {
            that._verifyScrollRestore(expectedTop, navIdx, scrollIntoView, attempt + 1)
          }, 220)
        })
        return
      }
      that._lastScrollTop = current > 0 ? current : expectedTop
      that._restoringHomeState = false
      that.setData({
        navDragActive: false,
        navActiveIdx: navIdx >= 0 ? navIdx : that.data.navActiveIdx,
      })
    }).exec()
  },

  _scrollToTop() {
    this._applyProgrammaticScroll({ scrollTop: 0, navIdx: 0, isRestore: true })
  },

  _scrollToDynastyStart(dynastyKey) {
    const key = String(dynastyKey || '').trim()
    if (!key) {
      this._scrollToTop()
      return
    }
    const ratio = this._ratio || 0.5
    const navItem = (this.data.navItems || []).find(item => item.key === key || item.label === key)
    const row = (this.data.matrixRows || []).find(r =>
      r.hxDynastyKey === key || r.dynastyKey === key || r.hxLabel === key
    )
    const rawTop = navItem ? navItem.yPx : (row ? Math.round((row.y || 0) * ratio) : 0)
    const maxScroll = Math.max(0, this.data.matrixTotalH * ratio - this.data.matrixHeight)
    const scrollTop = Math.max(0, Math.min(maxScroll, rawTop))
    this._restoringHomeState = true
    this.setData({
      matrixScrollTop: scrollTop,
      navDragActive: true,
    })
    this._lastScrollTop = scrollTop
    this._updateNavHighlight(scrollTop)
    this._releaseProgrammaticScrollLock()
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
  _syncScrollTopFromDom(done) {
    const finish = typeof done === 'function' ? done : function() {}
    try {
      wx.createSelectorQuery().in(this).select('#matrixScroll').scrollOffset(res => {
        if (res && res.scrollTop != null && !this._restoringHomeState) {
          this._lastScrollTop = res.scrollTop
          this._updateNavHighlight(res.scrollTop)
        }
        finish()
      }).exec()
    } catch {
      finish()
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
    this._syncScrollTopFromDom(() => this._writeHomeViewportState(syncRemote))
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
    if (
      !rawPayload.lastDynastyKey &&
      !rawPayload.lastScrollTopPx &&
      rawPayload.lastNavActiveIdx == null &&
      !(rawPayload.collapsedDynastyKeys || []).length
    ) {
      return
    }
    const existing = this._cachedHomeState || readLocalHomeState()
    const payload = mergePersistPayload(existing, rawPayload)
    writeLocalHomeState(payload)
    this._cachedHomeState = payload
    if (!syncRemote || !hasToken() || this._homeMatrixRemoteUnavailable) return
    request(HOME_MATRIX_STATE_PATH, {
      method: 'PUT',
      auth: true,
      data: {
        civilizationCode: payload.civilizationCode,
        lastDynastyKey: payload.lastDynastyKey,
        collapsedDynastyKeys: payload.collapsedDynastyKeys,
        lastScrollTopPx: payload.lastScrollTopPx,
      },
    }).catch(err => {
      if (isHomeMatrixApiMissing(err)) {
        this._homeMatrixRemoteUnavailable = true
        return
      }
      const msg = String(err && err.message || '')
      if (msg !== 'UNAUTHORIZED') {
        console.warn('[home] home matrix state save failed', err)
      }
    })
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

    this._refreshMatrixData().then(() => {
      if (this._readyLoaded) {
        const restoreState = this._cachedHomeState || readLocalHomeState()
        this._loadMatrix(this.data.activeCiv, this.data.expandedDynasties, () => {
          if (restoreState && hasMeaningfulHomeState(restoreState)) {
            this._restoreViewportFromState(restoreState)
          }
        })
      }
    })
  },

  onUnload() {
    if (this._matrixLoadTimer) clearTimeout(this._matrixLoadTimer)
    if (this._civSwitchTimer) clearTimeout(this._civSwitchTimer)
    if (this._homeStateSaveTimer) clearTimeout(this._homeStateSaveTimer)
    if (this._homeStateScrollTimer) clearTimeout(this._homeStateScrollTimer)
    this._syncScrollTopFromDom(() => this._persistHomeViewportState(true))
  },

  onHide() {
    this._syncScrollTopFromDom(() => this._persistHomeViewportState(true))
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

  _selectCiv(activeCiv, civIndex) {
    if (civIndex === this.data.civIndex && activeCiv === this.data.activeCiv) return
    const expandedDynasties = buildAllExpanded(activeCiv)
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
      this._wasSwiped  = true
      const delta  = dx < 0 ? 1 : -1
      const newIdx = ((this.data.civIndex + delta) + N) % N
      this._selectCiv(CIV_TABS[newIdx].id, newIdx)
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
    if (detailTop > 0 || !this._lastScrollTop) {
      this._lastScrollTop = detailTop
    }
    const scrollTop = this._lastScrollTop
    this._applyTabAlphaFromScroll(scrollTop)
    if (!this._restoringHomeState) {
      this._updateNavHighlight(scrollTop)
      this._scheduleHomeMatrixStateSave()
    }
    // nav 已收起但 navDragActive 仍锁定 → 用户手动滚动时释放（恢复期间不可打断）
    if (!this._restoringHomeState && this.data.navDragActive && !this.data.navActive && !this._navPendingActivation) {
      this.setData({ navDragActive: false })
    }
    // 用户手动滚动时收起导航栏（非 drag 状态）
    if (this.data.navActive && !this._navMoved && !this._isNavDragging) {
      this.setData({ navActive: false })
      this._hideNavHud()
    }
  },

  // 滚动结束后从 DOM 读取真实位置再保存（enhanced scroll-view 的 detail.scrollTop 可能不准）
  onMatrixScrollEnd() {
    if (this._restoringHomeState) return
    this._syncScrollTopFromDom(() => {
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
    const dynasty = ds.dynasty || ds.displayName || ''
    const person = ds.person || ''
    if (!dynasty && !person && !ds.entityId) return

    const map = this._dynastyUnitMap || this.data.dynastyUnitMap || {}
    const unitId = resolveNavigationUnitId({
      entityType: ds.entityType,
      entityId: ds.entityId,
      legacyId: ds.legacyId,
      dynastyId: ds.dynastyId,
      person,
      dynasty,
      displayName: ds.displayName,
    }, map)

    if (unitId) {
      let url = `/pages/dynasty-detail/index?unitId=${encodeURIComponent(unitId)}`
      const label = dynasty || ds.displayName || person
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
    // 长按激活了导航栏 → 不执行展开收起
    if (this._navPendingActivation) {
      this._navPendingActivation = false
      return
    }
    const dynastyKey = e.currentTarget.dataset.dynasty
    if (!dynastyKey) return
    const civTab = CIV_TABS[this.data.civIndex]
    const civName = civTab ? civTab.name : '华夏'
    const expanded = toggleDynastyExpanded(dynastyKey, this.data.expandedDynasties, civName)
    this.setData({ expandedDynasties: expanded })
    this._lastDynastyKey = dynastyKey
    this._loadMatrix(this.data.activeCiv, expanded, () => {
      this._syncScrollTopFromDom(() => this._persistHomeViewportState(true))
    })
  },
  noop() {}
})
