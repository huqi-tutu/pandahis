export function getEnvVersion(): string {
  try {
    return wx.getAccountInfoSync()?.miniProgram?.envVersion || ''
  } catch {
    return ''
  }
}

export function isDevelopEnv(): boolean {
  return getEnvVersion() === 'develop'
}

export function isDevtoolsClient(): boolean {
  try {
    const info = wx.getSystemInfoSync() as WechatMiniprogram.SystemInfo & {
      host?: { env?: string }
    }
    if (info.platform === 'devtools') return true
    if (info.host?.env === 'WeChatDevTools') return true
  } catch {
    // ignore
  }
  return false
}
