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
  { label: '宋', key: '北宋', start: 960 },
  { label: '元', key: '元',   start: 1271 },
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
function buildNavFromRows(matrixRows, ratio, civId) {
  const emperorCounts = getHomeEmperorCountMap(civId)
  const navItems = NAV_PRIMARY_DYNASTIES.map(d => {
    // 在 matrixRows 中找同 key 的第一行（检查 hxDynastyKey 和 dynastyKey）
    const row = (matrixRows || []).find(r =>
      r.hxDynastyKey === d.key || r.dynastyKey === d.key
    )
    const yPx = row ? Math.round(row.y * ratio) : 0
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
 * 根据 scrollTop 找到当前所在朝代（navItems 中的 index）
 *
 * @param {number} scrollTopPx
 * @param {Array} navItems    - buildNavFromRows 返回的 navItems
 * @returns {number} 当前激活的朝代在 navItems 中的索引（-1 表示无匹配）
 */
function findActiveNavIndex(scrollTopPx, navItems) {
  if (!navItems || !navItems.length) return -1
  // 找到最接近视口顶部的朝代（第一个 yPx 在视口范围内或刚好在视口上方的）
  var viewportBottom = scrollTopPx + 20
  var bestIdx = -1
  var bestDist = Infinity
  for (var i = 0; i < navItems.length; i++) {
    var yPx = navItems[i].yPx
    // 跳过 yPx 无效的项目
    if (yPx < 0) continue
    // 取朝代顶边到视口顶边的距离（接近 0 表示在视口顶部）
    var dist = Math.abs(yPx - scrollTopPx)
    if (dist < bestDist) {
      bestDist = dist
      bestIdx = i
    }
  }
  return bestIdx
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
  buildHomeEmperorCountMap,
  getHomeEmperorCountMap,
  invalidateHomeEmperorCountCache,
  buildNavFromRows,
  findActiveNavIndex,
  getEmperorCount,
  getPrimaryDynastyLabels,
}
