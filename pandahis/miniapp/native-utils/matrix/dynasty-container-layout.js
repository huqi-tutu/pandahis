/**
 * 乱世朝代 · 矩阵「一级容器 + 二级帝王卡」通用布局
 *
 * 规范与接入步骤见：.cursor/skills/dynasty-container-matrix/SKILL.md
 * 试点：三国（220–265 一级容器，魏/蜀/吴三列二级卡）
 *
 * 外层：与普通一级色块相同——buildBlocksFromRows + 时间轴切片
 * 内层：多列堆叠二级卡，高度不与坐标轴关联
 */

const CONTAINER_RADIUS_RPX = 16
const CONTAINER_INSET_PCT = 3.2
const CONTAINER_COL_GAP_PCT = 1.6
const SUB_CARD_H_RPX = 120
const SUB_CARD_H_NANBEI_RPX = 80
const SUB_CARD_GAP_RPX = 8
/** 二级卡与外层容器之间的内边距（顶/底/侧视觉留白） */
const SUB_CARD_PAD_RPX = 24
/** 补偿 buildBlocks 垂直间距对容器底缘的占用，保证底内边距生效 */
const CONTAINER_BLOCK_GAP_RESERVE_RPX = 16

/** 二级卡片：中性亚麻纸感 — 不带色相，仅微调明度 */
/** 方案A（春秋）：暖白中性 — 比纯白降低 2-3 档明度 */
const SUB_CARD_BG_A =
  'linear-gradient(180deg, #FAF8F5 0%, #F2F0EC 100%)'
/** 方案B（战国）：冷白中性 — 比纯白降低 2-3 档明度 */
const SUB_CARD_BG_B =
  'linear-gradient(180deg, #F5F6F8 0%, #EDEEF0 100%)'
/** 三国等其余容器：中间中性 */
const SUB_CARD_BG_NEUTRAL =
  'linear-gradient(180deg, #F8F7F5 0%, #F0EFED 100%)'
const SUB_CARD_STROKE = 'box-shadow: inset 0 0 0 1rpx rgba(255,255,255,.65)'

const REGIME_TO_DYNASTY_KEY = {
  '三国·魏': '三国',
  '三国·蜀': '三国',
  '三国·吴': '三国',
  '春秋':   '春秋',
  '齐':     '春秋',
  '楚':     '春秋',
  '燕':     '春秋',
  '晋':     '春秋',
  '宋':     '春秋',
  '韩':     '战国',
  '赵':     '战国',
  '魏':     '战国',
}

/** timelineEnd：大卡片在时间轴上的结束年（与轴标衔接，避免与西晋等重叠） */
const DYNASTY_CONTAINER_LAYOUTS = {
  三国: {
    dynastyKey: '三国',
    start: 220,
    timelineEnd: 266,
    columns: [
      { key: '三国·魏' },
      { key: '三国·蜀' },
      { key: '三国·吴' },
    ],
  },
  春秋: {
    dynastyKey: '春秋',
    start: -770,
    timelineEnd: -476,
    columns: [
      { key: '东周' },
      { key: '齐' },
      { key: '秦' },
      { key: '楚' },
      { key: '宋' },
      { key: '晋' },
    ],
  },
  战国: {
    dynastyKey: '战国',
    start: -475,
    timelineEnd: -221,
    columns: [
      { key: '东周' },
      { key: '齐' },
      { key: '秦' },
      { key: '楚' },
      { key: '燕' },
      { key: '韩' },
      { key: '赵' },
      { key: '魏' },
    ],
  },
  南北朝: {
    dynastyKey: '南北朝',
    start: 420,
    timelineEnd: 589,
    rows: [
      { columns: [
        { key: '北魏' },
        { key: '东魏' },
        { key: '西魏' },
        { key: '北齐' },
        { key: '北周' },
      ]},
      { columns: [
        { key: '南朝·宋' },
        { key: '南朝·齐' },
        { key: '南朝·梁' },
        { key: '南朝·陈' },
      ]},
    ],
  },
}

function getContainerTimelineEnd(layout) {
  return layout.timelineEnd != null ? layout.timelineEnd : layout.end
}

function buildHuaxiaDynastyColorMap(axisMarks, eraColorCount) {
  const map = {}
  ;(axisMarks || []).forEach((m, i) => {
    map[m.dynastyKey] = i % eraColorCount
  })
  return map
}

