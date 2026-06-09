// pages/index/index.js
// 历史图谱首页 - 时空矩阵
// 横轴：①中华文明 ②亚洲文明 ③欧洲文明 ④美洲文明 ⑤非洲文明
// 纵轴：时间（以中华帝王在位年限为高度基准）

const { EMPERORS, CHINA_BASE_RGB, CHINA_TEXT, DYNASTY_BG_ALPHA } = require('./emperors.js');
const { WORLD_EVENTS } = require('./worldEvents.js');

// ── 区域颜色（RGB 字符串，无括号，方便拼 rgba） ─────────────
const REGION_RGB = {
  asia:     '200,120,40',   // 暖琥珀：橙棕
  europe:   '74,128,208',   // 钢蓝
  americas: '58,154,96',    // 森绿
  africa:   '150,95,185',   // 紫罗兰（与亚洲完全区分）
};

// ── 工具函数 ──────────────────────────────────────────────

/**
 * 根据朝代计算背景色（同一红色，不同透明度）
 */
function dynastyBgColor(dynasty) {
  const alpha = DYNASTY_BG_ALPHA[dynasty] || 0.08;
  return `rgba(${CHINA_BASE_RGB},${alpha})`;
}

/**
 * 格式化年份（纯文本，用于 yearRange）
 */
function formatYear(year) {
  if (year < 0) return `前${Math.abs(year)}`;
  return `${year}`;
}

/**
 * 计算世界事件的背景色（同区域同色系，按年代远近调整透明度）
 * 越古老越透明，越近代越饱和
 */
function eventExtBg(region, event) {
  if (!event) return '';
  const rgb   = REGION_RGB[region];
  const total = 1912 - (-5500);
  const pos   = Math.max(0, Math.min(1, (event.start - (-5500)) / total));
  const alpha = +(0.08 + pos * 0.13).toFixed(2);
  return `background: rgba(${rgb},${alpha});`;
}

/**
 * 续接竖条的背景色（透明度减半，保留视觉连续性）
 */
function eventBarBg(region, event) {
  if (!event) return '';
  const rgb   = REGION_RGB[region];
  const total = 1912 - (-5500);
  const pos   = Math.max(0, Math.min(1, (event.start - (-5500)) / total));
  const alpha = +(0.04 + pos * 0.06).toFixed(2);
  return `background: rgba(${rgb},${alpha});`;
}

/**
 * 计算行高（rpx）—— 相对比例，保留长短可见差异
 *   史前（>500年）：固定分界符高度，不占空间
 *   三皇五帝（传说）：2rpx/年，上限 180rpx，适度表达长短
 *   历史帝王：5rpx/年，上限 280rpx，长短对比清晰
 */
function calcHeight(emp) {
  const reign = emp.reign;
  if (reign > 500) return 52;                                          // 史前：分界符
  if (emp.dynasty === '三皇五帝')
    return Math.max(72, Math.min(180, Math.round(reign * 2)));         // 传说：压缩比例
  return Math.max(64, Math.min(280, Math.round(reign * 5)));           // 历史帝王
}

/**
 * 从世界事件数组中找出与 [start, end] 最相关的事件
 * 优先取重叠时间最长的，次要取时间跨度最短（更精确）的
 */
function getRelevantEvent(region, start, end) {
  const candidates = WORLD_EVENTS.filter(e =>
    e.region === region && e.start <= end && e.end >= start
  );
  if (!candidates.length) return null;

  candidates.sort((a, b) => {
    const overlapA = Math.min(a.end, end) - Math.max(a.start, start);
    const overlapB = Math.min(b.end, end) - Math.max(b.start, start);
    if (overlapB !== overlapA) return overlapB - overlapA;
    return (a.end - a.start) - (b.end - b.start);
  });
  return candidates[0];
}

// ── 构建时间轴数据 ──────────────────────────────────────────

