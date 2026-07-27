/**
 * 南北朝 + 隋 联动收展与布局同步
 * - 收起：两张标准朝代卡（200rpx），16rpx 间距，581 刻度与隋卡顶齐线
 * - 展开：南北朝容器第二行子卡上移，避免被隋文帝遮挡
 */

const BLOCK_V_GAP_RPX = 16
const BLOCK_MIN_SEG_H = 20
const COLLAPSED_DYNASTY_CARD_H_RPX = 200
const NANBEI_AXIS_KEY = '南北朝'
const SUI_AXIS_KEY = '隋'
const NANBEI_LINKED_AXIS_KEYS = ['南北朝', '隋']
const NANBEI_ENTRY = 'merged_南北朝'
const SUI_ENTRY = 'ZQ_HX_SUI_SUI'
const NANBEI_CONTAINER_ID = '南北朝'
const SUI_WENDI_ENTRY = 'DW_HX_SUI_SUI_SUIWENDI'

function isBridgeBlock(b) {
  return !!(b && (b.isLBridge || b.isNanbeiLBridge || b.isNanbei581VBridge || b.isBridgeBlock))
}

function isNanbeiLinkedAxisKey(dynKey) {
  return NANBEI_LINKED_AXIS_KEYS.indexOf(dynKey) >= 0
}

function isNanbeiSuiExpanded(expandedDynasties) {
  if (!expandedDynasties) return false
  return !!(expandedDynasties[NANBEI_AXIS_KEY] || expandedDynasties[SUI_AXIS_KEY])
}

function isNanbeiSuiCollapsed(expandedDynasties) {
  return !isNanbeiSuiExpanded(expandedDynasties)
}

function isNanbeiContainerActive(expandedDynasties) {
  return isNanbeiSuiExpanded(expandedDynasties)
}

function applyNanbeiSuiLinkedExpansion(next, willExpand, civName, helpers) {
  if (willExpand) {
    next[NANBEI_AXIS_KEY] = true
    next[SUI_AXIS_KEY] = true
    if (helpers && helpers.setContainerExpandedState) {
      helpers.setContainerExpandedState(next, NANBEI_CONTAINER_ID, civName, true)
    }
  } else {
    delete next[NANBEI_AXIS_KEY]
    delete next[SUI_AXIS_KEY]
    if (helpers && helpers.setContainerExpandedState) {
      helpers.setContainerExpandedState(next, NANBEI_CONTAINER_ID, civName, false)
    }
  }
  return next
}

/** 收起态：581 起不再并列南北朝，避免 581–589 并行时间片撑高 */
function filterActiveForNanbeiSui(active, tS, expandedDynasties) {
  if (!active || !active.length) return active
  if (isNanbeiSuiExpanded(expandedDynasties)) return active
  if (tS < 581) return active
  return active.filter(e =>
    e.id !== NANBEI_ENTRY &&
    e.dynastyName !== NANBEI_AXIS_KEY &&
    e.dynastyGroup !== NANBEI_AXIS_KEY
  )
}

function findCollapsedCard(blocks, entryId) {
  return blocks.find(b => b.entryId === entryId && !isBridgeBlock(b) && !b.isDynastyContainer)
}

function rechainRowsFrom(rows, startIdx) {
  if (!rows.length || startIdx < 0) return
  let chainY = startIdx > 0
    ? rows[startIdx - 1].y + rows[startIdx - 1].h
    : rows[startIdx].y
  for (let i = startIdx; i < rows.length; i++) {
    rows[i].y = chainY
    chainY += rows[i].h
  }
}

function trimRowsBeforeTarget(rows, targetRowIdx, amount) {
  if (amount <= 0 || targetRowIdx <= 0) return 0
  let remaining = amount
  let trimStartIdx = targetRowIdx
  for (let i = targetRowIdx - 1; i >= 0 && remaining > 0; i--) {
    const cut = Math.min(rows[i].h, remaining)
    if (cut <= 0) continue
    rows[i].h -= cut
    remaining -= cut
    trimStartIdx = i
  }
  rechainRowsFrom(rows, trimStartIdx)
  return amount - remaining
}

