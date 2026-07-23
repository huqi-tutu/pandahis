import { hasToken, request } from '../../native-utils/api'
import { encodePathSegment } from '../../native-utils/encode-path-segment'
import { ROUTES, navigateTo } from '../../native-utils/router'
import { computePageTopPadPx } from '../../native-utils/nav-metrics'

type RefItemView = { work: string; chapter: string; excerpt: string; url: string }

/** 与后端约定一致：占位 `{}` / `[]` 视为无原文 */
function isRefMeaningless(ref: unknown): boolean {
  if (ref == null) return true
  if (Array.isArray(ref)) return ref.length === 0
  if (typeof ref === 'object') return Object.keys(ref as object).length === 0
  return false
}

function parseOriginalRef(ref: unknown): {
  title: string
  sourceWork: string
  items: RefItemView[]
  fallback: string
} | null {
  if (isRefMeaningless(ref)) return null
  if (typeof ref === 'string') {
    const t = ref.trim()
    return t ? { title: '母本原文', sourceWork: '', items: [], fallback: t } : null
  }
  if (typeof ref !== 'object' || ref === null) return null
  const o = ref as Record<string, unknown>
  const title = typeof o.title === 'string' && o.title.trim() ? o.title.trim() : '母本原文'
  const sourceWork =
    (typeof o.sourceWork === 'string' ? o.sourceWork.trim() : '') ||
    (typeof o.primarySource === 'string' ? o.primarySource.trim() : '')

  const textField =
    (typeof o.text === 'string' ? o.text.trim() : '') ||
    (typeof o.originalText === 'string' ? o.originalText.trim() : '')
  if (textField) {
    return { title, sourceWork, items: [], fallback: textField }
  }

  if (Array.isArray(o.paragraphs)) {
    const parts: string[] = []
    for (const p of o.paragraphs) {
      if (typeof p === 'string' && p.trim()) parts.push(p.trim())
      else if (p && typeof p === 'object') {
        const t = String((p as Record<string, unknown>).text ?? '').trim()
        if (t) parts.push(t)
      }
    }
    if (parts.length) return { title, sourceWork, items: [], fallback: parts.join('\n') }
  }

  const rawItems = o.items
  const items: RefItemView[] = []
  if (Array.isArray(rawItems)) {
    for (const it of rawItems) {
      if (!it || typeof it !== 'object') continue
      const x = it as Record<string, unknown>
      items.push({
        work: String(x.work ?? '').trim(),
        chapter: String(x.chapter ?? '').trim(),
        excerpt: String(x.excerpt ?? '')
          .trim()
          .replace(/\\r\\n/g, '\n')
          .replace(/\\n/g, '\n'),
        url: String(x.url ?? '').trim(),
      })
    }
  }
  const hasStructured = items.some((i) => i.work || i.chapter || i.excerpt || i.url)
  if (!hasStructured) return null
  return { title, sourceWork, items, fallback: '' }
}

Page({
  data: {
    empty: true,
    refTitle: '',
    refSourceWork: '',
    refItems: [] as RefItemView[],
    refFallback: '',
    pageTopPadPx: 88,
  },
  async onLoad(query: Record<string, string | undefined>) {
    try {
      this.setData({ pageTopPadPx: computePageTopPadPx() })
    } catch {
      this.setData({ pageTopPadPx: 88 })
    }
    const boxId = query.boxId || query.id
    if (!boxId) {
      this.setData({ empty: true, refTitle: '', refItems: [], refFallback: '' })
      return
    }
    try {
      const res = await request<{ originalRef: unknown }>(`/boxes/${encodePathSegment(boxId)}/original-ref`, {
        auth: hasToken(),
      })
      const parsed = parseOriginalRef(res.data.originalRef)
      if (!parsed) {
        this.setData({ empty: true, refTitle: '', refSourceWork: '', refItems: [], refFallback: '' })
        return
      }
      const hasContent = parsed.items.length > 0 || parsed.fallback.length > 0
      this.setData({
        empty: !hasContent,
        refTitle: parsed.title,
        refSourceWork: parsed.sourceWork,
        refItems: parsed.items,
        refFallback: parsed.fallback,
      })
    } catch (e: any) {
      const msg = String(e?.message || '')
      if (msg.includes('INSUFFICIENT_READS') || msg.includes('NEED_MEMBERSHIP_OR_READS')) {
        wx.showModal({
          title: '需要会员或阅读点',
          content: '开通会员可免扣点阅读；也可去会员页邀友助力或查看阅读点。',
          confirmText: '去开通',
          success: (r) => {
            if (r.confirm) wx.switchTab({ url: ROUTES.membership })
          },
        })
      } else if (msg === 'UNAUTHORIZED' || msg.includes('login required')) {
        wx.showModal({
          title: '需要登录',
          content: '登录后可开通会员或使用阅读点查看原文对照。',
          confirmText: '去登录',
          success: (r) => {
            if (r.confirm) navigateTo(ROUTES.login)
          },
        })
      } else {
        wx.showToast({ title: e?.message || '加载失败', icon: 'none' })
      }
      this.setData({ empty: true, refTitle: '', refSourceWork: '', refItems: [], refFallback: '' })
    }
  },
  copyLink(e: WechatMiniprogram.BaseEvent) {
    const url = (e.currentTarget as any).dataset.url as string
    if (!url) return
    wx.setClipboardData({
      data: url,
      success: () => wx.showToast({ title: '链接已复制', icon: 'none' }),
    })
  },
})
