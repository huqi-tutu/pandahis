const protoPage = require('../../behaviors/proto-page.js')

Page({
  behaviors: [protoPage],

  data: {
    filled: 1,
    complete: false,
    slots: [
      { filled: true },
      { filled: false },
      { filled: false },
      { filled: false },
    ],
  },

  onInvite() {
    wx.showShareMenu({ withShareTicket: true })
  },

  simulateComplete() {
    this.setData({
      filled: 4,
      complete: true,
      slots: [
        { filled: true },
        { filled: true },
        { filled: true },
        { filled: true },
      ]
    })
  },
})
