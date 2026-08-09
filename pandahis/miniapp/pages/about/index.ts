import { APP_DISPLAY_NAME, BRAND_LOGO_URL } from '../../native-utils/brand-assets'
import { computePageTopPadPx } from '../../native-utils/nav-metrics'

Page({
  data: {
    brandLogoUrl: BRAND_LOGO_URL,
    aboutNavTitle: `关于${APP_DISPLAY_NAME}`,
    introLead: `${APP_DISPLAY_NAME}以时空坐标组织史料，帮助你在朝代、人物与事件之间建立可浏览、可深读的知识网络。`,
    version: '0.1.0',
    pageTopPadPx: 88,
  },
  onLoad() {
    try {
      this.setData({ pageTopPadPx: computePageTopPadPx() })
    } catch {
      this.setData({ pageTopPadPx: 88 })
    }
  },
})
