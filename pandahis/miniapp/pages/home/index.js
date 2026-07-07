const protoPage = require('../../behaviors/proto-page.js')
const { navBarPx } = require('../../native-utils/matrix/layout.js')
const { CIV_TABS, buildRows, initialCiv, buildAllExpanded, toggleDynastyExpanded } = require('../../native-utils/matrix/mock-home-matrix.js')
const { fetchHomeMatrixData } = require('../../native-utils/matrix/matrix-cloud.js')
const { request } = require('../../native-utils/api.js')
const { buildNavFromRows, findActiveNavIndex } = require('../../native-utils/matrix/dynasty-nav-data.js')
const {
  OVERVIEW_CIV_SPOTS,
  OVERVIEW_SPOT_TO_MATRIX_SLUG,
  buildDynastyUnitMap,
  resolveNavigationUnitId,
} = require('./matrix-adapter.js')

const DEFAULT_OVERVIEW_MAP = '/images/world-history-dynasty-map.png'

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

    this.setData(Object.assign({
      activeCiv:         initialCiv,
      civIndex:          0,
      expandedDynasties: defaultExpanded,
      tabAreaH:          CIV_TEXT_TAB_BAR_RPX,
      civStackItems:     [],
      civTabsLoop:       buildLoopItems(0),
      civScrollLeft:     calcCivScroll(0, sw),
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

    const loadAfterData = () => {
      this._readyLoaded = true
      this._loadMatrix(this.data.activeCiv, this._pendingExpanded || this.data.expandedDynasties)
    }
    if (this._matrixDataPromise) {
      this._matrixDataPromise.then(loadAfterData).catch(loadAfterData)
    } else {
      loadAfterData()
    }
  },

  /** 构建并注入矩阵行（失败时降级为收起态） */
  _loadMatrix(civId, expandedDynasties) {
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
      })
      this._cacheNavRect()
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
        })
      } catch (err2) {
        console.error('[home-matrix] fallback load failed', err2)
      }
    }
  },

  /** 文字 Tab 固定展示，矩阵滚动不再切换 Tab 形态 */

  // ─── 导航高亮更新 ──────────────────────────────────────────────
  _updateNavHighlight(scrollTopPx) {
    const activeIdx = findActiveNavIndex(scrollTopPx, this.data.navItems)
    if (activeIdx !== this.data.navActiveIdx) {
      this.setData({ navActiveIdx: activeIdx })
    }
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
        this._loadMatrix(this.data.activeCiv, this.data.expandedDynasties)
      }
    })
  },

  onUnload() {
    if (this._matrixLoadTimer) clearTimeout(this._matrixLoadTimer)
    if (this._civSwitchTimer) clearTimeout(this._civSwitchTimer)
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
    const expandedDynasties = activeCiv === 'huaxia' ? buildAllExpanded('huaxia') : {}
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
    const scrollTop = e.detail.scrollTop
    this._lastScrollTop = scrollTop
    this._applyTabAlphaFromScroll(scrollTop)
    this._updateNavHighlight(scrollTop)
    // nav 已收起但 navDragActive 仍锁定 → 用户手动滚动时释放
    if (this.data.navDragActive && !this.data.navActive && !this._navPendingActivation) {
      this.setData({ navDragActive: false })
    }
    // 用户手动滚动时收起导航栏（非 drag 状态）
    if (this.data.navActive && !this._navMoved && !this._isNavDragging) {
      this.setData({ navActive: false })
      this._hideNavHud()
    }
  },

  // 滚动结束后补一次同步，覆盖惯性滚动末帧
  onMatrixScrollEnd(e) {
    const scrollTop = (e && e.detail && e.detail.scrollTop) || 0
    this._applyTabAlphaFromScroll(scrollTop, true)
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
    // 更新高亮和 HUD
    this.setData({ navActiveIdx: idx })
    this._showNavHud(navItems[idx])
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
    const yearStr = start < 0
      ? '前' + (-start) + (endYear ? ' — ' + (endYear < 0 ? '前' + (-endYear) : '' + endYear) : '')
      : '' + start + (endYear ? ' — ' + endYear : '')
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
    this._loadMatrix(this.data.activeCiv, expanded)
  },
  noop() {}
})
