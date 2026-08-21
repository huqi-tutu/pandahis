/** 与自定义 navigation-bar 一致：状态栏 + 胶囊对齐的顶栏高度 */
export type NavBarMetrics = {
  totalHeight: number
  statusBarHeight: number
  paddingLeft: number
  paddingRight: number
}

/** 导航栏底边到首屏内容的标准间距；0 = 内容紧贴导航底边 */
export const PAGE_CONTENT_GAP_RPX = 0

type SysLike = {
  windowWidth?: number
  windowHeight?: number
  statusBarHeight?: number
}

/** 与 navigation-bar 组件同一套胶囊算法（避免 88rpx 估算偏矮导致内容顶进导航） */
export function computeNavTotalHeightPx(sys?: SysLike): number {
  const info = sys ?? wx.getSystemInfoSync()
  const statusBarHeight = info.statusBarHeight || 20
  try {
    const rect = wx.getMenuButtonBoundingClientRect()
    if (rect && rect.height > 0 && rect.top >= 0) {
      const menuGap = Math.max(0, rect.top - statusBarHeight)
      return statusBarHeight + menuGap * 2 + rect.height
    }
  } catch {
    // fall through
  }
  const navPx = (88 * (info.windowWidth || 375)) / 750
  return statusBarHeight + navPx
}

/** 仅导航占位：优先胶囊实测高度；失败时回退状态栏 + 88rpx */
export function computeHeaderPadPx(sys?: SysLike): number {
  return computeNavTotalHeightPx(sys)
}

/** 滚动内容区 padding-top：导航占位 + 标准呼吸间距 */
export function computePageTopPadPx(sys?: SysLike): number {
  const info = sys ?? wx.getSystemInfoSync()
  const gapPx = (PAGE_CONTENT_GAP_RPX * (info.windowWidth || 375)) / 750
  return computeHeaderPadPx(info) + gapPx
}

/** 全屏 scroll-view 高度（Tab 页内容铺至窗口底） */
export function computePageHeightPx(sys?: SysLike): number {
  const info = sys ?? wx.getSystemInfoSync()
  return info.windowHeight || 667
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
