/** 与自定义 navigation-bar 一致：状态栏 + 胶囊对齐的顶栏高度 */
export type NavBarMetrics = {
  totalHeight: number
  statusBarHeight: number
  paddingLeft: number
  paddingRight: number
}

export function getNavBarMetrics(): Promise<NavBarMetrics> {
  return new Promise((resolve, reject) => {
    const rect = wx.getMenuButtonBoundingClientRect()
    wx.getSystemInfo({
      success: (res) => {
        const statusBarHeight = res.statusBarHeight || 0
        const menuGap = Math.max(0, rect.top - statusBarHeight)
        const navContentHeight = menuGap * 2 + rect.height
        resolve({
          totalHeight: statusBarHeight + navContentHeight,
          statusBarHeight,
          paddingLeft: Math.max(0, res.windowWidth - rect.right),
          paddingRight: Math.max(0, res.windowWidth - rect.left),
        })
      },
      fail: reject,
    })
  })
}
