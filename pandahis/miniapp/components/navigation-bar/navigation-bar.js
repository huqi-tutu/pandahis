Component({
  options: {
    multipleSlots: true,
  },
  properties: {
    extClass: { type: String, value: '' },
    title: { type: String, value: '' },
    background: { type: String, value: '' },
    color: { type: String, value: '' },
    back: { type: Boolean, value: true },
    loading: { type: Boolean, value: false },
    homeButton: { type: Boolean, value: false },
    animated: { type: Boolean, value: true },
    show: {
      type: Boolean,
      value: true,
      observer: '_showChange',
    },
    delta: { type: Number, value: 1 },
  },
  data: {
    displayStyle: '',
    navStyle: '',
    ios: true,
  },
  lifetimes: {
    attached() {
      const rect = wx.getMenuButtonBoundingClientRect()
      wx.getSystemInfo({
        success: (res) => {
          const statusBarHeight = res.statusBarHeight || 0
          const menuGap = Math.max(0, rect.top - statusBarHeight)
          const navContentHeight = menuGap * 2 + rect.height
          const totalHeight = statusBarHeight + navContentHeight
          const paddingRight = Math.max(0, res.windowWidth - rect.left)
          const paddingLeft = Math.max(0, res.windowWidth - rect.right)
          this.setData(
            {
              ios: res.platform !== 'android',
              navMetrics: {
                totalHeight,
                statusBarHeight,
                paddingLeft,
                paddingRight,
              },
            },
            this._recomputeStyle
          )
        },
      })
    },
  },
  methods: {
    _recomputeStyle() {
      const color = this.properties.color || ''
      const background = this.properties.background || ''
      const displayStyle = this.data.displayStyle || ''
      const metrics = this.data.navMetrics
      const parts = [`color: ${color}`, `background: ${background}`, displayStyle]
      if (metrics) {
        parts.push(
          `height: ${metrics.totalHeight}px`,
          `padding-top: ${metrics.statusBarHeight}px`,
          `padding-left: ${metrics.paddingLeft}px`,
          `padding-right: ${metrics.paddingRight}px`
        )
      }
      this.setData({ navStyle: parts.filter(Boolean).join('; ') })
    },
    _showChange(show) {
      const animated = this.data.animated
      let displayStyle = ''
      if (animated) {
        displayStyle = `opacity: ${show ? '1' : '0'};transition:opacity 0.5s;`
      } else {
        displayStyle = `display: ${show ? '' : 'none'}`
      }
      this.setData({ displayStyle }, this._recomputeStyle)
    },
    back() {
      const data = this.data
      if (data.delta) {
        wx.navigateBack({ delta: data.delta })
      }
      this.triggerEvent('back', { delta: data.delta }, {})
    },
  },
})
