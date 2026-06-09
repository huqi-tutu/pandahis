const urls = {
  home: '/pages/home-matrix/home-matrix',
  search: '/pages/search/search',
  vip: '/pages/vip/vip',
  mine: '/pages/mine/mine'
}

function go(tab) {
  wx.switchTab({ url: urls[tab] })
}

module.exports = { urls, go }
