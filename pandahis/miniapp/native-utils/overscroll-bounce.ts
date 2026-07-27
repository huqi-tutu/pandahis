/** 判断内容是否超出 scroll-view 可视区（容差 2px） */
export function measureScrollOverflow(
  page: WechatMiniprogram.Page.TrivialInstance,
  scrollSelector: string,
  contentSelector: string,
): Promise<boolean> {
  return new Promise((resolve) => {
    wx.createSelectorQuery()
      .in(page)
      .select(scrollSelector)
      .boundingClientRect()
      .select(contentSelector)
      .boundingClientRect()
      .exec((res) => {
        const viewport = res[0] as WechatMiniprogram.BoundingClientRectCallbackResult | null
        const content = res[1] as WechatMiniprogram.BoundingClientRectCallbackResult | null
        if (!viewport?.height || !content?.height) {
          resolve(false)
          return
        }
        resolve(content.height > viewport.height + 2)
      })
  })
}