/** 收起态：南北朝 + 隋 各一张标准朝代卡，581 刻度与隋顶齐线 */
function syncCollapsedNanbeiSuiTimeline(rows, blocks, overlays, expandedDynasties, ctx) {
  if (isNanbeiSuiExpanded(expandedDynasties) || !rows || !rows.length) return 0

  const CARD_H = ctx && ctx.collapsedDynastyCardH != null
    ? ctx.collapsedDynastyCardH
    : COLLAPSED_DYNASTY_CARD_H_RPX
  const GAP = ctx && ctx.collapsedDynastyGapRpx != null
    ? ctx.collapsedDynastyGapRpx
    : BLOCK_V_GAP_RPX

  const nb = findCollapsedCard(blocks, NANBEI_ENTRY)
  const sui = findCollapsedCard(blocks, SUI_ENTRY)
  if (!nb || !sui) return 0

  const row420Idx = rows.findIndex(r => r.tS === 420)
  const row581Idx = rows.findIndex(r => r.tS === 581)
  if (row420Idx < 0 || row581Idx <= row420Idx) return 0

  const row420 = rows[row420Idx]
  const nbTop = row420.y + Math.max(0, Math.round((row420.h - CARD_H) / 2))
  nb.top = nbTop
  nb.h = CARD_H
  nb.leftPct = 0
  nb.widthPct = 100

  const targetSuiTop = nbTop + CARD_H + GAP
  let row581Y = rows[row581Idx].y
  const delta = targetSuiTop - row581Y
  let shiftAmount = 0

  if (delta > 1) {
    for (let i = row581Idx; i < rows.length; i++) {
      rows[i].y += delta
    }
    shiftAmount = delta
    row581Y = rows[row581Idx].y
    const shiftBoundary = row581Y - delta
    blocks.forEach(b => {
      if (isBridgeBlock(b)) return
      if (b.entryId === NANBEI_ENTRY) return
      if (b.top >= shiftBoundary - 1) b.top += delta
    })
    if (overlays && overlays.length) {
      overlays.forEach(ov => {
        if (ov.entryId === NANBEI_ENTRY) return
        if (ov.headerTop != null && ov.headerTop >= shiftBoundary - 1) {
          ov.headerTop += delta
          if (ov.barTop != null && ov.barTop >= shiftBoundary - 1) ov.barTop += delta
        }
      })
    }
  } else if (delta < -1) {
    const trimAmount = trimRowsBeforeTarget(rows, row581Idx, -delta)
    shiftAmount = -trimAmount
    row581Y = rows[row581Idx].y
    if (trimAmount > 1) {
      const shiftBoundary = row581Y + trimAmount
      blocks.forEach(b => {
        if (isBridgeBlock(b)) return
        if (b.entryId === NANBEI_ENTRY || b.entryId === SUI_ENTRY) return
        if (b.top >= shiftBoundary - 1) b.top -= trimAmount
      })
      if (overlays && overlays.length) {
        overlays.forEach(ov => {
          if (ov.entryId === NANBEI_ENTRY || ov.entryId === SUI_ENTRY) return
          if (ov.headerTop != null && ov.headerTop >= shiftBoundary - 1) {
            ov.headerTop -= trimAmount
            if (ov.barTop != null && ov.barTop >= shiftBoundary - 1) ov.barTop -= trimAmount
          }
        })
      }
    }
  }

  sui.top = targetSuiTop
  sui.h = CARD_H
  sui.leftPct = 0
  sui.widthPct = 100

  // 581 行顶与隋卡顶对齐
  rows[row581Idx].y = targetSuiTop

  applyCollapsedTimelineMarks(rows, expandedDynasties)

  return Math.abs(shiftAmount)
}

/** 收起态：581 刻度放在 581 行，不与 589 行混用 */
function applyCollapsedTimelineMarks(rows, expandedDynasties) {
  if (isNanbeiSuiExpanded(expandedDynasties)) return
  const row581 = rows.find(r => r.tS === 581)
  const row589 = rows.find(r => Math.abs(r.tS - 589) < 1)
  if (!row581) return

  row581.showYear = true
  row581.year = '581'
  row581.hxLabel = SUI_AXIS_KEY
  row581.dynastyKey = SUI_AXIS_KEY
  row581.expandable = true
  row581.expanded = false

  if (row589) {
    row589.showYear = false
    row589.hxLabel = ''
    row589.expandable = false
    row589.expanded = false
    row589.dynastyKey = ''
  }
}

/** 展开态：南北朝容器第二行子卡上移，避免与隋文帝重叠 */
function adjustNanbeiExpandedSubCards(subCards, subOverlays, blocks, expandedDynasties) {
  if (!isNanbeiSuiExpanded(expandedDynasties)) return 0
  if (!subCards || !subCards.length) return 0

  const wendi = blocks.find(b => b.entryId === SUI_WENDI_ENTRY && !isBridgeBlock(b))
  if (!wendi) return 0

  const row2Cards = subCards.filter(s =>
    s.containerId === NANBEI_CONTAINER_ID && /_r1_/.test(String(s.id || ''))
  )
  if (!row2Cards.length) return 0

  const GAP = BLOCK_V_GAP_RPX
  const row2Bottom = Math.max(...row2Cards.map(s => s.top + s.h))
  const overlap = row2Bottom + GAP - wendi.top
  if (overlap <= 0) return 0
  const lift = overlap

  row2Cards.forEach(card => {
    card.top -= lift
  })

  if (subOverlays && subOverlays.length) {
    const row2Ids = new Set(row2Cards.map(c => c.id))
    subOverlays.forEach(ov => {
      const cardId = String(ov.id || '').replace(/_chrome$/, '')
      if (!row2Ids.has(cardId) && !/_r1_/.test(String(ov.id || ''))) return
      if (ov.headerTop != null) ov.headerTop -= lift
      if (ov.barTop != null) ov.barTop -= lift
    })
  }

  return lift
}

module.exports = {
  NANBEI_AXIS_KEY,
  SUI_AXIS_KEY,
  NANBEI_LINKED_AXIS_KEYS,
  NANBEI_ENTRY,
  SUI_ENTRY,
  isNanbeiLinkedAxisKey,
  isNanbeiSuiExpanded,
  isNanbeiSuiCollapsed,
  isNanbeiContainerActive,
  applyNanbeiSuiLinkedExpansion,
  filterActiveForNanbeiSui,
  syncCollapsedNanbeiSuiTimeline,
  applyCollapsedTimelineMarks,
  adjustNanbeiExpandedSubCards,
}
