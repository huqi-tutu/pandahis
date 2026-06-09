const protoPage = require('../../behaviors/proto-page.js')
const { buildSwimData } = require('../../data/mock-dynasty.js')

const CONCURRENT_TAB_H = 36
const SWIM_SHEET_RPX = 1440

/** 锚点年份 → 泳道横向 scroll-left（px） */
function computeAnchorScrollLeft(anchorYear, startYear, endYear, viewportWidthPx) {
  const year = Number(anchorYear)
  if (!year || Number.isNaN(year)) return 0

  const span = endYear - startYear
  if (span <= 0) return 0

  const sys = wx.getSystemInfoSync()
  const rpx = sys.windowWidth / 750
  const sheetPx = SWIM_SHEET_RPX * rpx
  const clamped = Math.max(startYear, Math.min(endYear, year))
  const targetPx = ((clamped - startYear) / span) * sheetPx
  const bias = viewportWidthPx * 0.32

  return Math.max(0, Math.min(targetPx - bias, Math.max(0, sheetPx - viewportWidthPx)))
}

Page({
  behaviors: [protoPage],

  data: {
    dynasty:        null,
    scrollTop:      0,
    axisPinned:     false,
    swimScrollLeft: 0,
    pageScrollTop:  0,
    isFavorite:     false,
    overlayVisible: false,
    overlayLabel:   '',
    overlayBars:    [],
  },

  onLoad(options) {
    const dynastyName = decodeURIComponent(options.dynasty || '北宋')
    const parsed = parseInt(options.anchorYear, 10)
    this._anchorYear = Number.isNaN(parsed) ? null : parsed

    const d = buildSwimData(dynastyName)
    this.setData({ dynasty: d })
  },

  onReady() {
    try {
      const sys = wx.getSystemInfoSync()
      const statusBar = sys.statusBarHeight || 20
      const top = statusBar + 44 + CONCURRENT_TAB_H
      this.setData({ scrollTop: top }, () => {
        setTimeout(() => {
          this.checkAxisPinned()
          if (this._anchorYear != null) this.scrollToAnchorYear()
        }, 80)
      })
    } catch (e) {
      this.setData({ scrollTop: 118 }, () => {
        setTimeout(() => {
          this.checkAxisPinned()
          if (this._anchorYear != null) this.scrollToAnchorYear()
        }, 80)
      })
    }
  },

  /** 首页带入 anchorYear：纵向滚到泳道区 + 横向锚定时间轴 */
  scrollToAnchorYear() {
    const d = this.data.dynasty
    if (!d || this._anchorYear == null) return

    const query = wx.createSelectorQuery().in(this)
    query.select('.dyn-swim-hscroll').boundingClientRect()
    query.select('.dyn-swim-matrix').boundingClientRect()
    query.select('.dynasty-scroll').scrollOffset()
    query.exec((res) => {
      const hRect = res && res[0]
      const matrixRect = res && res[1]
      const scroll = res && res[2]
      const sys = wx.getSystemInfoSync()
      const viewportW = (hRect && hRect.width) ? hRect.width : sys.windowWidth

      const scrollLeft = computeAnchorScrollLeft(
        this._anchorYear,
        d.startYear,
        d.endYear,
        viewportW,
      )

      const updates = { swimScrollLeft: scrollLeft }

      if (matrixRect && scroll) {
        const pageTop = this.data.scrollTop || 0
        const matrixTopInScroll = scroll.scrollTop + matrixRect.top - pageTop
        updates.pageScrollTop = Math.max(0, Math.round(matrixTopInScroll - 8))
      }

      this.setData(updates, () => {
        setTimeout(() => this.checkAxisPinned(), 100)
      })
    })
  },

  onDynastyScroll() {
    if (this._axisScrollTimer) return
    this._axisScrollTimer = setTimeout(() => {
      this._axisScrollTimer = null
      this.checkAxisPinned()
    }, 16)
  },

  /** scroll-view 内 sticky 不可靠：滚到顶后切换 fixed 时间轴 */
  checkAxisPinned() {
    const query = wx.createSelectorQuery().in(this)
    query.select('.dyn-swim-stick-head').boundingClientRect()
    query.exec((res) => {
      const rect = res && res[0]
      if (!rect || rect.height <= 0) return

      const viewportTop = this.data.scrollTop || 0
      const pinned = rect.top <= viewportTop + 1
      if (pinned !== this.data.axisPinned) {
        this.setData({ axisPinned: pinned })
      }
    })
  },

  _syncHScroll(scrollLeft) {
    if (this._hScrollLock) return
    if (Math.abs(scrollLeft - this.data.swimScrollLeft) < 1) return

    this._hScrollLock = true
    this.setData({ swimScrollLeft: scrollLeft }, () => {
      setTimeout(() => { this._hScrollLock = false }, 60)
    })
  },

  onSwimHScroll(e) {
    this._syncHScroll(e.detail.scrollLeft)
  },

  onAxisHScroll(e) {
    this._syncHScroll(e.detail.scrollLeft)
  },

  goNext() {
    const next = this.data.dynasty && this.data.dynasty.next
    if (next && next.dynasty) {
      wx.navigateTo({
        url: `/pages/dynasty-detail/dynasty-detail?dynasty=${encodeURIComponent(next.dynasty)}`
      })
    }
  },

  toggleFavorite() {
    const next = !this.data.isFavorite
    this.setData({ isFavorite: next })
    wx.showToast({
      title: next ? '已收藏' : '已取消收藏',
      icon: 'none',
      duration: 1200,
    })
  },

  onShare() {
    wx.showShareMenu({ withShareTicket: true })
  },

  showMoreOverlay(e) {
    const { lane, label } = e.currentTarget.dataset
    const extraBars = this.data.dynasty.lanes[lane].extraBars
    this.setData({
      overlayVisible: true,
      overlayLabel:   label,
      overlayBars:    extraBars,
    })
  },

  hideOverlay() {
    this.setData({ overlayVisible: false })
  },

  onBarTap(e) {
    const { boxKey, boxTitle } = e.currentTarget.dataset
    if (!boxKey && !boxTitle) return
    wx.navigateTo({
      url: `/pages/box-detail/box-detail?title=${encodeURIComponent(boxTitle || '')}`
    })
  },
})
