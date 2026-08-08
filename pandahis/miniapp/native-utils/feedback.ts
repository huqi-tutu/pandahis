import { request, uploadFile } from './api'
import { compressImageUnder1MB } from './compress-image'

export const FEEDBACK_TYPES = [
  { value: 'feature', label: '功能反馈' },
  { value: 'content', label: '内容反馈' },
  { value: 'partnership', label: '交流合作' },
  { value: 'other', label: '其他' },
] as const

export type FeedbackType = (typeof FEEDBACK_TYPES)[number]['value']

export const FEEDBACK_CONTENT_MAX = 1000
export const FEEDBACK_IMAGE_MAX = 3
export const FEEDBACK_DAILY_LIMIT = 5

export type FeedbackSubmitResult = {
  id: number
  feedbackType: string
  content: string
  imageUrls: string[]
  status: string
  createdAt: string
}

export async function uploadFeedbackImage(localPath: string): Promise<string> {
  const compressed = await compressImageUnder1MB(localPath)
  const res = await uploadFile<{ url: string }>('/feedback/images', compressed, { name: 'file' })
  const url = res.data?.url
  if (!url) throw new Error('上传失败')
  return url
}

export async function submitFeedback(payload: {
  feedbackType: FeedbackType
  content: string
  imageUrls: string[]
}): Promise<FeedbackSubmitResult> {
  const res = await request<FeedbackSubmitResult>('/feedback', {
    method: 'POST',
    auth: true,
    data: {
      feedbackType: payload.feedbackType,
      content: payload.content,
      imageUrls: payload.imageUrls,
    },
  })
  return res.data
}
