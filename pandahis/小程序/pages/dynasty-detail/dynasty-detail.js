const protoPage = require('../../behaviors/proto-page.js')
const { request } = require('../../utils/api.js')
const { encodePathSegment } = require('../../utils/encode-path-segment.js')
const { mapHeroSwimToDynasty } = require('./dynasty-api-adapter.js')

const CONCURRENT_TAB_H = 36
const SWIM_SHEET_RPX = 1440

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
    loadError:      '',
    scrollTop:      0,
    axisPinned:     false,
    swimScrollLeft: 0,
    pageScrollTop:  0,
    isFavorite:     false,
    overlayVisible: false,
    overlayLabel:   '',
    overlayBars:    [],
  },

  async onLoad(options) {
    const unitId = options.unitId || options.dynastyId || ''
    const parsed = parseInt(options.anchorYear, 10)
    this._anchorYear = Number.isNaN(parsed) ? null : parsed

    if (!unitId) {
      this.setData({ loadError: '缺少朝代 ID，无法加载' })
      return
    }

    try {
      const enc = encodePathSegment(unitId)
      const [heroRes, swimRes] = await Promise.all([
        request(`/units/${enc}`),
        request(`/units/${enc}/swim-matrix`),
      ])
      const dynasty = mapHeroSwimToDynasty(heroRes.data, swimRes.data)
      this.setData({ dynasty, loadError: '' }, () => this._initScrollLayout())
    } catch (e) {
      console.error('[dynasty-detail] API failed', e)
      this.setData({
        dynasty: null,
        loadError: '无法加载朝代数据，请确认后端已启动且数据已导入',
      })
      wx.showToast({ title: '加载失败', icon: 'none' })
    }
  },

  onReady() {
    if (this.data.dynasty) this._initScrollLayout()
  },

  _initScrollLayout() {
    if (!this.data.dynasty) return
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

  scrollToAnchorYear() {
    const d = this.data.dynasty
    if (!d || this._anchorYear == null) return

    const query = wx.createSelectorQuery().in(this)
    query.select('.dyn-swim-hscroll').boundingClientRect()
    query.select('.dyn-swim-matrix').boundingClientRect()
    query.select('.dynasty-scroll').scrollOffset()
    query.exec((res) => {
      const hRect = res && res[0]
      const mRect = res && res[1]
      const scroll = res && res[2]
      if (!hRect || !mRect) return

      const sys = wx.getSystemInfoSync()
      const left = computeAnchorScrollLeft(
        this._anchorYear,
        d.startYear,
        d.endYear,
        sys.windowWidth
      )
      this.setData({ swimScrollLeft: left })

      const offsetY = (scroll && scroll.scrollTop) || 0
      const targetTop = Math.max(0, mRect.top + offsetY - this.data.scrollTop - 16)
      this.setData({ pageScrollTop: targetTop })
    })
  },

  checkAxisPinned() {
    const query = wx.createSelectorQuery().in(this)
    query.select('.dyn-swim-stick-head').boundingClientRect()
    query.exec((res) => {
      const rect = res && res[0]
      if (!rect) return
      const pinned = rect.top <= this.data.scrollTop + 2
      if (pinned !== this.data.axisPinned) {
        this.setData({ axisPinned: pinned })
      }
    })
  },

  onDynastyScroll(e) {
    this.checkAxisPinned()
  },

  onSwimHScroll(e) {
    this.setData({ swimScrollLeft: e.detail.scrollLeft })
  },

  onAxisHScroll(e) {
    this.setData({ swimScrollLeft: e.detail.scrollLeft })
  },

  onBarTap(e) {
    const ds = e.currentTarget.dataset || {}
    const boxId = ds.boxKey || ds.box || ''
    if (!boxId) {
      wx.showToast({ title: ds.title || '暂无详情', icon: 'none' })
      return
    }
    wx.navigateTo({ url: `/pages/box-detail/box-detail?boxId=${encodeURIComponent(boxId)}` })
  },

  showMoreOverlay(e) {
    const label = e.currentTarget.dataset.label
    const laneIdx = Number(e.currentTarget.dataset.lane)
    const lanes = (this.data.dynasty && this.data.dynasty.lanes) || []
    const lane = lanes[laneIdx]
    if (!lane) return
    const bars = (lane.extraBars && lane.extraBars.length)
      ? lane.extraBars
      : (lane.collapsedRows || []).flat()
    this.setData({ overlayVisible: true, overlayLabel: label, overlayBars: bars })
  },

  hideOverlay() {
    this.setData({ overlayVisible: false })
  },

  goNext() {
    const next = this.data.dynasty && this.data.dynasty.next
    if (!next || !next.dynasty) return
    wx.navigateTo({
      url: `/pages/dynasty-detail/dynasty-detail?unitId=${encodeURIComponent(next.dynasty)}&dynasty=${encodeURIComponent(next.title)}`,
    })
  },

  toggleFavorite() {
    this.setData({ isFavorite: !this.data.isFavorite })
  },

  onShare() {
    wx.showToast({ title: '分享功能开发中', icon: 'none' })
  },
})
