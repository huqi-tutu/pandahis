const protoPage = require('../../behaviors/proto-page.js')
const { navBarPx } = require('../../utils/layout.js')
const { CIV_TABS, buildRows, initialCiv, buildAllExpanded, toggleDynastyExpanded } = require('../../data/mock-home-matrix.js')
const { fetchHomeMatrixData } = require('../../utils/matrix-cloud.js')
const dynastyRaw = require('../../data/dynasty-data.js')

const DYNASTY_ID_BY_NAME = (() => {
  const map = {}
  for (const d of dynastyRaw || []) {
    const id = d.dynastyId
    if (!id) continue
    if (d.name) map[String(d.name).trim()] = id
    if (d.dynasty) map[String(d.dynasty).trim()] = id
    if (d.dynasty2) map[String(d.dynasty2).trim()] = id
  }
  return map
})()

// ─────────────────────────────────────────────────────────────────────────────
// 【旧版】横向滑动模式常量（stackMode=false 时使用）
// ─────────────────────────────────────────────────────────────────────────────
const CIV_CARD_W_RPX   = 130
const CIV_CARD_GAP_RPX = 16
const CIV_TAB_BAR_RPX  = 180

const N = CIV_TABS.length  // 18

/** 时间轴列宽（rpx），与 home-matrix.wxss 中 .matrix-time-col 保持一致 */
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
const STACK_MAX_D      = 4     // 最多展示左右各 4 张

// 文字 Tab 常量（向下滑动后展示）
const TEXT_ITEM_W_RPX  = 72
const TEXT_ITEM_GAP_RPX = 10

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
  return Math.max(0, mid - screenW / 2)
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

