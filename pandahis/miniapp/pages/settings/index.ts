import {
  clearToken,
  getBaseUrl,
  hasToken,
  probeApiConnectivity,
  useLocalDevApi,
  useProductionApi,
} from '../../native-utils/api'
import { formatApiRequestError } from '../../native-utils/load-error-message'
import { computePageTopPadPx } from '../../native-utils/nav-metrics'
import { getEnvVersion, isDevtoolsClient } from '../../native-utils/runtime-env'
import { ROUTES, SUPPORT_EMAIL, navigateTo } from '../../native-utils/router'
import { APP_DISPLAY_NAME } from '../../native-utils/brand-assets'

const APP_VERSION = '1.0.0'

Page({
  data: {
    loggedIn: false,
    apiBase: '',
    pageTopPadPx: 88,
    appVersion: APP_VERSION,
    aboutNavTitle: `关于${APP_DISPLAY_NAME}`,
  },
  onLoad() {
    try {
      this.setData({ pageTopPadPx: computePageTopPadPx() })
    } catch {
      this.setData({ pageTopPadPx: 88 })
    }
  },
  onShow() {
    this.setData({
      loggedIn: hasToken(),
      apiBase: getBaseUrl(),
    })
  },
  goContact() {
    wx.showModal({
      title: '联系我们',
      content: `如有问题或建议，请发送邮件至：\n${SUPPORT_EMAIL}`,
      confirmText: '复制邮箱',
      cancelText: '关闭',
      success: (r) => {
        if (!r.confirm) return
        wx.setClipboardData({
          data: SUPPORT_EMAIL,
          success: () => wx.showToast({ title: '已复制邮箱', icon: 'success' }),
        })
      },
    })
  },
  goFeedback() {
    if (!hasToken()) {
      wx.showModal({
        title: '需要登录',
        content: '登录后可提交帮助与反馈。',
        confirmText: '去登录',
        success: (r) => {
          if (r.confirm) navigateTo(ROUTES.login)
        },
      })
      return
    }
    navigateTo(ROUTES.feedback)
  },
  goAbout() {
    navigateTo(ROUTES.about)
  },
  async testApiConnection() {
    wx.showLoading({ title: '检测中', mask: true })
    const result = await probeApiConnectivity()
    wx.hideLoading()
    if (result.ok) {
      wx.showModal({
        title: '连接正常',
        content: `基础、登录、朝代概要、朝代画布接口均正常。\n\n当前接口：\n${getBaseUrl()}${hasToken() ? '\n\n已保存登录令牌' : '\n\n未登录（请在登录页授权）'}`,
        showCancel: false,
      })
      return
    }
    const hint = formatApiRequestError(result.error)
    const stageText = result.stage === 'swim-matrix'
      ? '（朝代画布接口失败，详情页无法展示）'
      : result.stage === 'unit'
        ? '（朝代概要接口失败）'
        : result.stage === 'auth'
          ? '（微信登录接口不可达，登录与用户资料会失败）'
          : '（基础健康检查失败）'
    wx.showModal({
      title: '连接失败',
      content: `${hint}${stageText}\n\n当前配置：\n${getBaseUrl()}`,
      confirmText: '切生产接口',
      cancelText: '关闭',
      success: (r) => {
        if (!r.confirm) return
        useProductionApi()
        this.setData({ apiBase: getBaseUrl() })
        wx.showToast({ title: '已切换生产接口', icon: 'success' })
      },
    })
  },
  onApiBaseTap() {
    if (getEnvVersion() !== 'develop') {
      void this.testApiConnection()
      return
    }
    const items = ['使用生产接口（推荐，手机预览用这个）', '检测接口连接']
    const localDevIndex = isDevtoolsClient() ? items.push('使用本机接口 localhost:8080') - 1 : -1
    wx.showActionSheet({
      itemList: items,
      success: (res) => {
        if (res.tapIndex === 0) {
          useProductionApi()
          wx.showToast({ title: '已切换生产接口', icon: 'success' })
          this.setData({ apiBase: getBaseUrl() })
        } else if (res.tapIndex === 1) {
          void this.testApiConnection()
        } else if (res.tapIndex === localDevIndex) {
          useLocalDevApi()
          wx.showToast({ title: '已切换本机接口', icon: 'success' })
          this.setData({ apiBase: getBaseUrl() })
        }
      },
    })
  },
  clearCache() {
    wx.showModal({
      title: '清除缓存',
      content: '将清除本地图片缓存等数据，不会删除登录状态与邀请码。',
      success: (r) => {
        if (!r.confirm) return
        try {
          const info = wx.getStorageInfoSync()
          const keep = new Set(['accessToken', 'apiBaseUrl', 'pendingInviteCode', 'userLoggedOut'])
          for (const key of info.keys) {
            if (!keep.has(key)) wx.removeStorageSync(key)
          }
        } catch {
          // ignore
        }
        wx.showToast({ title: '已清除', icon: 'success' })
      },
    })
  },
  logout() {
    wx.showModal({
      title: '退出登录',
      content: '确定退出当前账号？',
      confirmText: '退出',
      success: (r) => {
        if (!r.confirm) return
        clearToken()
        this.setData({ loggedIn: false })
        wx.showToast({ title: '已退出', icon: 'success' })
        setTimeout(() => navigateTo(ROUTES.login), 400)
      },
    })
  },
})
