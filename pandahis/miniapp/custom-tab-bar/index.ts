type TabItem = { pagePath: string }

Component({
  data: {
    selected: 0,
    list: [
      { pagePath: '/pages/home/index' },
      { pagePath: '/pages/search/index' },
      { pagePath: '/pages/membership/index' },
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
      wx.switchTab({ url: item.pagePath })
    },
  },
})
