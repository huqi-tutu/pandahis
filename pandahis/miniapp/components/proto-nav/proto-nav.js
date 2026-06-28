Component({
  properties: {
    title: {
      type: String,
      value: ''
    },
    /** 首页类：左 slot + 标题绝对居中 */
    homeNav: {
      type: Boolean,
      value: false
    },
    showBack: {
      type: Boolean,
      value: false
    },
    /** 右侧占位宽度，避免标题与胶囊错位（可选） */
    rightWidthRpx: {
      type: Number,
      value: 0
    },
    /** homeNav 时左上角模式切换文案（不用 slot，避免插槽不渲染） */
    modePillText: {
      type: String,
      value: ''
    },
    /** homeNav 时左上角模式切换图标（优先于 modePillText） */
    modePillIcon: {
      type: String,
      value: ''
    },
    rightPillText: {
      type: String,
      value: ''
    }
  },

  data: {
    statusBarHeight: 20
  },

  lifetimes: {
    attached() {
      try {
        const statusBarHeight =
          typeof wx.getWindowInfo === 'function'
            ? wx.getWindowInfo().statusBarHeight
            : wx.getSystemInfoSync().statusBarHeight
        this.setData({ statusBarHeight: statusBarHeight || 20 })
      } catch (e) {
        this.setData({ statusBarHeight: 20 })
      }
    }
  },

  methods: {
    onBack() {
      wx.navigateBack({
        fail: () => {
          wx.switchTab({ url: '/pages/home/index' })
        }
      })
    },

    onModePillTap() {
      this.triggerEvent('modepilltap')
    },

    onRightPillTap() {
      this.triggerEvent('rightpilltap')
    }
  }
})
