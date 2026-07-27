/** 与自定义 navigation-bar 一致：状态栏 + 胶囊对齐的顶栏高度 */
export type NavBarMetrics = {
  totalHeight: number
  statusBarHeight: number
  paddingLeft: number
  paddingRight: number
}

/** 导航栏底边到首屏内容的标准间距；0 = 内容紧贴导航底边 */
export const PAGE_CONTENT_GAP_RPX = 0

/** 仅导航占位：状态栏 + 88rpx 导航条（固定定位元素用） */
export function computeHeaderPadPx(sys?: WechatMiniprogram.SystemInfo): number {
  const info = sys ?? wx.getSystemInfoSync()
  const navPx = (88 * info.windowWidth) / 750
  return (info.statusBarHeight || 20) + navPx
}

/** 滚动内容区 padding-top：导航占位 + 标准呼吸间距 */
export function computePageTopPadPx(sys?: WechatMiniprogram.SystemInfo): number {
  const info = sys ?? wx.getSystemInfoSync()
  const gapPx = (PAGE_CONTENT_GAP_RPX * info.windowWidth) / 750
  return computeHeaderPadPx(info) + gapPx
}

/** 全屏 scroll-view 高度（Tab 页内容铺至窗口底） */
export function computePageHeightPx(sys?: WechatMiniprogram.SystemInfo): number {
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
