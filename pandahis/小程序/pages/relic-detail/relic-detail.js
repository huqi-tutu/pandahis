const protoPage = require('../../behaviors/proto-page.js')

Page({
  behaviors: [protoPage],

  data: {
    name: '',
    museum: '',
    detail: '',
  },

  onLoad(options) {
    const name     = options.name     ? decodeURIComponent(options.name)     : ''
    const location = options.location ? decodeURIComponent(options.location) : ''
    const detail   = options.detail   ? decodeURIComponent(options.detail)   : '暂无详细介绍。'

    this.setData({ name, museum: location, detail })
  },
})
