function fmtYear(y) {
  if (y < 0) return `前${Math.abs(y)}`
  return String(y)
}

function mapBars(lanes) {
  return (lanes || []).map(lane => ({
    ...lane,
    collapsedRows: (lane.collapsedRows || []).map(row =>
      (row || []).map(bar => ({
        ...bar,
        boxKey: bar.boxId || bar.boxKey || '',
        boxTitle: bar.boxTitle || bar.title || '',
      }))
    ),
  }))
}

/** 后端 UnitHero + SwimMatrix → 页面 dynasty 结构 */
function mapHeroSwimToDynasty(hero, swim) {
  const unit = hero.unit || {}
  const parts = String(unit.crumbText || '').split('·').map(s => s.trim())
  const civ = parts[0] || ''
  const startYear = swim.startYear != null ? swim.startYear : unit.startYear
  const endYear = swim.endYear != null ? swim.endYear : unit.endYear
  const next = hero.nextUnit
    ? { title: hero.nextUnit.title || '', dynasty: hero.nextUnit.unitId || '' }
    : { title: '', dynasty: '' }

  return {
    title: unit.name || unit.dynastyName || '',
    civ,
    range: `${fmtYear(startYear)}–${fmtYear(endYear)}`,
    startYear,
    endYear,
    intro: String(unit.summary || '').trim() || '空',
    ticks: swim.ticks || [],
    endLabel: swim.endLabel || fmtYear(endYear),
    lanes: mapBars(swim.lanes),
    concurrentItems: swim.concurrentItems || [],
    next,
  }
}

module.exports = { mapHeroSwimToDynasty }
