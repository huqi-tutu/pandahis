const protoPage = require('../../behaviors/proto-page.js')
const { getRelations, getCritiques, getRelics } = require('../../data/data-loader.js')
const { buildRelationTree, layoutRadialTree, buildCapsule } = require('../../data/relation-tree.js')
const { headerOffsetPx } = require('../../utils/layout.js')

/** Tab 栏 top / 内容区 top（与 proto-nav 高度对齐，避免首屏 tabTop=0 被导航遮住） */
function boxLayoutMetrics() {
  try {
    const sys = wx.getSystemInfoSync()
    const tabTop = headerOffsetPx()
    const tabBarPx = 72 * (sys.windowWidth / 750)
    return { tabTop, bodyTop: tabTop + tabBarPx }
  } catch (e) {
    return { tabTop: 88, bodyTop: 124 }
  }
}

/** 统一连线线宽（与黄帝延伸分支一致） */
const EDGE_LINE_WIDTH = 1.5
const EDGE_LABEL_COLOR = '#B0A89E'

/** V5 原型 5 号页 — 关系图谱主题 */
const GRAPH_THEME = {
  root: {
    fill: 'rgba(155, 62, 56, 0.22)',
    stroke: 'rgba(155, 62, 56, 0.68)',
  },
  categoryLink: 'rgba(47, 41, 38, 0.28)',
  '家庭': {
    nodeFill: 'rgba(91, 138, 114, 0.12)',
    nodeStroke: 'rgba(91, 138, 114, 0.62)',
    edgeStroke: 'rgba(91, 138, 114, 0.55)',
    catFill: 'rgba(91, 138, 114, 0.1)',
    catStroke: 'rgba(91, 138, 114, 0.65)',
    labelFill: 'rgba(71, 108, 88, 0.88)',
  },
  '师从': {
    nodeFill: 'rgba(91, 127, 168, 0.12)',
    nodeStroke: 'rgba(91, 127, 168, 0.58)',
    edgeStroke: 'rgba(91, 127, 168, 0.52)',
    catFill: 'rgba(91, 127, 168, 0.1)',
    catStroke: 'rgba(91, 127, 168, 0.62)',
    labelFill: 'rgba(71, 95, 128, 0.88)',
  },
  '敌对': {
    nodeFill: 'rgba(184, 122, 107, 0.12)',
    nodeStroke: 'rgba(184, 122, 107, 0.58)',
    edgeStroke: 'rgba(184, 122, 107, 0.52)',
    catFill: 'rgba(184, 122, 107, 0.1)',
    catStroke: 'rgba(184, 122, 107, 0.62)',
    labelFill: 'rgba(138, 92, 80, 0.88)',
  },
  '君臣': {
    nodeFill: 'rgba(142, 124, 168, 0.12)',
    nodeStroke: 'rgba(142, 124, 168, 0.58)',
    edgeStroke: 'rgba(142, 124, 168, 0.52)',
    catFill: 'rgba(142, 124, 168, 0.1)',
    catStroke: 'rgba(142, 124, 168, 0.62)',
    labelFill: 'rgba(108, 94, 128, 0.88)',
  },
}

const DEEP_NODE_TEXT_COLOR = '#8A8A8A'
const NODE_TEXT_COLOR = '#2F2926'