function resolveHuaxiaDynastyKey(dyn, colorMap) {
  if (!dyn) return ''
  if (dyn.id === 'ZQ_HX_CHUNQIU_QINZHUHOU') return '春秋'
  if (REGIME_TO_DYNASTY_KEY[dyn.name]) return REGIME_TO_DYNASTY_KEY[dyn.name]
  const candidates = [dyn.dynasty2, dyn.dynasty_zy, dyn.dynasty, dyn.name]
  for (const k of candidates) {
    if (k && colorMap[k] != null) return k
  }
  return dyn.name || ''
}

function assignHuaxiaDynastyColorIndices(civName, dynastiesByCiv, axisMarks, eraColorCount) {
  const colorMap = buildHuaxiaDynastyColorMap(axisMarks, eraColorCount)
  const list = dynastiesByCiv[civName] || []
  list.forEach(dyn => {
    const key = resolveHuaxiaDynastyKey(dyn, colorMap)
    dyn.dynastyColorKey = key
    dyn.colorIdx = colorMap[key] != null ? colorMap[key] : 0
  })
  return colorMap
}

function getHuaxiaDynastyColorIdx(dyn, colorMap) {
  const key = resolveHuaxiaDynastyKey(dyn, colorMap)
  return colorMap[key] != null ? colorMap[key] : 0
}

const REGIME_CONTAINER_IDS = new Set(['春秋', '战国'])

function isRegimeContainerExpanded(containerId, expandedDynasties) {
  return !!(expandedDynasties && expandedDynasties[containerId])
}

function isDynastyContainerActive(containerId, expandedDynasties) {
  const layout = DYNASTY_CONTAINER_LAYOUTS[containerId]
  if (!layout) return false
  if (!expandedDynasties) return false
  if (REGIME_CONTAINER_IDS.has(containerId)) {
    return isRegimeContainerExpanded(containerId, expandedDynasties)
  }
  if (expandedDynasties[containerId]) return true
  if (layout.columns) return layout.columns.some(col => !!expandedDynasties[col.key])
  if (layout.rows) {
    return layout.rows.some(row =>
      row.columns.some(col => !!expandedDynasties[col.key])
    )
  }
  return false
}

function filterEntriesForTimeSlices(displayEntries, expandedDynasties) {
  return (displayEntries || []).filter(e => {
    if (!e.containerId) return true
    if (REGIME_CONTAINER_IDS.has(e.containerId)) return false
    if (!isDynastyContainerActive(e.containerId, expandedDynasties)) return true
    return false
  })
}

function getEmperorReignYears(emp) {
  const span = (emp.end - emp.start) || emp.years || 1
  return Math.max(1, span)
}

/** 最密列：每张固定 SUB_CARD_H_RPX，得到列总高 */
function calcUniformColumnStackHeight(cardCount) {
  if (!cardCount) return 0
  return cardCount * SUB_CARD_H_RPX + Math.max(0, cardCount - 1) * SUB_CARD_GAP_RPX
}

function calcColumnStackHeight(cardCount) {
  return calcUniformColumnStackHeight(cardCount)
}

/**
 * 同一容器内各列对齐到 targetStackH。
 * 最密列（张数=maxCount）：每张 120rpx；
 * 其余列：在 targetStackH 内按在位时长等比分配各卡高度。
 */
function calcColumnCardHeights(emperors, targetStackH, isDenseColumn) {
  const n = emperors.length
  if (!n || targetStackH <= 0) return []

  const gapTotal = Math.max(0, n - 1) * SUB_CARD_GAP_RPX
  const cardArea = targetStackH - gapTotal
  if (n === 1) return [{ emp: emperors[0], h: cardArea }]

  if (isDenseColumn) {
    return emperors.map(emp => ({ emp, h: SUB_CARD_H_RPX }))
  }

  const weights = emperors.map(getEmperorReignYears)
  const totalWeight = weights.reduce((a, b) => a + b, 0)
  const minTotal = n * SUB_CARD_H_RPX
  let heights

  if (minTotal >= cardArea) {
    heights = weights.map(w => Math.floor(cardArea * w / totalWeight))
  } else {
    const extra = cardArea - minTotal
    heights = weights.map(w =>
      Math.floor(SUB_CARD_H_RPX + extra * w / totalWeight)
    )
  }

  let used = heights.reduce((a, b) => a + b, 0)
  for (let i = 0; used < cardArea; i += 1) {
    heights[i % n] += 1
    used += 1
  }
  while (used > cardArea) {
    const idx = heights.findIndex(h => h > SUB_CARD_H_RPX)
    if (idx < 0) break
    heights[idx] -= 1
    used -= 1
  }

  return emperors.map((emp, idx) => ({ emp, h: heights[idx] }))
}

