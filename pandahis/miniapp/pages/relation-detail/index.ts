import { request } from '../../native-utils/api'
import { encodePathSegment } from '../../native-utils/encode-path-segment'
import { ROUTES, navigateTo } from '../../native-utils/router'

Page({
  data: {
    name: '',
    info: null as {
      name: string
      category: string
      role: string
      level: string
      lineage: string
      summary: string
      targetBoxId?: string
    } | null,
    color: '#9B3E38',
    headerPadPx: 88,
  },
  async onLoad(query: Record<string, string | undefined>) {
    try {
      const sys = wx.getSystemInfoSync()
      const navPx = 88 * (sys.windowWidth / 750)
      this.setData({ headerPadPx: (sys.statusBarHeight || 20) + navPx })
    } catch {
      this.setData({ headerPadPx: 88 })
    }
    const boxId = query.boxId
    const nodeKey = query.nodeKey || query.name
    if (!boxId || !nodeKey) return
    const name = decodeURIComponent(nodeKey)
    this.setData({ name })
    try {
      const enc = encodePathSegment(boxId)
      const key = encodeURIComponent(nodeKey)
      const res = await request<any>(`/boxes/${enc}/graph/nodes/${key}`)
      const d = res.data || {}
      this.setData({
        info: {
          name: d.name || name,
          category: d.category || '',
          role: d.role || '',
          level: d.level || '',
          lineage: d.lineage || '',
          summary: d.summary || '',
          targetBoxId: d.targetBoxId,
        },
      })
    } catch {
      this.setData({
        info: {
          name,
          category: '关系',
          role: '',
          level: '',
          lineage: '',
          summary: `暂无 ${name} 的详细关系数据。`,
        },
      })
    }
  },
  goTargetBox() {
    const id = this.data.info?.targetBoxId
    if (!id) return
    navigateTo(ROUTES.boxDetail, { boxId: id })
  },
})
