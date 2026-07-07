const { DYNASTY_DB, buildSwimData } = require('../../native-utils/matrix/mock-dynasty.js')

const SWIM_SHEET_RPX = 1440

function normalizeDynastyKey(name) {
  const raw = String(name || '').trim()
  if (!raw) return ''
  if (DYNASTY_DB[raw]) return raw
  const noChao = raw.replace(/朝$/, '')
  if (DYNASTY_DB[noChao]) return noChao
  if (raw.includes('北宋') || raw === '宋' || raw.includes('南宋')) return '北宋'
  for (const key of Object.keys(DYNASTY_DB)) {
    if (raw.includes(key) || key.includes(raw)) return key
  }
  return raw
}

function buildSwimMatrixFromMock(dynastyName) {
  const key = normalizeDynastyKey(dynastyName)
  const raw = buildSwimData(key)
  return {
    startYear: raw.startYear,
    endYear: raw.endYear,
    endLabel: raw.endLabel,
    ticks: raw.ticks,
    lanes: raw.lanes,
    concurrentItems: raw.concurrentItems || [],
    sheetWidthRpx: SWIM_SHEET_RPX,
    _mock: raw,
  }
}

function buildHeroFromMock(swimMatrix, unitId, dynastyName) {
  const d = swimMatrix._mock || {}
  const title = d.title || dynastyName || '朝代'
  const id = String(unitId || title).trim()
  const next = d.next
    ? {
        unitId: d.next.dynasty || d.next.title || '',
        title: String(d.next.title || '').split(' · ')[0] || d.next.dynasty || '',
        startYear: d.endYear,
      }
    : null
  return {
    unit: {
      id,
      name: title,
      dynastyName: title,
      crumbText: d.civ || '',
      eraText: d.range || `${d.startYear}–${d.endYear}`,
      startYear: d.startYear,
      endYear: d.endYear,
      durationYears: Math.max(0, d.endYear - d.startYear),
      summary: d.intro || '',
    },
    relatedUnits: [],
    nextUnit: next,
  }
}

function collectMatrixBoxIds(swim) {
  const ids = []
  for (const lane of swim.lanes || []) {
    for (const row of lane.collapsedRows || []) {
      for (const bar of row) {
        if (bar && bar.boxId) ids.push(bar.boxId)
      }
    }
  }
  return ids
}

module.exports = {
  SWIM_SHEET_RPX,
  normalizeDynastyKey,
  buildSwimMatrixFromMock,
  buildHeroFromMock,
  collectMatrixBoxIds,
}
