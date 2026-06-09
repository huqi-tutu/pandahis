const { headerOffsetPx } = require('../utils/layout.js')

module.exports = Behavior({
  data: {
    headerPadPx: 88
  },
  lifetimes: {
    attached() {
      this.setData({ headerPadPx: headerOffsetPx() })
    }
  }
})