function buildTimeCells() {
  const cells = EMPERORS.map(emp => {
    const dynColor  = CHINA_TEXT;
    const dynBg     = dynastyBgColor(emp.dynasty);
    const height    = calcHeight(emp);
    // 年份标签格式：前490 / 618
    const yearLabel = emp.start < 0 ? `前${Math.abs(emp.start)}` : `${emp.start}`;

    const asia    = getRelevantEvent('asia',     emp.start, emp.end);
    const europe  = getRelevantEvent('europe',   emp.start, emp.end);
    const americas= getRelevantEvent('americas', emp.start, emp.end);
    const africa  = getRelevantEvent('africa',   emp.start, emp.end);

    return {
      id:          emp.id,
      yearLabel,
      yearRange:   `${formatYear(emp.start)}—${formatYear(emp.end)}`,
      dynasty:     emp.dynasty,
      dynastyColor: dynColor,
      dynastyBg:   dynBg,
      height,
      china: {
        name:   emp.name,
        dynasty: emp.dynasty,
        reign:  emp.reign,
        note:   emp.note || '',
        color:  dynColor,
        bg:     dynBg,
      },
      asia,
      europe,
      americas,
      africa,
      // 事件内联背景色（按年代深浅）
      asiaExtBg:     eventExtBg('asia',     asia),
      europeExtBg:   eventExtBg('europe',   europe),
      americasExtBg: eventExtBg('americas', americas),
      africaExtBg:   eventExtBg('africa',   africa),
      // 续接竖条背景色
      asiaBarBg:     eventBarBg('asia',     asia),
      europeBarBg:   eventBarBg('europe',   europe),
      americasBarBg: eventBarBg('americas', americas),
      africaBarBg:   eventBarBg('africa',   africa),
      // 续接标记（初始 false，下一步计算）
      asiaCont:     false,
      europeCont:   false,
      americasCont: false,
      africaCont:   false,
    };
  });

  // 标记"续接"（同一事件跨越多行帝王时，后续行标记 cont=true）
  const regions = ['asia', 'europe', 'americas', 'africa'];
  for (let i = 1; i < cells.length; i++) {
    for (const r of regions) {
      if (cells[i][r] && cells[i - 1][r] && cells[i][r].id === cells[i - 1][r].id) {
        cells[i][r + 'Cont'] = true;
      }
    }
  }

  return cells;
}

// ── Page 定义 ──────────────────────────────────────────────

Page({
  data: {
    timeCells: [],
    loading: true,
    selectedCell: null,
    showDetail: false,
    timeScrollTop: 0,   // 时间轴 scroll-top，由右侧纵向滚动同步驱动
  },

  onLoad() {
    const timeCells = buildTimeCells();
    this.setData({ timeCells, loading: false });
  },

  // 右侧文明列纵向滚动时，同步左侧时间轴
  onCivScroll(e) {
    this.setData({ timeScrollTop: e.detail.scrollTop });
  },

  // 点击帝王/事件格
  onCellTap(e) {
    const { cell, type } = e.currentTarget.dataset;
    if (!cell) return;

    const title = type === 'china' ? cell.name : cell.name;
    const content = type === 'china'
      ? `朝代：${cell.dynasty}\n在位：${cell.reign} 年`
      : `文明：${type === 'asia' ? '亚洲' : type === 'europe' ? '欧洲' : type === 'americas' ? '美洲' : '非洲'}\n时期：${cell.name}`;

    wx.showModal({
      title,
      content,
      showCancel: false,
      confirmText: '知道了',
    });
  },

  // 滚动到某年份
  jumpToYear(e) {
    const target = e.currentTarget.dataset.year;
    const cells = this.data.timeCells;
    const idx = cells.findIndex(c => c.china && c.china.name.includes(target));
    if (idx < 0) return;
    // 计算 scrollTop
    let top = 0;
    for (let i = 0; i < idx; i++) {
      top += cells[i].height;
    }
    this.setData({ scrollTop: top });
  },

  onAITap() {
    wx.showToast({ title: 'AI 助手开发中', icon: 'none' });
  },

  onShareAppMessage() {
    return { title: '历史图谱 · 人类文明的时空坐标', path: '/pages/index/index' };
  },
});
