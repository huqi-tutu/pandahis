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
    const device = wx.getDeviceInfo?.()
    if (device?.platform === 'devtools') return true

    const appBase = wx.getAppBaseInfo?.()
    const hostEnv = (appBase as { host?: { env?: string } } | undefined)?.host?.env
    if (hostEnv === 'WeChatDevTools') return true
  } catch {
    // ignore
  }
  return false
}