const BOX_DB = {
  '黄帝': {
    title: '黄帝',
    sub: '约前2717—前2599 · 华夏 · 君纪',
    paragraphs: [
      '黄帝，姬姓，号轩辕氏，被尊为华夏人文始祖。《史记》开篇第一人，"生而神灵，弱而能言，幼而徇齐，长而敦敏，成而聪明"。',
      '他统一了以熊、罴、狼、豹等为图腾的各部落，在阪泉之战中三战三胜炎帝，又在涿鹿之战擒杀蚩尤，奠定了华夏族的基本版图。',
      '黄帝时代被认为是中华文明的起源期：仓颉造字、伶伦制乐、大挠作历、岐伯论医、嫘祖养蚕——诸多文明创举都归于这个时代。',
      '黄帝崩，葬桥山。其后裔颛顼、帝喾、尧、舜相继为帝，开启了五帝时代的序幕。',
    ],
  },
  '乌台诗案': {
    title: '乌台诗案',
    sub: '1079—1080 · 华夏 · 事略',
    paragraphs: [
      '苏轼是个倒霉孩子。他写诗的时候，绝没想到一首小诗能把自己送进监狱。',
      '元丰二年，时任湖州知州的他，照例给皇帝写了份谢恩表。文章里夹了几句牢骚——没办法，变法派折腾得他实在受不了，就随手发了点感慨。',
      '结果这几句话被御史台的人盯上了。他们翻箱倒柜，从苏轼过去写的诗里挑出一百多首"有问题"的，一条条批注送到神宗面前。神宗也没怎么想，就下令把苏轼抓了。',
      '在御史台大牢里关了一百多天。苏轼以为自己要死了，写了两首绝命诗给弟弟苏辙。幸亏王安石说了句"岂有圣世而杀才士乎"，加上太后求情，最终降为检校水部员外郎、黄州团练副使。',
      '从此，黄州成了苏轼的"流放地"，却也成就了他。赤壁赋、寒食帖……那些流传千古的作品，都写于黄州。',
    ],
  },
}

function getBox(title) {
  return BOX_DB[title] || {
    title: title || '史略详情',
    sub: '华夏 · 事略',
    paragraphs: ['暂无详情内容。'],
  }
}

