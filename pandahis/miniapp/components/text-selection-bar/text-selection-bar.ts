Component({
  properties: {
    visible: {
      type: Boolean,
      value: false,
    },
    left: {
      type: Number,
      value: 0,
    },
    top: {
      type: Number,
      value: 0,
    },
  },
  methods: {
    noop() {},
    onCopy() {
      this.triggerEvent('copy')
    },
    onShare() {
      this.triggerEvent('share')
    },
    onQuery() {
      this.triggerEvent('query')
    },
    onCorrection() {
      this.triggerEvent('correction')
    },
  },
})
