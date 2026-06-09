import { request } from './api'

export type InviteBindResult = { bound: boolean; message: string }

export async function bindInviteCode(inviteCode: string): Promise<InviteBindResult> {
  const res = await request<InviteBindResult>('/invite/bind', {
    method: 'POST',
    auth: true,
    data: { inviteCode: inviteCode.trim().toUpperCase() },
  })
  return res.data
}
