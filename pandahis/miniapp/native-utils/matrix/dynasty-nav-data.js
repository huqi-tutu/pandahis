/**
 * 历史图谱 · 朝代导航索引数据模块
 *
 * 为首页左侧朝代导航索引、Mini Map、HUD 提供一二级朝代数据
 * 和矩阵 y 坐标映射。
 *
 * 设计目标（Phase 3 兼容）：
 *   1. 集中存放一级朝代列表（索引项）
 *   2. 提供 matrixRows → 朝代 y 坐标映射函数
 *   3. 提供 emperor 计数（与首页矩阵展开态一致）
 *   4. 数据计算独立于页面逻辑，Phase 3 拖动交互直接复用
 */

const { buildRows } = require('./mock-home-matrix.js')

// ─── 一级朝代导航索引 ─────────────────────────────────────────────
// 规则：只显示一级朝代，不显示西汉/东汉、北宋/南宋、五代十国、十六国
// 周→西周起点，汉→西汉起点，晋→西晋起点，宋→北宋起点
const NAV_PRIMARY_DYNASTIES = [
  { label: '夏', key: '夏',   start: -2070 },
  { label: '商', key: '商',   start: -1600 },
  { label: '周', key: '西周', start: -1046 },
  { label: '秦', key: '秦',   start: -221 },
  { label: '汉', key: '西汉', start: -202 },
  { label: '晋', key: '西晋', start: 266 },
  { label: '隋', key: '隋',   start: 581 },
  { label: '唐', key: '唐',   start: 618 },
  { label: '宋', key: '宋', start: 960 },
  { label: '元', key: '元',   start: 1260 },
  { label: '明', key: '明',   start: 1368 },
  { label: '清', key: '清',   start: 1636 },
]

// ─── 帝王计数（静态兜底，HUD 优先用 buildHomeEmperorCountMap 动态值） ──
const EMPEROR_COUNT_MAP = {
  '夏':   17,
  '商':   30,
  '周':   38,
  '西周': 12,
  '东周': 26,
  '秦':   2,
  '西汉': 15,
  '东汉': 14,
  '三国': 11,
  '西晋': 4,
  '东晋': 11,
  '隋':   2,
  '唐':   21,
  '五代十国': 8,
  '北宋': 9,
  '南宋': 9,
  '元':   8,
  '明':   15,
  '清':   11,
}

let _homeEmperorCountCache = null

/**
 * 按首页矩阵展开规则统计各朝代帝王数（与卡片展示一致）
 * 规则：单独展开该朝代后，统计 kind=single 且 dynasty 匹配的 overlay 数
 */
function buildHomeEmperorCountMap(civId) {
  const slug = civId || 'huaxia'
  const counts = {}
  NAV_PRIMARY_DYNASTIES.forEach(d => {
    try {
      const layout = buildRows(slug, { [d.key]: true })
      counts[d.key] = (layout.overlays || []).filter(o =>
        o.kind === 'single' && o.dynasty === d.key
      ).length
    } catch (err) {
      counts[d.key] = EMPEROR_COUNT_MAP[d.key] || 0
    }
  })
  return counts
}

function getHomeEmperorCountMap(civId) {
  if (!_homeEmperorCountCache) {
    _homeEmperorCountCache = buildHomeEmperorCountMap(civId)
  }
  return _homeEmperorCountCache
}

function invalidateHomeEmperorCountCache() {
  _homeEmperorCountCache = null
}

/**
 * 由 matrixRows 建立"朝代 key → y 坐标(px)"的映射
 *
 * @param {Array} matrixRows  - buildRows 返回的 rows 数组
 * @param {number} ratio      - rpx→px 比例（screenW / 750）
 * @returns {Object}  { navItems, dynYMap }
 *   navItems: 每项 { label, key, start, yPx, emperorCount }
 *   dynYMap:  { [dynastyKey]: yPx } 用于 Mini Map 计算
 */