function calcContainerMinTimelineHeight(displayEntries, containerId) {
  const layout = DYNASTY_CONTAINER_LAYOUTS[containerId]
  if (!layout) return 0
  if (layout.rows) {
    // 多行容器：每行内取最大列卡片数，多行叠加
    const cardH = containerId === '南北朝' ? SUB_CARD_H_NANBEI_RPX : SUB_CARD_H_RPX
    let totalH = 0
    layout.rows.forEach((row, ri) => {
      const counts = row.columns.map(col =>
        (displayEntries || []).filter(e =>
          e.containerId === containerId && e.containerColumn === col.key
        ).length
      )
      const maxCount = Math.max(0, ...counts)
      const rowH = cardH * maxCount + Math.max(0, maxCount - 1) * SUB_CARD_GAP_RPX
      totalH += rowH
      if (ri < layout.rows.length - 1) totalH += SUB_CARD_GAP_RPX
    })
    // 南北朝容器底部额外留白，让隋文帝卡片可以重叠在容器区域内
    const bottomPad = 0
    return totalH + SUB_CARD_PAD_RPX * 2 + CONTAINER_BLOCK_GAP_RESERVE_RPX + bottomPad
  }
  const counts = layout.columns.map(col =>
    (displayEntries || []).filter(e =>
      e.containerId === containerId && e.containerColumn === col.key
    ).length
  )
  const maxCount = Math.max(0, ...counts)
  return calcUniformColumnStackHeight(maxCount)
    + SUB_CARD_PAD_RPX * 2
    + CONTAINER_BLOCK_GAP_RESERVE_RPX
}

/**
 * 容器时段行高不足时，等比放大该时段各切片高度（仍与时间轴年界对齐）
 */
function applyContainerTimelineHeightBoost(mergedSlices, expandedDynasties, displayEntries, calcSliceH) {
  if (!mergedSlices || !mergedSlices.length) return

  Object.keys(DYNASTY_CONTAINER_LAYOUTS).forEach(containerId => {
    if (!isDynastyContainerActive(containerId, expandedDynasties)) return
    const layout = DYNASTY_CONTAINER_LAYOUTS[containerId]
    const timelineEnd = getContainerTimelineEnd(layout)
    const minTotalH = calcContainerMinTimelineHeight(displayEntries, containerId)
    if (minTotalH <= 0) return

    const indices = []
    let currentTotal = 0
    mergedSlices.forEach((sl, i) => {
      if (sl.tE <= layout.start || sl.tS >= timelineEnd) return
      indices.push(i)
      currentTotal += calcSliceH(sl.tS, sl.tE, sl.active)
    })
    if (!indices.length || currentTotal >= minTotalH) return

    const scale = minTotalH / currentTotal
    indices.forEach(i => {
      mergedSlices[i]._containerHeightScale = scale
    })
  })
}

function findContainerBlock(blocks, containerId) {
  const entryId = `container_span_${containerId}`
  const segs = (blocks || [])
    .filter(b => b.entryId === entryId || b.containerId === containerId)
    .sort((a, b) => a.top - b.top)
  if (!segs.length) return null
  const top = segs[0].top
  const bottom = Math.max(...segs.map(s => s.top + s.h))
  return {
    entryId,
    top,
    h: bottom - top,
    leftPct: segs[0].leftPct,
    widthPct: segs[0].widthPct,
    segs,
  }
}

function calcColumnGeometry(numCols, insetPct, gapPct) {
  const n = Math.max(1, numCols)
  const gaps = (n - 1) * gapPct
  const usable = 100 - insetPct * 2 - gaps
  const widthPct = usable / n
  let left = insetPct
  return Array.from({ length: n }, (_, i) => {
    const geom = { leftPct: left, widthPct, colIndex: i, numCols: n }
    left += widthPct + (i < n - 1 ? gapPct : 0)
    return geom
  })
}