Page({
  behaviors: [protoPage],

  data: {
    box: null,
    tabs: ['详情', '关系', '评述', '见证'],
    activeTab: 0,
    critColors: ['#92ADA4', '#C9825A', '#7BA87B', '#B85A5A', '#84572F', '#5A8FA8'],

    // 关系图谱
    graphNodes: [],
    graphLinks: [],
    graphWidth: 800,
    graphHeight: 800,
    graphScale: '100%',
    canvasH: 400,

    // 关系列表（备用）
    relationGroups: [], // 保留供兼容
    relationTotal: 0,

    // 评述 Tab
    critiques: [],

    // 见证 Tab
    relics: [],

    // 音频
    audioOpen: false,
    playing: false,
    audioProgress: 28,
    audioCurrentTime: '01:04',
    audioDuration: '03:42',
    isFavorited: false,
    ...boxLayoutMetrics(),
  },

  _boxTitle: '',
  _canvas: null,
  _ctx: null,

  onLoad(options) {
    this.setData(boxLayoutMetrics())

    const title = decodeURIComponent(options.title || '')
    this._boxTitle = title
    const box = getBox(title)
    const rel = getRelations(title)
    const crit = getCritiques(title)
    const relics = getRelics(title)

    this.setData({
      box,
      relationGroups: rel.groups,
      relationTotal: rel.total,
      critiques: crit,
      relics,
    })

    // 构建关系图谱
    this._buildGraph(title, rel)
  },

  onReady() {
    this.setData(boxLayoutMetrics())
  },

  _buildGraph(title, rel) {
    if (rel.total === 0) return

    const relations = []
    rel.groups.forEach(g => {
      g.items.forEach(item => {
        relations.push({
          '关系ID': item.id,
          '关联史略名称': title,
          '关系节点标题': item.name,
          '关系类别': g.category,
          '关系层级': item.level,
          '上级连接线标题': item.role,
          '所属一级关系': item.parent1,
          '所属二级关系': item.parent2,
          '所属三级关系': item.parent3,
          '所属四级关系': item.parent4,
          '关系简述': item.summary,
        })
      })
    })

    const tree = buildRelationTree(relations, title)
    const { nodes, links, bounds } = layoutRadialTree(tree)

    // 保存原始数据，缩放时重新绘制
    this._graphNodes = nodes
    this._graphLinks = links
    this._graphBounds = bounds

    this.setData({
      graphNodes: nodes,
      graphLinks: links,
      graphWidth: 800,
      graphHeight: 800,
      graphScale: 1,
      graphOffsetX: 0,
      graphOffsetY: 0,
    })
  },

  onTabTap(e) {
    const tab = Number(e.currentTarget.dataset.i)
    this.setData({ activeTab: tab })
    if (tab === 1) {
      // 等 DOM 渲染完，先计算画布高度，再初始化 canvas
      setTimeout(() => {
        this._calcCanvasH(() => {
          setTimeout(() => this._initGraph(), 150)
        })
      }, 200)
    }
  },

  _calcCanvasH(cb) {
    const sys = wx.getSystemInfoSync()
    const bodyTop = this.data.bodyTop || 100
    const scrollViewH = sys.windowHeight - bodyTop
    const canvasH = scrollViewH
    this.setData({ canvasH: Math.max(350, canvasH) }, () => {
      if (cb) cb()
    })
  },

  // 初始化 Canvas 并自适应缩放
  _initGraph() {
    const query = this.createSelectorQuery()
    query.select('#relationCanvas')
      .fields({ node: true, size: true })
      .exec((res) => {
        if (!res || !res[0] || !res[0].node) return

        const canvas = res[0].node
        const ctx = canvas.getContext('2d')
        const dpr = wx.getSystemInfoSync().pixelRatio

        // 设置 canvas 物理尺寸
        let viewW = res[0].width
        let viewH = res[0].height

        // 如果尺寸还没算好（可能布局未完成），重试
        if (!viewW || !viewH || viewW < 10 || viewH < 10) {
          this._initRetryCount = (this._initRetryCount || 0) + 1
          if (this._initRetryCount < 5) {
            setTimeout(() => this._initGraph(), 300)
          }
          return
        }

        canvas.width = viewW * dpr
        canvas.height = viewH * dpr

        this._canvas = canvas
        this._ctx = ctx
        this._dpr = dpr
        this._viewW = viewW
        this._viewH = viewH

        // 自动缩放：让整个图谱适配 viewport
        this._autoFit()
      })
  },

  /** 以当前视口中心对应的图谱内容为锚点缩放（+/- 按钮） */
  _applyScaleAtViewportCenter(newScale) {
    const fitScale = this._fitScale || newScale
    const minS = this._minScale ?? 0.1
    const maxS = this._maxScale ?? 3
    newScale = Math.max(minS, Math.min(maxS, newScale))

    const oldScale = this._scale || 1
    const viewW = this._viewW || 375
    const viewH = this._viewH || 400
    const cx = viewW / 2
    const cy = viewH / 2
    const gx = (cx - (this._offsetX || 0)) / oldScale
    const gy = (cy - (this._offsetY || 0)) / oldScale

    this._scale = newScale
    this._offsetX = cx - gx * newScale
    this._offsetY = cy - gy * newScale

    this.setData({
      graphScale: Math.round((newScale / fitScale) * 100) + '%',
    })
    this._render()
  },

  _autoFit() {
    const bounds = this._graphBounds
    if (!bounds || !bounds.width || !bounds.height) return

    const pad = 28
    const scaleX = (this._viewW - pad * 2) / bounds.width
    const scaleY = (this._viewH - pad * 2) / bounds.height
    const fitScale = Math.min(scaleX, scaleY)
    const scale = fitScale

    this._fitScale = fitScale
    this._minScale = Math.max(0.08, fitScale * 0.35)
    this._maxScale = Math.min(3, fitScale * 2.5)
    this._scale = scale
    this._offsetX = this._viewW / 2 - (bounds.minX + bounds.width / 2) * scale
    this._offsetY = this._viewH / 2 - (bounds.minY + bounds.height / 2) * scale

    this.setData({
      graphScale: Math.round((scale / fitScale) * 100) + '%',
    })
    this._render()
  },

  // Canvas 触摸事件
  _touchState: null,

  onGraphTouchStart(e) {
    const touches = e.touches
    if (touches.length === 1) {
      this._touchState = {
        type: 'pan',
        startX: touches[0].x,
        startY: touches[0].y,
        startOffsetX: this._offsetX || 0,
        startOffsetY: this._offsetY || 0,
      }
    } else if (touches.length === 2) {
      const dx = touches[1].x - touches[0].x
      const dy = touches[1].y - touches[0].y
      const pinchCx = (touches[0].x + touches[1].x) / 2
      const pinchCy = (touches[0].y + touches[1].y) / 2
      const startScale = this._scale || 1
      this._touchState = {
        type: 'pinch',
        startDist: Math.hypot(dx, dy),
        startScale,
        startOffsetX: this._offsetX || 0,
        startOffsetY: this._offsetY || 0,
        startPinchCx: pinchCx,
        startPinchCy: pinchCy,
        anchorGx: (pinchCx - (this._offsetX || 0)) / startScale,
        anchorGy: (pinchCy - (this._offsetY || 0)) / startScale,
      }
    }
  },

  onGraphTouchMove(e) {
    if (!this._touchState || !this._ctx) return
    const touches = e.touches

    if (this._touchState.type === 'pan' && touches.length === 1) {
      const dx = touches[0].x - this._touchState.startX
      const dy = touches[0].y - this._touchState.startY
      this._offsetX = this._touchState.startOffsetX + dx
      this._offsetY = this._touchState.startOffsetY + dy
      this._render()
    } else if (this._touchState.type === 'pinch' && touches.length === 2) {
      const dx = touches[1].x - touches[0].x
      const dy = touches[1].y - touches[0].y
      const dist = Math.hypot(dx, dy)
      if (this._touchState.startDist < 1) return

      const ratio = dist / this._touchState.startDist
      const minS = this._minScale ?? 0.1
      const maxS = this._maxScale ?? 3
      let newScale = this._touchState.startScale * ratio
      newScale = Math.max(minS, Math.min(maxS, newScale))

      const pinchCx = (touches[0].x + touches[1].x) / 2
      const pinchCy = (touches[0].y + touches[1].y) / 2
      const { anchorGx, anchorGy } = this._touchState

      this._scale = newScale
      this._offsetX = pinchCx - anchorGx * newScale
      this._offsetY = pinchCy - anchorGy * newScale

      this.setData({
        graphScale: Math.round((newScale / (this._fitScale || newScale)) * 100) + '%',
      })
      this._render()
    }
  },

  onGraphTouchEnd() {
    this._touchState = null
  },

  _curveTangent(link, t) {
    const eps = 0.02
    const p1 = this._curvePoint(link, Math.max(0, t - eps))
    const p2 = this._curvePoint(link, Math.min(1, t + eps))
    const dx = p2.x - p1.x
    const dy = p2.y - p1.y
    const len = Math.hypot(dx, dy) || 1
    return { tx: dx / len, ty: dy / len, nx: -dy / len, ny: dx / len }
  },

  /** 点到贝塞尔曲线的最短距离（采样近似） */
  _curveMinDist(link, px, py) {
    let min = Infinity
    for (let i = 0; i <= 24; i++) {
      const p = this._curvePoint(link, i / 24)
      const d = Math.hypot(px - p.x, py - p.y)
      if (d < min) min = d
    }
    return min
  },

  /** 同父节点同类型连线沿曲线错开 t，避免标签挤在一起 */
  _edgeLabelTMap(links) {
    const labeled = links.filter(
      link => link.label && link.label.length > 0 && link.type !== 'category'
    )
    const groups = {}
    labeled.forEach(link => {
      const key = `${link.from}|${link.type}`
      if (!groups[key]) groups[key] = []
      groups[key].push(link)
    })

    const tMap = new Map()
    Object.values(groups).forEach(group => {
      group.sort((a, b) => (a.toY + a.toX * 0.3) - (b.toY + b.toX * 0.3))
      const n = group.length
      group.forEach((link, i) => {
        const along = link.labelAlong != null ? link.labelAlong : i
        const t = link.labelT != null
          ? link.labelT
          : (n === 1 ? 0.5 : 0.28 + (along / Math.max(n - 1, 1)) * 0.44)
        tMap.set(link, t)
      })
    })
    return tMap
  },

  /** 计算连线标签位置：法向偏移置于线段旁，不与线及其他标签重叠 */
  _layoutEdgeLabels(links) {
    const placed = []
    const BASE_OFFSET = 18
    const MIN_LINE_DIST = 11
    const MIN_LABEL_DIST = 26
    const tMap = this._edgeLabelTMap(links)

    const labeled = links.filter(
      link => link.label && link.label.length > 0 && link.type !== 'category'
    )

    return labeled.map((link, idx) => {
      const t = tMap.get(link) ?? 0.5
      const anchor = this._curvePoint(link, t)
      const { nx, ny } = this._curveTangent(link, t)
      let side = link.labelSide != null ? link.labelSide : (idx % 2 === 0 ? 1 : -1)
      let offset = BASE_OFFSET

      for (let attempt = 0; attempt < 10; attempt++) {
        const lx = anchor.x + nx * offset * side
        const ly = anchor.y + ny * offset * side
        let ok = this._curveMinDist(link, lx, ly) >= MIN_LINE_DIST
        if (ok) {
          for (const p of placed) {
            if (Math.hypot(lx - p.x, ly - p.y) < MIN_LABEL_DIST) {
              ok = false
              break
            }
          }
        }
        if (ok) {
          placed.push({ x: lx, y: ly })
          return { link, x: lx, y: ly }
        }
        if (attempt % 2 === 0) side *= -1
        else offset += 4
      }

      const lx = anchor.x + nx * offset * side
      const ly = anchor.y + ny * offset * side
      placed.push({ x: lx, y: ly })
      return { link, x: lx, y: ly }
    })
  },

  _drawEdgeLabel(ctx, text, x, y) {
    ctx.font = '9px sans-serif'
    ctx.fillStyle = EDGE_LABEL_COLOR
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(text, x, y)
  },

  _curvePoint(link, t) {
    const dx = link.toX - link.fromX
    const dy = link.toY - link.fromY
    const len = Math.hypot(dx, dy)
    if (len < 1) return { x: link.fromX, y: link.fromY }
    const bulge = len * (link.type === 'category' ? 0.08 : 0.2)
    const nx = -dy / len
    const ny = dx / len

    if (link.type === 'category') {
      const cx1 = link.fromX + dx * 0.5 + nx * bulge
      const cy1 = link.fromY + dy * 0.5 + ny * bulge
      const u = 1 - t
      return {
        x: u * u * link.fromX + 2 * u * t * cx1 + t * t * link.toX,
        y: u * u * link.fromY + 2 * u * t * cy1 + t * t * link.toY,
      }
    }

    const cx1 = link.fromX + dx * 0.35 + nx * bulge
    const cy1 = link.fromY + dy * 0.35 + ny * bulge
    const cx2 = link.fromX + dx * 0.65 + nx * bulge * 0.7
    const cy2 = link.fromY + dy * 0.65 + ny * bulge * 0.7
    const u = 1 - t
    return {
      x: u * u * u * link.fromX + 3 * u * u * t * cx1 + 3 * u * t * t * cx2 + t * t * t * link.toX,
      y: u * u * u * link.fromY + 3 * u * u * t * cy1 + 3 * u * t * t * cy2 + t * t * t * link.toY,
    }
  },

  _render() {
    const ctx = this._ctx
    if (!ctx) return

    const nodes = this._graphNodes
    const links = this._graphLinks
    const dpr = this._dpr
    const scale = this._scale || 1
    const offsetX = this._offsetX || 0
    const offsetY = this._offsetY || 0

    ctx.setTransform(1, 0, 0, 1, 0, 0)
    ctx.clearRect(0, 0, this._viewW * dpr, this._viewH * dpr)

    ctx.scale(dpr, dpr)
    ctx.translate(offsetX, offsetY)
    ctx.scale(scale, scale)

    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'

    const nodeById = Object.fromEntries(nodes.map(n => [n.id, n]))

    // === 第1层：连线 ===
    links.forEach(link => {
      if (isNaN(link.fromX) || isNaN(link.fromY) || isNaN(link.toX) || isNaN(link.toY)) return

      const isCategoryLink = link.type === 'category'
      let strokeStyle = GRAPH_THEME.categoryLink
      if (isCategoryLink) {
        const catNode = nodeById[link.to]
        if (catNode && GRAPH_THEME[catNode.name]) {
          strokeStyle = GRAPH_THEME[catNode.name].edgeStroke
        }
      } else {
        const theme = GRAPH_THEME[link.type] || {}
        strokeStyle = theme.edgeStroke || GRAPH_THEME.categoryLink
      }

      ctx.beginPath()
      ctx.strokeStyle = strokeStyle
      ctx.lineWidth = EDGE_LINE_WIDTH

      const dx = link.toX - link.fromX
      const dy = link.toY - link.fromY
      const len = Math.sqrt(dx * dx + dy * dy)
      if (len < 1) return

      if (isCategoryLink) {
        const bulge = len * 0.08
        const nx = -dy / len
        const ny = dx / len
        const cx1 = link.fromX + dx * 0.5 + nx * bulge
        const cy1 = link.fromY + dy * 0.5 + ny * bulge
        ctx.moveTo(link.fromX, link.fromY)
        ctx.quadraticCurveTo(cx1, cy1, link.toX, link.toY)
      } else {
        const bulge = len * 0.2
        const nx = -dy / len
        const ny = dx / len
        const cx1 = link.fromX + dx * 0.35 + nx * bulge
        const cy1 = link.fromY + dy * 0.35 + ny * bulge
        const cx2 = link.fromX + dx * 0.65 + nx * bulge * 0.7
        const cy2 = link.fromY + dy * 0.65 + ny * bulge * 0.7
        ctx.moveTo(link.fromX, link.fromY)
        ctx.bezierCurveTo(cx1, cy1, cx2, cy2, link.toX, link.toY)
      }
      ctx.stroke()
    })

    // === 第2层：关系类型节点（圆角矩形，仅填充无边框） ===
    nodes.forEach(node => {
      if (node.type !== 'category') return

      const theme = GRAPH_THEME[node.name] || {}
      const rect = node.rect || { w: 58, h: 24 }
      const w = rect.w
      const h = rect.h
      const r = 8

      ctx.beginPath()
      this._roundRect(ctx, node.x - w / 2, node.y - h / 2, w, h, r)
      ctx.fillStyle = theme.catFill || 'rgba(255, 252, 247, 0.94)'
      ctx.fill()

      ctx.font = '700 10px sans-serif'
      ctx.fillStyle = NODE_TEXT_COLOR
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText(node.name, node.x, node.y)
    })

    // === 第3层：人物/根节点胶囊 ===
    nodes.forEach(node => {
      if (node.type === 'category') return

      const isRoot = node.type === 'root'
      const levelNum = node.levelNum || 0
      const cap = node.capsule || buildCapsule(node.name, { isRoot, levelNum })
      const w = cap.w
      const h = cap.h
      const r = h / 2

      ctx.beginPath()
      ctx.fillStyle = isRoot ? 'rgba(155, 62, 56, 0.15)' : '#FFFFFF'
      this._roundRect(ctx, node.x - w / 2, node.y - h / 2, w, h, r)
      ctx.fill()
    })

    // === 第4层：连线标签（曲线法向偏移 + 碰撞消解） ===
    this._layoutEdgeLabels(links).forEach(({ link, x, y }) => {
      this._drawEdgeLabel(ctx, link.label, x, y)
    })

    // === 第5层：节点标题（胶囊内上下居中） ===
    nodes.forEach(node => {
      if (node.type === 'category') return

      const isRoot = node.type === 'root'
      const levelNum = node.levelNum || 0
      const cap = node.capsule || buildCapsule(node.name, { isRoot, levelNum })
      const fontSize = cap.fontSize

      ctx.font = `600 ${fontSize}px sans-serif`
      ctx.fillStyle = isRoot
        ? NODE_TEXT_COLOR
        : (levelNum >= 4 ? DEEP_NODE_TEXT_COLOR : NODE_TEXT_COLOR)
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText(cap.displayName || node.name, node.x, node.y)
    })
  },

  // 辅助：绘制圆角矩形路径
  _roundRect(ctx, x, y, w, h, r) {
    ctx.moveTo(x + r, y)
    ctx.lineTo(x + w - r, y)
    ctx.arcTo(x + w, y, x + w, y + r, r)
    ctx.lineTo(x + w, y + h - r)
    ctx.arcTo(x + w, y + h, x + w - r, y + h, r)
    ctx.lineTo(x + r, y + h)
    ctx.arcTo(x, y + h, x, y + h - r, r)
    ctx.lineTo(x, y + r)
    ctx.arcTo(x, y, x + r, y, r)
    ctx.closePath()
  },

  // 点击图谱节点
  onCanvasTap(e) {
    const { x, y } = e.detail
    const nodes = this._graphNodes
    const scale = this._scale || 1
    const offsetX = this._offsetX || 0
    const offsetY = this._offsetY || 0

    // 屏幕坐标 → 图谱坐标
    const gx = (x - offsetX) / scale
    const gy = (y - offsetY) / scale

    const hitNode = nodes.find(n => {
      if (n.type === 'category') return false
      const isRoot = n.type === 'root'
      const levelNum = n.levelNum || 0
      const cap = n.capsule || buildCapsule(n.name, { isRoot, levelNum })
      const dx = Math.abs(n.x - gx)
      const dy = Math.abs(n.y - gy)
      return dx <= cap.w / 2 + 4 && dy <= cap.h / 2 + 4
    })

    if (hitNode && hitNode.type === 'person') {
      wx.navigateTo({
        url: `/pages/relation-detail/relation-detail?name=${encodeURIComponent(hitNode.name)}&box=${encodeURIComponent(this._boxTitle)}`,
      })
    }
  },

  // 放大 10%
  onZoomIn() {
    const step = (this._fitScale || this._scale || 1) * 0.1
    this._applyScaleAtViewportCenter((this._scale || 1) + step)
  },

  onZoomOut() {
    const step = (this._fitScale || this._scale || 1) * 0.1
    this._applyScaleAtViewportCenter((this._scale || 1) - step)
  },

  toggleAudio() {
    this.setData({ audioOpen: !this.data.audioOpen })
  },

  togglePlay() {
    this.setData({ playing: !this.data.playing })
  },

  // 跳转关系节点详情
  onRelationTap(e) {
    const { name } = e.currentTarget.dataset
    wx.navigateTo({
      url: `/pages/relation-detail/relation-detail?name=${encodeURIComponent(name)}&box=${encodeURIComponent(this._boxTitle)}`,
    })
  },

  // 跳转评述详情
  onCritiqueTap(e) {
    const { idx } = e.currentTarget.dataset
    const c = this.data.critiques[idx]
    wx.navigateTo({
      url: `/pages/critique-detail/critique-detail?title=${encodeURIComponent(c.title)}&author=${encodeURIComponent(c.author)}&book=${encodeURIComponent(c.book)}&era=${encodeURIComponent(c.era)}&content=${encodeURIComponent(c.content)}`,
    })
  },

  // 跳转文物详情
  onRelicTap(e) {
    const { idx } = e.currentTarget.dataset
    const r = this.data.relics[idx]
    wx.navigateTo({
      url: `/pages/relic-detail/relic-detail?name=${encodeURIComponent(r.name)}&location=${encodeURIComponent(r.location)}&detail=${encodeURIComponent(r.detail)}`,
    })
  },

  // ─── 底部操作栏 ───

  // 查看原文
  onOriginalTap() {
    // 暂时切到详情 Tab（Tab 0），后续可跳转到独立原文对照页
    this.setData({ activeTab: 0 })
  },

  // 收藏/取消收藏
  onFavoriteTap() {
    const next = !this.data.isFavorited
    this.setData({ isFavorited: next })
    wx.showToast({
      title: next ? '已收藏' : '已取消收藏',
      icon: 'none',
      duration: 1200,
    })
  },

  // 分享
  onShareTap() {
    // 触发微信分享菜单
  },

  onShareAppMessage() {
    const title = this._boxTitle || '史略详情'
    return {
      title: `历史图谱 · ${title}`,
      path: `/pages/box-detail/box-detail?title=${encodeURIComponent(title)}`,
    }
  },
})