function findNavRow(matrixRows, dynasty) {
  const key = String(dynasty.key || '').trim()
  const label = String(dynasty.label || '').trim()
  return (matrixRows || []).find(r =>
    r.hxDynastyKey === key ||
    r.dynastyKey === key ||
    r.hxLabel === key ||
    r.hxLabel === label
  ) || null
}

function buildNavFromRows(matrixRows, ratio, civId) {
  const emperorCounts = getHomeEmperorCountMap(civId)
  const navItems = NAV_PRIMARY_DYNASTIES.map(d => {
    const row = findNavRow(matrixRows, d)
    const yPx = row ? Math.round(row.y * ratio) : -1
    return {
      label:   d.label,
      key:     d.key,
      start:   d.start,
      yPx,
      emperorCount: emperorCounts[d.key] || 0,
    }
  })

  // dynYMap: 所有 HUAXIA_AXIS_MARKS 中出现的 dynastyKey → yPx
  // 供 Mini Map 和 Phase 3 拖动使用
  const dynYMap = {}
  if (matrixRows) {
    matrixRows.forEach(r => {
      if (r.hxDynastyKey && !(r.hxDynastyKey in dynYMap)) {
        dynYMap[r.hxDynastyKey] = Math.round(r.y * ratio)
      }
    })
  }

  return { navItems, dynYMap }
}

/**
 * 根据 scrollTop 找到视口顶部对应的朝代（navItems 中的 index）
 *
 * 规则：取 yPx 不超过视口顶线（+ 阈值）的最后一个索引项；
 * 五帝等不在 nav 中的顶部段（scrollTop 尚未到达首个索引）返回 -1。
 */
function findActiveNavIndex(scrollTopPx, navItems, thresholdPx, opts) {
  if (!navItems || !navItems.length) return -1
  const topLine = Math.max(0, scrollTopPx + (thresholdPx != null ? thresholdPx : 32))
  let bestIdx = -1
  for (let i = 0; i < navItems.length; i++) {
    const yPx = navItems[i].yPx
    if (yPx <= 0) continue
    if (yPx <= topLine) bestIdx = i
    else break
  }

  const pinnedKey = opts && opts.pinnedKey ? String(opts.pinnedKey).trim() : ''
  const maxScroll = opts && opts.maxScroll
  if (
    pinnedKey &&
    maxScroll != null &&
    Number.isFinite(maxScroll) &&
    scrollTopPx >= maxScroll - 16
  ) {
    const pinnedIdx = navItems.findIndex(item => item.key === pinnedKey || item.label === pinnedKey)
    if (pinnedIdx >= 0 && navItems[pinnedIdx].yPx > maxScroll) {
      return pinnedIdx
    }
  }
  return bestIdx
}

/** 末代无法置顶时，选中明/清仍须把两张卡完整露出来 */
const NAV_REVEAL_CLUSTERS = [
  ['明', '清'],
]

function getNavRevealCluster(key) {
  const k = String(key || '').trim()
  if (!k) return []
  const cluster = NAV_REVEAL_CLUSTERS.find(keys => keys.indexOf(k) >= 0)
  return cluster ? cluster.slice() : [k]
}

function calcMaxScrollPx(totalHRpx, bottomPadRpx, ratio, viewportPx) {
  const r = Number(ratio) || 0
  const contentPx = (Number(totalHRpx) || 0) * r + (Number(bottomPadRpx) || 0) * r
  return Math.max(0, contentPx - (Number(viewportPx) || 0))
}

function blockMatchesNavKey(block, key) {
  if (!block || !key) return false
  if (block.containerId === key) return true
  if (block.entryId === `container_span_${key}`) return true
  if (block.dynasty === key || block.displayName === key) return true
  if (key === '宋' && (block.dynasty === '北宋' || block.displayName === '北宋' || block.dynasty === '南宋')) return true
  if (key === '两晋' && (block.dynasty === '西晋' || block.dynasty === '东晋')) return true
  if (key === '周' && (block.dynasty === '西周' || block.dynasty === '东周')) return true
  if (key === '汉' && (block.dynasty === '西汉' || block.dynasty === '东汉')) return true
  if (key === '晋' && (block.dynasty === '西晋' || block.dynasty === '东晋')) return true
  return false
}