// ─── 切换模式：true = 层叠卡片，false = 横向滑动（回退）─────────────
const STACK_MODE = true

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
    stackMode:         STACK_MODE,
    // 层叠卡片模式数据
    civStackItems:     [],
    // 文字 Tab 数据（向下滑动后展示）
    civTextItems:      CIV_TABS.map((t, i) => ({ id: t.id, name: t.name, realIdx: i })),
    civTextScrollLeft: 0,
    // 图片→文字渐变进度（0=图片，1=文字），由 onMatrixScroll 驱动
    tabAlpha:          0,
    stackLayerStyle:   'opacity:1;transform:translateY(0px);z-index:2;',
    textLayerStyle:    'opacity:0;transform:translateY(14px);pointer-events:none;z-index:1;',
    // Tab 栏当前高度 rpx（随滚动从 STACK_BAR_RPX 缩至 TEXT_BAR_RPX）
    tabAreaH:          STACK_BAR_RPX,
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
    matrixOverlays:    [],
    matrixTotalH:      0,
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
    try {
      const sys = wx.getSystemInfoSync()
      sw = sys.windowWidth
      statusBar = sys.statusBarHeight || 20
      windowHeight = sys.windowHeight
    } catch (e) {}

    this._screenW = sw
    this._statusBarH = statusBar
    this._windowHeight = windowHeight
    this._ratio = sw / 750
    this._navPx = navBarPx()
    this._pendingExpanded = defaultExpanded

    const navPx = navBarPx()
    const headerPadPx = statusBar + navPx
    const tabBarPx = STACK_BAR_RPX * (sw / 750)
    const scrollAreaTop = headerPadPx + tabBarPx
    const matrixHeight = Math.max(200, windowHeight - scrollAreaTop)
    const pickerMetrics = calcCivPickerMetrics(windowHeight, headerPadPx, sw)

    this.setData(Object.assign({
      activeCiv:         initialCiv,
      civIndex:          0,
      expandedDynasties: defaultExpanded,
      civStackItems:     buildStackItems(0, sw),
      civTabsLoop:       buildLoopItems(0),
      civScrollLeft:     calcCivScroll(0, sw),
      civScrollAnim:     false,
      scrollAreaTop,
      matrixHeight,
      scrollRatio:       sw / 750,
      statusBarPx:       statusBar,
      windowHeightPx:    windowHeight,
      matrixRows:        [],
      matrixBlocks:      [],
      matrixTotalH:      0,
    }, buildTabLayerStyles(0), pickerMetrics))

    this._tabAlpha = 0
    this._preloadCivImages()
    this._skipShowRefresh = true
    this._matrixDataPromise = this._refreshMatrixData()
    wx.nextTick(() => this._syncTabAlphaFromDom())
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
    try {
      const sys = wx.getSystemInfoSync()
      windowHeight = sys.windowHeight
      statusBar = sys.statusBarHeight || 20
      sw = sys.windowWidth
      this._screenW = sw
      this._statusBarH = statusBar
      this._windowHeight = windowHeight
      this._ratio = sw / 750
    } catch (e) {}

    const navPx = this._navPx || navBarPx()
    const headerPadPx = statusBar + navPx
    const tabBarPx = (this.data.stackMode ? STACK_BAR_RPX : CIV_TAB_BAR_RPX) * (sw / 750)
    const scrollAreaTop = headerPadPx + tabBarPx
    const matrixHeight = Math.max(200, windowHeight - scrollAreaTop)
    this.setData(Object.assign({
      scrollAreaTop,
      matrixHeight,
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
        matrixRows:     enrichMatrixRows(layout.rows     || []),
        matrixBlocks:   layout.blocks   || [],
        matrixOverlays: layout.overlays || [],
        matrixTotalH:   layout.totalH   || 0,
        civScrollAnim: true,
      })
    } catch (err) {
      console.error('[home-matrix] _loadMatrix failed', err)
      try {
        const layout = buildRows(civId, {})
        this.setData({
          matrixRows:     enrichMatrixRows(layout.rows     || []),
          matrixBlocks:   layout.blocks   || [],
          matrixOverlays: layout.overlays || [],
          matrixTotalH:   layout.totalH   || 0,
          expandedDynasties: {},
        })
      } catch (err2) {
        console.error('[home-matrix] fallback load failed', err2)
      }
    }
  },

  /** 根据矩阵 scrollTop 同步图片 Tab / 文字 Tab 渐隐状态 */
  _applyTabAlphaFromScroll(scrollTop, force) {
    const THRESHOLD = 130
    const raw  = Math.min(1, Math.max(0, (scrollTop || 0) / THRESHOLD))
    const next = Math.round(raw * 100) / 100
    if (!force && Math.abs(next - (this._tabAlpha || 0)) < 0.02) return
    this._tabAlpha = next
    const r          = this._ratio      || 0.5
    const statusBarH = this._statusBarH || 20
    const tabAreaH      = Math.round(STACK_BAR_RPX - next * (STACK_BAR_RPX - TEXT_BAR_RPX))
    const scrollAreaTop = statusBarH + (this._navPx || navBarPx()) + tabAreaH * r
    const matrixHeight = Math.max(200, (this._windowHeight || 667) - scrollAreaTop)
    this.setData(Object.assign(
      { tabAreaH, scrollAreaTop, matrixHeight },
      buildTabLayerStyles(next)
    ))
  },

  _syncTabAlphaFromDom() {
    if (!this.data.stackMode) return
    wx.nextTick(() => {
      wx.createSelectorQuery()
        .in(this)
        .select('#matrixScroll')
        .scrollOffset(res => {
          if (res && res.scrollTop != null) {
            this._applyTabAlphaFromScroll(res.scrollTop, true)
          }
        })
        .exec()
    })
  },

  onShow() {
    const app = getApp()
    const pending = app.globalData && app.globalData.pendingCiv
    if (pending && pending !== this.data.activeCiv) {
      const idx = CIV_TABS.findIndex(c => c.id === pending)
      if (idx >= 0) this._selectCiv(CIV_TABS[idx].id, idx)
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

    // 先启动卡片动画，延迟矩阵重建避免阻塞动画帧
    this._applyStackStyles(civIndex, sw)
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
  onMatrixScroll(e) {
    this._applyTabAlphaFromScroll(e.detail.scrollTop)
  },

  // 滚动结束后补一次同步，覆盖惯性滚动末帧
  onMatrixScrollEnd(e) {
    const scrollTop = (e && e.detail && e.detail.scrollTop) || 0
    this._applyTabAlphaFromScroll(scrollTop, true)
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
    wx.navigateTo({ url: '/pages/home-overview/home-overview' })
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

  _resolveDynastyId(name) {
    const k = String(name || '').trim()
    if (!k) return ''
    if (DYNASTY_ID_BY_NAME[k]) return DYNASTY_ID_BY_NAME[k]
    for (const [title, id] of Object.entries(DYNASTY_ID_BY_NAME)) {
      if (title.includes(k) || k.includes(title)) return id
    }
    return ''
  },

  onCardTap(e) {
    const ds = e.currentTarget.dataset || {}
    if (!ds.dynasty && !ds.dynastyId) return
    this._openDynastyDetail(ds.dynasty, ds.anchorYear, ds.dynastyId)
  },

  onMiniTap(e) {
    const ds = e.currentTarget.dataset || {}
    if (!ds.dynasty && !ds.dynastyId) return
    this._openDynastyDetail(ds.dynasty, ds.anchorYear, ds.dynastyId)
  },

  _openDynastyDetail(dynasty, anchorYear, dynastyId) {
    const id = dynastyId || this._resolveDynastyId(dynasty)
    if (!id) {
      wx.showToast({ title: '未找到朝代 ID', icon: 'none' })
      return
    }
    let url = `/pages/dynasty-detail/dynasty-detail?unitId=${encodeURIComponent(id)}`
    if (dynasty) {
      url += `&dynasty=${encodeURIComponent(String(dynasty))}`
    }
    if (anchorYear != null && anchorYear !== '') {
      url += `&anchorYear=${encodeURIComponent(String(anchorYear))}`
    }
    wx.navigateTo({ url })
  },

  // 展开/收起华夏某朝代（点击时间轴朝代名旁箭头触发）
  onDynastyToggle(e) {
    const dynastyKey = e.currentTarget.dataset.dynasty
    if (!dynastyKey) return
    const civTab = CIV_TABS[this.data.civIndex]
    const civName = civTab ? civTab.name : '华夏'
    const expanded = toggleDynastyExpanded(dynastyKey, this.data.expandedDynasties, civName)
    this.setData({ expandedDynasties: expanded })
    this._loadMatrix(this.data.activeCiv, expanded)
  }
})
