import { computePageTopPadPx } from '../../native-utils/nav-metrics'

Page({
  data: {
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
