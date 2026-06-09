/** 与 proto-nav 一致：状态栏 + 88rpx 导航行（随屏宽换算 px） */
function headerOffsetPx() {
  try {
    const sys = wx.getSystemInfoSync()
    const navPx = 88 * (sys.windowWidth / 750)
    return (sys.statusBarHeight || 20) + navPx
  } catch (e) {
    return 88
  }
}

/** 导航栏内容区高度 px（不含状态栏），与 home-matrix 矩阵 top 计算对齐 */
function navBarPx() {
  try {
    const sys = wx.getSystemInfoSync()
    return 88 * (sys.windowWidth / 750)
  } catch (e) {
    return 44
  }
}

module.exports = {
  headerOffsetPx,
  navBarPx,
}
