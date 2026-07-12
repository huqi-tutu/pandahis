/** 小程序 App 全局选项（app.ts 使用） */
interface IAppOption {
  globalData: Record<string, unknown>
}

declare namespace WechatMiniprogram {
  interface SystemInfo {
    safeAreaInsets?: {
      bottom?: number
      top?: number
      left?: number
      right?: number
    }
  }
}
