import { request, setToken, hasToken, hasUserLoggedOut } from './api'
import { clearPendingInviteCode, peekPendingInviteCode } from './invite-storage'
import { ROUTES } from './router'

export type WxLoginData = {
  accessToken: string
  expiresIn: number
  newUser?: boolean
  inviteRecorded?: boolean
}

export function wxLoginCode(): Promise<string> {
  return new Promise((resolve, reject) => {
    wx.login({
      success: (res) => {
        if (res.code) resolve(res.code)
        else reject(new Error('未取得 code'))
      },
      fail: () => reject(new Error('wx.login 失败')),
    })
  })
}

/** 调用后端 /auth/wx-login，写入 accessToken */
export async function loginWithWxCode(options?: {
  inviteCode?: string
}): Promise<WxLoginData> {
  const code = await wxLoginCode()
  const inviteCode = (options?.inviteCode ?? peekPendingInviteCode()).trim()
  const res = await request<WxLoginData>('/auth/wx-login', {
    method: 'POST',
    data: inviteCode ? { code, inviteCode } : { code },
  })
  const accessToken = res.data?.accessToken
  if (!accessToken || typeof accessToken !== 'string') {
    throw new Error('登录响应异常，未获取到令牌')
  }
  setToken(accessToken)
  if (inviteCode) clearPendingInviteCode()
  return res.data
}

export type LeaveAfterLoginOptions = {
  /** 登录后强制切到指定 Tab（如邀请页） */
  switchTab?: string
}

/** 登录成功后离开登录页：可指定 Tab；否则优先返回上一页，失败则切到「我的」 */
export function leaveAfterLogin(delayMs = 400, options?: LeaveAfterLoginOptions) {
  const go = () => {
    if (options?.switchTab) {
      wx.switchTab({
        url: options.switchTab,
        fail: () => wx.switchTab({ url: ROUTES.mine }),
      })
      return
    }
    const pages = getCurrentPages()
    const prev = pages.length > 1 ? pages[pages.length - 2] : null
    const notifyPrev = () => {
      const r = (prev as WechatMiniprogram.Page.Instance<
        Record<string, unknown>,
        WechatMiniprogram.IAnyObject
      > & { refresh?: () => void })?.refresh
      if (typeof r === 'function') void r.call(prev)
    }
    if (pages.length > 1) {
      wx.navigateBack({
        success: notifyPrev,
        fail: () => wx.switchTab({ url: ROUTES.mine }),
      })
      return
    }
    wx.switchTab({ url: ROUTES.mine })
  }
  if (delayMs > 0) {
    setTimeout(go, delayMs)
  } else {
    go()
  }
}

/** 启动时静默登录：已有 token 则跳过；用户主动退出后不再自动登录 */
export async function trySilentWxLogin(): Promise<boolean> {
  if (hasToken()) return true
  if (hasUserLoggedOut()) return false
  try {
    await loginWithWxCode()
    return true
  } catch {
    return false
  }
}

export function loginSuccessToast(data: WxLoginData) {
  if (data.inviteRecorded) {
    wx.showToast({ title: '登录成功，邀请已生效', icon: 'success' })
    return
  }
  if (data.newUser) {
    wx.showToast({ title: '注册成功', icon: 'success' })
    return
  }
  wx.showToast({ title: '登录成功', icon: 'success' })
}
