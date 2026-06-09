import { stashInviteFromLaunchOptions } from './native-utils/invite-storage'
import { trySilentWxLogin } from './native-utils/wx-auth'

const NOTO_SERIF_WOFF2 =
  'https://cdn.jsdelivr.net/npm/@fontsource/noto-serif-sc@5.0.18/files/noto-serif-sc-chinese-simplified-700-normal.woff2'

function loadTitleFont() {
  wx.loadFontFace({
    family: 'Noto Serif SC',
    source: `url("${NOTO_SERIF_WOFF2}")`,
    global: true,
    fail: () => {
      /* fallback: Songti SC via design-tokens */
    },
  })
}

App<IAppOption>({
  globalData: {},
  onLaunch(options: WechatMiniprogram.App.LaunchShowOption) {
    loadTitleFont()
    stashInviteFromLaunchOptions(options)
    void trySilentWxLogin()
  },
  onShow(options: WechatMiniprogram.App.LaunchShowOption) {
    stashInviteFromLaunchOptions(options)
  },
})