function buildDynastyContainerVisuals(ctx) {
  const {
    blocks,
    displayEntries,
    expandedDynasties,
    civId,
    entryToCardFields,
    fitCardTimeFontSize,
    inferLabelLayout,
    HEADER_TOP_INSET,
  } = ctx

  const subCards = []
  const subOverlays = []

  Object.keys(DYNASTY_CONTAINER_LAYOUTS).forEach(containerId => {
    const layout = DYNASTY_CONTAINER_LAYOUTS[containerId]
    if (!isDynastyContainerActive(containerId, expandedDynasties)) return
    const isChunqiu = containerId === '春秋'
    const isZhanguo = containerId === '战国'
    const isNanbei = containerId === '南北朝'
    const subCardBg = isChunqiu ? SUB_CARD_BG_A : isZhanguo ? SUB_CARD_BG_B : SUB_CARD_BG_NEUTRAL

    const containerBlock = findContainerBlock(blocks, containerId)
    if (!containerBlock) return

    // 南北朝容器无额外底部留白，时间轴表现与实际时间一致

    const innerTop = containerBlock.top + SUB_CARD_PAD_RPX

    if (layout.rows) {
      // 多行容器（南北朝专用）
      const cardH = containerId === '南北朝' ? SUB_CARD_H_NANBEI_RPX : SUB_CARD_H_RPX
      let rowTop = innerTop
      layout.rows.forEach((row, ri) => {
        const colGeoms = calcColumnGeometry(
          row.columns.length,
          CONTAINER_INSET_PCT,
          CONTAINER_COL_GAP_PCT
        )
        const columnPlans = row.columns.map((col, colIdx) => {
          const members = (displayEntries || [])
            .filter(e => e.containerId === containerId && e.containerColumn === col.key)
            .sort((a, b) => a.start - b.start)
          return { colIdx, geom: colGeoms[colIdx], members }
        })
        const maxCount = Math.max(0, ...columnPlans.map(p => p.members.length))
        if (!maxCount) return
        const targetStackH = cardH * maxCount + Math.max(0, maxCount - 1) * SUB_CARD_GAP_RPX

        columnPlans.forEach(plan => {
          const { geom, members, colIdx } = plan
          if (!members.length) return
          const isDenseColumn = members.length === maxCount
          const cardLayouts = calcColumnCardHeights(members, targetStackH, isDenseColumn)
          let cardTop = rowTop
          cardLayouts.forEach(({ emp, h: empH }) => {
            const fields = entryToCardFields(emp, civId)
            const top = cardTop
            const cardId = `${emp.id}_sub_${containerId}_r${ri}_c${colIdx}`
            const isRegimeCard = !!emp.isRegimeOnly
            const actualH = containerId === '南北朝' ? Math.min(empH, cardH) : empH

            subCards.push(Object.assign({}, fields, {
              id: cardId,
              entryId: emp.id,
              legacyId: emp.legacyId || '',
              isContainerSubCard: true,
              containerId,
              top,
              h: actualH,
              leftPct: geom.leftPct,
              widthPct: geom.widthPct,
              subCardBg,
              subCardStroke: SUB_CARD_STROKE,
              radiusRpx: 12,
              cardBg: subCardBg,
              zIndex: 8,
              entityType: 'regime',
              entityId: emp.regimeId || emp.id,
              regimeId: emp.regimeId || emp.id,
              dynastyId: emp.dynastyId || '',
            }))

            const timeFontRpx = fitCardTimeFontSize(fields.timeRange, geom.widthPct)
            subOverlays.push({
              id: `${cardId}_chrome`,
              entryId: emp.id,
              kind: fields.kind,
              person: fields.person,
              displayName: fields.displayName,
              dynasty: fields.dynasty,
              timeRange: fields.timeRange,
              highlights: fields.highlights || [],
              hideLabels: false,
              hideTags: false,
              hideTime: !!fields.hideTime || !!emp.isRegimeOnly,
              labelLayout: inferLabelLayout(geom.widthPct),
              headerTop: top,
              headerLeftPct: geom.leftPct,
              headerWidthPct: geom.widthPct,
              headerHeight: actualH,
              timeFontRpx,
              zIndex: 25,
              isRegimeCard,
            })

            cardTop += actualH + SUB_CARD_GAP_RPX
          })
        })
        rowTop += calcUniformColumnStackHeight(maxCount) + SUB_CARD_GAP_RPX
      })
      return
    }

    // 单行容器（三国/春秋/战国 原有逻辑）
    const colGeoms = calcColumnGeometry(
      layout.columns.length,
      CONTAINER_INSET_PCT,
      CONTAINER_COL_GAP_PCT
    )

    const columnPlans = layout.columns.map((col, colIdx) => {
      const members = (displayEntries || [])
        .filter(e => e.containerId === containerId && e.containerColumn === col.key)
        .sort((a, b) => a.start - b.start)
      return { colIdx, geom: colGeoms[colIdx], members }
    })

    const maxCount = Math.max(0, ...columnPlans.map(p => p.members.length))
    if (!maxCount) return

    const targetStackH = calcUniformColumnStackHeight(maxCount)

    columnPlans.forEach(plan => {
      const { geom, members, colIdx } = plan
      if (!members.length) return

      const isDenseColumn = members.length === maxCount
      const cardLayouts = calcColumnCardHeights(members, targetStackH, isDenseColumn)
      let cardTop = innerTop

      cardLayouts.forEach(({ emp, h: cardH }) => {
        const fields = entryToCardFields(emp, civId)
        const top = cardTop
        const cardId = `${emp.id}_sub_${colIdx}`
        const isRegimeCard = !!emp.isRegimeOnly
        const cardHeaderTop = isRegimeCard ? top : top + HEADER_TOP_INSET

        subCards.push(Object.assign({}, fields, {
          id: cardId,
          entryId: emp.id,
          legacyId: emp.legacyId || '',
          isContainerSubCard: true,
          containerId,
          top,
          h: cardH,
          leftPct: geom.leftPct,
          widthPct: geom.widthPct,
          subCardBg,
          subCardStroke: SUB_CARD_STROKE,
          radiusRpx: 12,
          cardBg: subCardBg,
          zIndex: 8,
          entityType: emp.isRegimeOnly ? 'regime' : 'emperor',
          entityId: emp.regimeId || emp.id,
          regimeId: emp.regimeId || emp.id,
          dynastyId: emp.dynastyId || '',
        }))

        const timeFontRpx = fitCardTimeFontSize(fields.timeRange, geom.widthPct)
        const useStackedLayout = containerId === '三国'
        subOverlays.push({
          id: `${cardId}_chrome`,
          entryId: emp.id,
          kind: fields.kind,
          person: fields.person,
          displayName: fields.displayName,
          dynasty: fields.dynasty,
          timeRange: fields.timeRange,
          highlights: fields.highlights || [],
          hideLabels: false,
          hideTags: false,
          hideTime: !!fields.hideTime || !!emp.isRegimeOnly,
          labelLayout: useStackedLayout ? 'stacked' : inferLabelLayout(geom.widthPct),
          headerTop: cardHeaderTop,
          headerLeftPct: geom.leftPct,
          headerWidthPct: geom.widthPct,
          headerHeight: useStackedLayout ? Math.max(0, cardH - HEADER_TOP_INSET * 2) : 0,
          timeFontRpx,
          zIndex: 25,
          isRegimeCard,
        })

        cardTop += cardH + SUB_CARD_GAP_RPX
      })
    })
  })

  return { subCards, subOverlays }
}

