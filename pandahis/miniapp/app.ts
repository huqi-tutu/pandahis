import { stashInviteFromLaunchOptions } from './native-utils/invite-storage'
import { clearDevelopApiBaseUrl } from './native-utils/api'
import { getEnvVersion, isDevtoolsClient } from './native-utils/runtime-env'
import { trySilentWxLogin } from './native-utils/wx-auth'

/** 真机预览清除无效的本机/局域网 API 缓存，避免误连不可达地址 */
function migrateApiBaseUrlForClient() {
  try {
    if (getEnvVersion() !== 'develop') return
    if (isDevtoolsClient()) return
    const stored = String(wx.getStorageSync('apiBaseUrl') || '').trim()
    if (!stored) return
    if (/^http:\/\//i.test(stored)) {
      clearDevelopApiBaseUrl()
    }
  } catch {
    // ignore
  }
}

/** 加载 Noto Serif SC，解决 Android 无内置宋体导致标题字体不一致 */
function loadAppFonts() {
  try {
    const platform = wx.getDeviceInfo?.().platform || wx.getSystemInfoSync().platform
    // 开发者工具无法稳定加载外链字体；真机需在后台配置 downloadFile 合法域名
    if (platform === 'devtools') return
  } catch {
    return
  }
  wx.loadFontFace({
    family: 'Noto Serif SC',
    source:
      'url("https://cdn.jsdelivr.net/npm/@fontsource/noto-serif-sc@5.1.1/files/noto-serif-sc-chinese-simplified-700-normal.woff2")',
    weight: '700',
    global: true,
    fail(err) {
      console.warn('[字体] Noto Serif SC 700 加载失败', err)
    },
  })
  wx.loadFontFace({
    family: 'Noto Serif SC',
    source:
      'url("https://cdn.jsdelivr.net/npm/@fontsource/noto-serif-sc@5.1.1/files/noto-serif-sc-chinese-simplified-400-normal.woff2")',
    weight: '400',
    global: true,
    fail(err) {
      console.warn('[字体] Noto Serif SC 400 加载失败', err)
    },
  })
}

App<IAppOption>({
  globalData: {},
  onLaunch(options: WechatMiniprogram.App.LaunchShowOption) {
    migrateApiBaseUrlForClient()
    loadAppFonts()
    stashInviteFromLaunchOptions(options)
    void trySilentWxLogin()
  },
  onShow(options: WechatMiniprogram.App.LaunchShowOption) {
    stashInviteFromLaunchOptions(options)
  },
  onHide() {
    try {
      const pages = getCurrentPages()
      for (let i = pages.length - 1; i >= 0; i--) {
        const page = pages[i] as WechatMiniprogram.Page.Instance<
          WechatMiniprogram.IAnyObject,
          WechatMiniprogram.IAnyObject
        > & {
          _persistHomeViewportState?: (syncRemote: boolean) => void
          _syncScrollTopFromDom?: (done?: () => void) => void
          route?: string
        }
        const route = page?.route ? String(page.route) : ''
        if (!route.endsWith('home/index')) continue
        if (page._syncScrollTopFromDom) {
          page._syncScrollTopFromDom(() => page._persistHomeViewportState?.(true))
        } else {
          page._persistHomeViewportState?.(true)
        }
        break
      }
    } catch {
      // ignore
    }
  },
})
