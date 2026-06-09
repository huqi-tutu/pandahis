import { hasToken, request } from '../../native-utils/api'
import { encodePathSegment } from '../../native-utils/encode-path-segment'
import { ROUTES, navigateTo } from '../../native-utils/router'

type RefItemView = { work: string; chapter: string; excerpt: string; url: string }

/** 与后端约定一致：占位 `{}` / `[]` 视为无原文 */
function isRefMeaningless(ref: unknown): boolean {
  if (ref == null) return true
  if (Array.isArray(ref)) return ref.length === 0
  if (typeof ref === 'object') return Object.keys(ref as object).length === 0
  return false
}

function parseOriginalRef(ref: unknown): { title: string; items: RefItemView[]; fallback: string } | null {
  if (isRefMeaningless(ref)) return null
  if (typeof ref === 'string') {
    const t = ref.trim()
    return t ? { title: '原文', items: [], fallback: t } : null
  }
  if (typeof ref !== 'object' || ref === null) return null
  const o = ref as Record<string, unknown>
  const title = typeof o.title === 'string' && o.title.trim() ? o.title.trim() : '史料原文'
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
  if (!hasStructured) {
    try {
      const fallback = JSON.stringify(ref, null, 2)
      return { title, items: [], fallback }
    } catch {
      return { title, items: [], fallback: String(ref) }
    }
  }
  return { title, items, fallback: '' }
}

Page({
  data: {
    empty: true,
    refTitle: '',
    refItems: [] as RefItemView[],
    refFallback: '',
  },
  async onLoad(query: Record<string, string | undefined>) {
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
        this.setData({ empty: true, refTitle: '', refItems: [], refFallback: '' })
        return
      }
      const hasContent = parsed.items.length > 0 || parsed.fallback.length > 0
      this.setData({
        empty: !hasContent,
        refTitle: parsed.title,
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
      this.setData({ empty: true, refTitle: '', refItems: [], refFallback: '' })
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
