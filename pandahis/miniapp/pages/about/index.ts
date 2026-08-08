import { BRAND_LOGO_URL } from '../../native-utils/brand-assets'
import { computePageTopPadPx } from '../../native-utils/nav-metrics'

Page({
  data: {
    brandLogoUrl: BRAND_LOGO_URL,
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
