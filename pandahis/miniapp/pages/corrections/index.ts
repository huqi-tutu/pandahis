import { hasToken, request } from '../../native-utils/api'
import {
  CorrectionDetail,
  CorrectionListItem,
  correctionStatusLabel,
  fetchCorrectionDetail,
  formatCorrectionTime,
  navigateToCorrectionSource,
  resolveCorrectionSourceNav,
} from '../../native-utils/correction'
import { ROUTES, navigateTo } from '../../native-utils/router'
import { computePageTopPadPx } from '../../native-utils/nav-metrics'

type CorrectionListVm = CorrectionListItem & {
  createdAtLabel: string
  statusLabel: string
}

const EMPTY_DETAIL: CorrectionDetail = {
  id: 0,
  boxId: '',
  boxTitle: '',
  civilizationName: '',
  dynastyName: '',
  sourceType: 'dynasty_canvas',
  sourceRefId: null,
  status: 'pending',
  createdAt: '',
}

Page({
  data: {
    hasToken: false,
    loaded: false,
    items: [] as CorrectionListVm[],
    detailVisible: false,
    detail: EMPTY_DETAIL,
    canViewSource: false,
    pageTopPadPx: 88,
  },
  onLoad() {
    try {
      this.setData({ pageTopPadPx: computePageTopPadPx() })
    } catch {
      this.setData({ pageTopPadPx: 88 })
    }
  },
  onShow() {
    const ok = hasToken()
    this.setData({ hasToken: ok, loaded: false, items: [] })
    if (ok) void this.load()
    else this.setData({ loaded: true })
  },
  goLogin() {
    navigateTo(ROUTES.login)
  },
  mapItem(item: CorrectionListItem): CorrectionListVm {
    return {
      ...item,
      createdAtLabel: formatCorrectionTime(item.createdAt),
      statusLabel: correctionStatusLabel(item.status),
    }
  },
  async load() {
    try {
      const all: CorrectionListItem[] = []
      let page = 1
      const pageSize = 50
      let total = 0
      while (true) {
        const res = await request<{ items: CorrectionListItem[]; total: number }>(
          `/corrections?page=${page}&pageSize=${pageSize}`,
          { auth: true }
        )
        const batch = res.data.items || []
        all.push(...batch)
        total = res.data.total ?? all.length
        if (batch.length < pageSize || all.length >= total) break
        page += 1
      }
      this.setData({
        items: all.map((x) => this.mapItem(x)),
        loaded: true,
      })
    } catch {
      this.setData({ items: [], loaded: true })
    }
  },
  async onItemTap(e: WechatMiniprogram.BaseEvent) {
    const id = Number((e.currentTarget as WechatMiniprogram.IAnyObject).dataset.id)
    if (!id) return
    try {
      wx.showLoading({ title: '加载中', mask: true })
      const detail = await fetchCorrectionDetail(id)
      wx.hideLoading()
      const canViewSource = !('error' in resolveCorrectionSourceNav(detail))
      this.setData({ detail, detailVisible: true, canViewSource })
    } catch (err: unknown) {
      wx.hideLoading()
      const msg = err instanceof Error ? err.message : '加载失败'
      wx.showToast({ title: msg, icon: 'none' })
    }
  },
  closeDetail() {
    this.setData({ detailVisible: false, canViewSource: false })
  },
  onViewSource() {
    const detail = this.data.detail as CorrectionDetail
    if (!detail || !detail.id || !this.data.canViewSource) return
    const ok = navigateToCorrectionSource(detail)
    if (ok) this.setData({ detailVisible: false, canViewSource: false })
  },
})