function applyDynastyContainerBlockStyles(blocks) {
  ;(blocks || []).forEach(b => {
    if (!b.isDynastyContainer) return
    b.radiusStyle = `${CONTAINER_RADIUS_RPX}rpx`
    b.edgeClass = (b.edgeClass || '') + ' era-block--dynasty-container'
    // 容器底色须在二级卡之下（二级卡 z-index 8）
    b.zIndex = 3
  })
}

module.exports = {
  DYNASTY_CONTAINER_LAYOUTS,
  REGIME_TO_DYNASTY_KEY,
  SUB_CARD_BG_A,
  SUB_CARD_BG_B,
  SUB_CARD_BG_NEUTRAL,
  CONTAINER_RADIUS_RPX,
  SUB_CARD_H_RPX,
  SUB_CARD_PAD_RPX,
  CONTAINER_BLOCK_GAP_RESERVE_RPX,
  buildHuaxiaDynastyColorMap,
  resolveHuaxiaDynastyKey,
  assignHuaxiaDynastyColorIndices,
  getHuaxiaDynastyColorIdx,
  isDynastyContainerActive,
  isRegimeContainerExpanded,
  REGIME_CONTAINER_IDS,
  filterEntriesForTimeSlices,
  calcContainerMinTimelineHeight,
  applyContainerTimelineHeightBoost,
  buildDynastyContainerVisuals,
  applyDynastyContainerBlockStyles,
  getContainerTimelineEnd,
}
