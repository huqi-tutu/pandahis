/**
 * @antv/f6-wx MIT — 本地 RadialLayout，无云端绘图 API
 */
import { toF6GraphData, type ApiGraphPayload } from '../../utils/f6-graph-adapter'
import { getF6Runtime, readCanvasMetrics, type F6GraphInstance } from '../../utils/f6-runtime'

Component({
  properties: {
    graph: {
      type: Object,
      value: {} as ApiGraphPayload,
    },
    viewportHeight: {
      type: Number,
      value: 400,
    },
  },

  data: {
    canvasReady: false,
    canvasWidth: 375,
    layoutHeight: 400,
    pixelRatio: 2,
    scaleLabel: '100%',
    hint: '',
  },

  observers: {
    graph(g: ApiGraphPayload) {
      if (!g?.nodes?.length) {
        this.publishHint('暂无关系数据')
        return
      }
      this.publishHint('')
      if ((this as any)._graphReady) this.rebuildGraph()
      else this.tryInitGraph()
    },
    viewportHeight(h: number) {
      if (h > 0) this.setData({ layoutHeight: h })
    },
  },

  lifetimes: {
    attached() {
      const { windowWidth, pixelRatio } = readCanvasMetrics()
      const layoutHeight = this.properties.viewportHeight || 400
      this.setData({
        canvasWidth: windowWidth,
        layoutHeight,
        pixelRatio,
        canvasReady: true,
      })
      ;(this as any)._expandedKeys = new Set<string>()
    },
    detached() {
      this.destroyGraph()
      ;(this as any)._canvasCtx = null
    },
  },

  methods: {
    publishHint(message: string) {
      const hint = String(message || '').trim()
      if (hint !== this.data.hint) {
        this.setData({ hint })
      }
      this.triggerEvent('renderHint', { hint })
    },

    formatScale(zoom: number) {
      return `${Math.round(zoom * 100)}%`
    },

    destroyGraph() {
      const g = (this as any)._graph as F6GraphInstance | null
      if (g) {
        try {
          g.destroy()
        } catch {
          /* ignore */
        }
      }
      ;(this as any)._graph = null
      ;(this as any)._graphReady = false
    },

    buildLayoutData() {
      const payload = (this.properties.graph || {}) as ApiGraphPayload
      const expandedKeys = (this as any)._expandedKeys as Set<string>
      const canvas = (this as any)._canvasCtx as { width?: number; height?: number } | null
      const ratio = this.data.pixelRatio || 1
      return toF6GraphData(payload, expandedKeys, {
        width: canvas?.width || this.data.canvasWidth * ratio,
        height: canvas?.height || this.data.layoutHeight * ratio,
      })
    },

    onCanvasInit(e: WechatMiniprogram.CustomEvent) {
      const detail = e.detail || {}
      const ctx = detail.ctx
      const renderer = detail.renderer || 'mini-native'
      const rect = detail.rect || {}
      const ratio = this.data.pixelRatio || 1
      // f6-canvas 缓冲区 = 逻辑尺寸 × pixelRatio，F6 必须用 rect 物理尺寸
      const width = rect.width || this.data.canvasWidth * ratio
      const height = rect.height || this.data.layoutHeight * ratio

      if (!ctx) {
        this.publishHint('画布初始化失败')
        console.warn('[f6-relation-graph] missing canvas ctx')
        return
      }

      ;(this as any)._canvasCtx = { ctx, renderer, width, height }
      console.info('[f6-relation-graph] canvas init', width, height, 'ratio', ratio)
      this.tryInitGraph()
    },

    getCanvasCenter() {
      const canvas = (this as any)._canvasCtx as { width?: number; height?: number } | null
      const ratio = this.data.pixelRatio || 1
      const width = canvas?.width || this.data.canvasWidth * ratio
      const height = canvas?.height || this.data.layoutHeight * ratio
      return { x: width / 2, y: height / 2 }
    },

    normalizeViewport(graph: F6GraphInstance) {
      try {
        graph.fitView(32)
        const z = graph.getZoom()
        if (z < 0.22) graph.fitView(40)
        this.setData({ scaleLabel: this.formatScale(graph.getZoom()) })
      } catch {
        /* ignore */
      }
    },

    tryInitGraph() {
      const canvas = (this as any)._canvasCtx as {
        ctx: unknown
        renderer: string
        width: number
        height: number
      } | null
      if (!canvas?.ctx) return

      const payload = (this.properties.graph || {}) as ApiGraphPayload
      if (!payload.nodes?.length) return

      const { nodes, edges, centerId } = this.buildLayoutData()
      if (!nodes.length) {
        this.publishHint('暂无关系数据')
        return
      }

      let F6
      try {
        F6 = getF6Runtime()
      } catch (err: any) {
        const msg = err?.message || '关系图谱加载失败'
        this.publishHint(msg)
        console.warn('[f6-relation-graph] getF6Runtime failed', msg)
        return
      }

      this.destroyGraph()

      const { ctx, renderer, width, height } = canvas
      try {
        const graph = new F6.Graph({
          context: ctx,
          renderer,
          width,
          height,
          fitView: false,
          modes: {
            default: ['drag-canvas', 'zoom-canvas'],
          },
          defaultNode: {
            type: 'circle',
            size: 48,
            labelCfg: {
              position: 'center',
              style: { fontSize: 11, fill: '#343A40' },
            },
          },
          defaultEdge: {
            type: 'quadratic',
            style: {
              lineWidth: 1.5,
              lineDash: [4, 4],
              endArrow: false,
            },
            labelCfg: {
              autoRotate: true,
              refY: 0,
              style: {
                fontSize: 9,
                fill: '#FAF8F5',
                background: {
                  fill: 'rgba(108, 117, 125, 0.88)',
                  padding: [2, 5, 2, 5],
                  radius: 4,
                },
              },
            },
          },
        })

        graph.data({ nodes, edges })
        graph.render()
        this.normalizeViewport(graph)

        graph.on('node:tap', (evt: any) => {
          const model = evt?.item?.getModel?.() || evt?.item?.get?.('model')
          if (!model?.id) return
          const expandedKeys = (this as any)._expandedKeys as Set<string>
          if (model.hasHiddenChildren) {
            if (expandedKeys.has(model.id)) expandedKeys.delete(model.id)
            else expandedKeys.add(model.id)
            this.rebuildGraph()
            return
          }
          this.triggerEvent('nodeTap', {
            key: model.id,
            targetBoxId: model.targetBoxId,
            nodeType: model.relationType,
          })
        })

        graph.on('viewportchange', () => {
          try {
            const z = graph.getZoom()
            const label = this.formatScale(z)
            if (label !== this.data.scaleLabel) {
              this.setData({ scaleLabel: label })
              this.triggerEvent('zoomChange', { scale: z })
            }
          } catch {
            /* ignore */
          }
        })

        ;(this as any)._graph = graph
        ;(this as any)._graphReady = true
        this.publishHint('')
        console.info('[f6-relation-graph] render ok nodes=', nodes.length)
      } catch (err: any) {
        const msg = err?.message || '关系图谱渲染失败'
        this.publishHint(msg)
        console.warn('[f6-relation-graph] render failed', err)
      }
    },

    rebuildGraph() {
      const graph = (this as any)._graph as F6GraphInstance | null
      if (!graph) return
      const { nodes, edges } = this.buildLayoutData()
      if (!nodes.length) return
      graph.changeData({ nodes, edges })
      graph.render()
      this.normalizeViewport(graph)
    },

    onCanvasTouch(e: WechatMiniprogram.CustomEvent) {
      const graph = (this as any)._graph as F6GraphInstance | null
      graph?.emitEvent(e.detail)
    },

    onZoomIn() {
      const graph = (this as any)._graph as F6GraphInstance | null
      if (!graph) return
      const center = this.getCanvasCenter()
      graph.zoom(1.18, center)
      this.setData({ scaleLabel: this.formatScale(graph.getZoom()) })
    },

    onZoomOut() {
      const graph = (this as any)._graph as F6GraphInstance | null
      if (!graph) return
      const center = this.getCanvasCenter()
      graph.zoom(1 / 1.18, center)
      this.setData({ scaleLabel: this.formatScale(graph.getZoom()) })
    },

    zoomIn() {
      this.onZoomIn()
    },

    zoomOut() {
      this.onZoomOut()
    },

    resetZoom() {
      const graph = (this as any)._graph as F6GraphInstance | null
      if (!graph) return
      graph.fitView(24)
      this.setData({ scaleLabel: this.formatScale(graph.getZoom()) })
    },

    getZoomScale() {
      const graph = (this as any)._graph as F6GraphInstance | null
      return graph?.getZoom?.() || 1
    },

    paintCached() {
      /* F6 自绘，保留接口兼容 box-detail 缩放栏 */
    },
  },
})
