import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { CIVILIZATIONS, TIME_AXIS, UNITS, yearLabel } from '../data/content'

type HomeMode = 'overview' | 'immersive'

function civColorVar(civId: string) {
  return CIVILIZATIONS.find((c) => c.id === civId)?.colorVar ?? '--c-huaxia'
}

export function ExplorePage() {
  const [mode, setMode] = useState<HomeMode>('immersive')
  const [activeCivId, setActiveCivId] = useState(CIVILIZATIONS[0]?.id ?? '')

  const unitsByYear = useMemo(() => {
    const map = new Map<number, typeof UNITS>()
    for (const row of TIME_AXIS) map.set(row.year, [])
    for (const u of UNITS) {
      let best = TIME_AXIS[0]!
      let bestDist = Math.abs(u.startYear - best.year)
      for (const r of TIME_AXIS) {
        const d = Math.abs(u.startYear - r.year)
        if (d < bestDist) {
          best = r
          bestDist = d
        }
      }
      const list = map.get(best.year) ?? []
      list.push(u)
      map.set(best.year, list)
    }
    return map
  }, [])

  const displayCivs = mode === 'overview' ? CIVILIZATIONS : CIVILIZATIONS.filter((c) => c.id === activeCivId)
  const colCount = Math.max(1, displayCivs.length)
  const colTpl = `repeat(${colCount}, minmax(${mode === 'overview' ? 58 : 1}fr, 1fr))`

  return (
    <div className="page page-pad">
      <div className="glass card" style={{ position: 'relative' }}>
        <div className="explore-hd-web">
          <div className="card-title" style={{ marginBottom: 0 }}>
            图谱层 · 时空矩阵
          </div>
          <div className="explore-mode-bar" role="group" aria-label="首页模式">
            <button
              type="button"
              className={`explore-mode-btn ${mode === 'overview' ? 'active' : ''}`}
              onClick={() => setMode('overview')}
            >
              总览
            </button>
            <button
              type="button"
              className={`explore-mode-btn ${mode === 'immersive' ? 'active' : ''}`}
              onClick={() => setMode('immersive')}
            >
              沉浸
            </button>
          </div>
        </div>

        <div className="mini-search" style={{ margin: '12px 0' }}>
          ⌕ 搜索朝代、人物、事件…
          <Link to="/search" style={{ marginLeft: 'auto', color: 'var(--accent)' }}>
            去搜索 →
          </Link>
        </div>

        {mode === 'immersive' ? (
          <div className="unit-civ-tabs-web" role="tablist" aria-label="地域">
            {CIVILIZATIONS.map((c) => (
              <button
                key={c.id}
                className={`civ-tab-web ${activeCivId === c.id ? 'active' : ''}`}
                onClick={() => setActiveCivId(c.id)}
                style={
                  activeCivId === c.id
                    ? { borderColor: `color-mix(in oklab, var(${c.colorVar}) 55%, rgba(255,255,255,0.08))` }
                    : undefined
                }
              >
                {c.name}
              </button>
            ))}
            <div className="civ-tab-fade" aria-hidden="true" />
          </div>
        ) : (
          <p className="explore-overview-hint muted" style={{ fontSize: 12, marginBottom: 12, letterSpacing: 0.5 }}>
            总览模式：14 地域 × 时间轴；横滑查看完整矩阵。色块为粗略朝代/帝王单元入口。
          </p>
        )}

        <div className={mode === 'overview' ? 'explore-matrix-scroll' : undefined}>
          <div
            className={`grid-web ${mode === 'overview' ? 'grid-web-overview' : ''}`}
            style={mode === 'overview' ? { minWidth: `calc(68px + ${colCount} * 72px)` } : undefined}
          >
            <div className="grid-time">
              <div className="grid-time-hd">时间</div>
              {TIME_AXIS.map((row) => (
                <div key={row.year} className="grid-time-cell" style={{ height: row.rowHeightPx }}>
                  <span className="grid-year">{row.label}</span>
                </div>
              ))}
            </div>

            <div className="grid-civs">
              <div className="grid-civ-hd" style={{ gridTemplateColumns: colTpl }}>
                {displayCivs.map((c) => (
                  <div
                    key={c.id}
                    className="grid-civ-hd-cell"
                    style={{ color: `color-mix(in oklab, var(${c.colorVar}) 62%, #fff 10%)` }}
                  >
                    {c.name}
                  </div>
                ))}
              </div>

              <div className="grid-body">
                {TIME_AXIS.map((row) => (
                  <div key={row.year} className="grid-row" style={{ gridTemplateColumns: colTpl, height: row.rowHeightPx }}>
                    {displayCivs.map((civ) => {
                      const units = unitsByYear.get(row.year) ?? []
                      const candidates = units.filter((u) => u.civilizationId === civ.id)
                      const match = candidates[0] ?? null
                      return (
                        <div key={`${row.year}:${civ.id}`} className="grid-cell">
                          {match ? (
                            <Link
                              to={`/units/${match.id}`}
                              className={`grid-card ${mode === 'overview' ? 'grid-card-compact' : ''}`}
                              style={{
                                background: `color-mix(in oklab, var(${civColorVar(match.civilizationId)}) 16%, rgba(255,255,255,0.02))`,
                              }}
                            >
                              <div className="grid-card-title">{match.name}</div>
                              <div className="grid-card-sub">
                                {yearLabel(match.startYear)} — {yearLabel(match.endYear)}
                              </div>
                              {candidates.length > 1 ? (
                                <div className="grid-card-sub" style={{ marginTop: 2, color: 'rgba(200,200,215,0.42)' }}>
                                  +{candidates.length - 1} 更多
                                </div>
                              ) : null}
                            </Link>
                          ) : (
                            <div className="grid-empty" />
                          )}
                        </div>
                      )
                    })}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div style={{ height: 10 }} />
        <div className="muted" style={{ fontSize: 12, letterSpacing: 0.6 }}>
          沉浸模式下单地域 Tab 展示细粒度帝王分布；点击单元格进入<strong> 朝代详情（王朝层）</strong>，再在格中打开
          <strong> 史略盒子</strong>。
        </div>
      </div>
    </div>
  )
}
