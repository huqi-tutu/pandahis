const protoPage = require('../../behaviors/proto-page.js')

Page({
  behaviors: [protoPage],

  data: {
    tab: 0,
    dynasties: [
      { title: '宋', time: '今天', era: '960 — 1279', path: '一级文明归属：华夏' },
      { title: '唐', time: '昨天', era: '618 — 907', path: '一级文明归属：华夏' }
    ],
    boxes: [
      { title: '乌台诗案', time: '05-03', era: '1079 — 1080', path: '华夏 ＞ 宋 ＞ 宋神宗' },
      { title: '黄州寒食帖', time: '05-01', era: '1082 — 1082', path: '华夏 ＞ 宋 ＞ 宋神宗' }
    ]
  },

  switchTab(e) {
    this.setData({ tab: Number(e.currentTarget.dataset.i) })
  }
})
