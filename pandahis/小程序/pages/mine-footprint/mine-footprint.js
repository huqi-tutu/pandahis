const protoPage = require('../../behaviors/proto-page.js')

Page({
  behaviors: [protoPage],

  data: {
    summary: '共 127 条 · 按访问时间由近及远',
    list: [
      { title: '乌台诗案', time: '刚刚', era: '1079 — 1080', path: '华夏 ＞ 宋 ＞ 宋神宗 ＞ 事略' },
      { title: '王安石变法', time: '18 分钟前', era: '1069 — 1085', path: '华夏 ＞ 宋 ＞ 宋神宗 ＞ 典制' },
      { title: '苏轼贬黄州', time: '昨天', era: '1080 — 1084', path: '华夏 ＞ 宋 ＞ 宋神宗 ＞ 士臣' },
      { title: '贞观之治', time: '05-03', era: '627 — 649', path: '华夏 ＞ 唐 ＞ 唐太宗 ＞ 事略' }
    ]
  }
})