function measureKeysRangePx(keys, ctx) {
  const ratio = ctx.ratio || 0.5
  const blocks = ctx.matrixBlocks || []
  const navItems = ctx.navItems || []
  let topPx = Infinity
  let bottomPx = -Infinity

  ;(keys || []).forEach(key => {
    const matched = blocks.filter(b => blockMatchesNavKey(b, key))
    matched.forEach(b => {
      const top = Number(b.top) * ratio
      const bottom = (Number(b.top) + Number(b.h)) * ratio
      if (Number.isFinite(top)) topPx = Math.min(topPx, top)
      if (Number.isFinite(bottom)) bottomPx = Math.max(bottomPx, bottom)
    })
    if (matched.length) return
    const navItem = navItems.find(item => item.key === key || item.label === key)
    if (navItem && navItem.yPx > 0) {
      topPx = Math.min(topPx, navItem.yPx)
      bottomPx = Math.max(bottomPx, navItem.yPx)
    }
  })

  if (!Number.isFinite(topPx) || !Number.isFinite(bottomPx) || bottomPx < topPx) return null
  return { topPx, bottomPx }
}

/**
 * 索引导航吸附：默认把目标朝代置顶；末代置顶不下时，保证需露出来的卡片完整可见。
 */
function resolveNavSnapTopPx(targetKey, ctx) {
  const key = String(targetKey || '').trim()
  if (!key || !ctx) return 0
  const ratio = ctx.ratio || 0.5
  const viewportPx = Number(ctx.matrixHeight) || 0
  const maxScroll = calcMaxScrollPx(
    ctx.matrixTotalH,
    ctx.matrixScrollBottomPad,
    ratio,
    viewportPx
  )
  const navItems = ctx.navItems || []
  const item = navItems.find(i => i.key === key || i.label === key)
  const clusterKeys = getNavRevealCluster(key)
  const range = measureKeysRangePx(clusterKeys, ctx)
  const pinTop = item && item.yPx > 0
    ? item.yPx
    : (range ? range.topPx : 0)
  const inset = ctx.scrollInsetPx != null ? ctx.scrollInsetPx : 8
  const preferred = Math.max(0, pinTop - inset)

  if (range && viewportPx > 0 && range.bottomPx - range.topPx <= viewportPx) {
    const minScroll = Math.max(0, range.bottomPx - viewportPx)
    const maxKeepTop = Math.max(0, range.topPx - inset)
    let snap = preferred
    if (snap < minScroll) snap = minScroll
    if (snap > maxKeepTop) snap = maxKeepTop
    return Math.max(0, Math.min(maxScroll, snap))
  }

  return Math.max(0, Math.min(maxScroll, preferred))
}

/**
 * 在某 navItem 的年范围内查找帝王数（从 emperor-data.js 中统计）
 * @param {string} key
 * @returns {number}
 */
function getEmperorCount(key) {
  const counts = getHomeEmperorCountMap()
  return counts[key] || EMPEROR_COUNT_MAP[key] || 0
}

// ─── 一级朝代列表（纯文案，供模板遍历） ──────────────────────────
function getPrimaryDynastyLabels() {
  return NAV_PRIMARY_DYNASTIES.map(d => d.label)
}

module.exports = {
  NAV_PRIMARY_DYNASTIES,
  EMPEROR_COUNT_MAP,
  NAV_REVEAL_CLUSTERS,
  buildHomeEmperorCountMap,
  getHomeEmperorCountMap,
  invalidateHomeEmperorCountCache,
  buildNavFromRows,
  findActiveNavIndex,
  calcMaxScrollPx,
  resolveNavSnapTopPx,
  getNavRevealCluster,
  getEmperorCount,
  getPrimaryDynastyLabels,
}
