const protoPage = require('../../behaviors/proto-page.js')

Page({
  behaviors: [protoPage],

  data: {
    title: '',
    author: '',
    book: '',
    era: '',
    body: '',
  },

  onLoad(options) {
    const title   = options.title   ? decodeURIComponent(options.title)   : ''
    const author  = options.author  ? decodeURIComponent(options.author)  : ''
    const book    = options.book    ? decodeURIComponent(options.book)    : ''
    const era     = options.era     ? decodeURIComponent(options.era)     : ''
    const content = options.content ? decodeURIComponent(options.content) : '暂无评述内容。'

    this.setData({ title, author, book, era, body: content })
  },
})
