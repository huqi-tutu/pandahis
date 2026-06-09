const protoPage = require('../../behaviors/proto-page.js')

Page({
  behaviors: [protoPage],

  data: {
    selectedPlan:  'invite',
    selectedLabel: '邀友获取 · 季卡 · ¥0',
    buyBarH: 140,   // px：底部 bar 占位高度
  },

  onPlanTap(e) {
    const { plan, label } = e.currentTarget.dataset
    this.setData({ selectedPlan: plan, selectedLabel: label })
  },

  onConfirm() {
    const plan = this.data.selectedPlan
    if (plan === 'invite') {
      // 跳转邀友页
      wx.navigateTo({ url: '/pages/vip-invite/vip-invite' })
    } else {
      wx.showToast({ title: '功能开发中', icon: 'none' })
    }
  },
})
