function readWindowMetrics() {
  try {
    if (typeof wx.getWindowInfo === 'function') {
      const w = wx.getWindowInfo()
      return {
        windowWidth: w.windowWidth || 375,
        statusBarHeight: w.statusBarHeight || 20,
      }
    }
  } catch (e) {
    // fall through
  }
  try {
    const sys = wx.getSystemInfoSync()
    return {
      windowWidth: sys.windowWidth || 375,
      statusBarHeight: sys.statusBarHeight || 20,
    }
  } catch (e) {
    return { windowWidth: 375, statusBarHeight: 20 }
  }
}

/** 与 proto-nav 一致：状态栏 + 88rpx 导航行（随屏宽换算 px） */
function headerOffsetPx() {
  const { windowWidth, statusBarHeight } = readWindowMetrics()
  const navPx = 88 * (windowWidth / 750)
  return statusBarHeight + navPx
}

/** 导航栏内容区高度 px（不含状态栏），与 home-matrix 矩阵 top 计算对齐 */
function navBarPx() {
  const { windowWidth } = readWindowMetrics()
  return 88 * (windowWidth / 750)
}

module.exports = {
  headerOffsetPx,
  navBarPx,
}
