import { hasToken } from '../native-utils/api'
import { ROUTES, navigateTo } from '../native-utils/router'

type TabItem = { pagePath: string }

const INVITE_TAB_INDEX = 2

Component({
  data: {
    selected: 0,
    list: [
      { pagePath: '/pages/home/index' },
      { pagePath: '/pages/search/index' },
      { pagePath: '/pages/invite/index' },
      { pagePath: '/pages/my/index' },
    ] as TabItem[],
  },
  methods: {
    setSelected(index: number) {
      this.setData({ selected: index })
    },
    onTap(e: WechatMiniprogram.BaseEvent) {
      const indexStr = (e.currentTarget as unknown as { dataset: { index: string } }).dataset.index
      const index = Number(indexStr)
      const item = this.data.list[index]
      if (!item) return
      if (index === INVITE_TAB_INDEX && !hasToken()) {
        navigateTo(ROUTES.login, { from: 'invite' })
        return
      }
      wx.switchTab({ url: item.pagePath })
    },
  },
})
