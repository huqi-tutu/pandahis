import { Link, useNavigate, useParams } from 'react-router-dom'
import { getUnit, listBoxesByUnit, listRelatedCrossCivUnits, nextDynastyUnit, yearLabel } from '../data/content'
import type { CategoryKey } from '../data/models'

/** PRD：君纪 → 士臣 → 典制 → 事略 → 民录 */
const CATS: { key: CategoryKey; name: string }[] = [
  { key: 'junji', name: '君纪' },
  { key: 'shichen', name: '士臣' },
  { key: 'dianzhi', name: '典制' },
  { key: 'shilue', name: '事略' },
  { key: 'minlu', name: '民录' },
]

export function UnitPage() {
  const nav = useNavigate()
  const { unitId } = useParams()

  const unit = unitId ? getUnit(unitId) : null
  const boxes = unit ? listBoxesByUnit(unit.id) : []

  const years = Array.from(new Set(boxes.map((b) => b.year))).sort((a, b) => a - b)
  const cell = (y: number, k: CategoryKey) =>
    boxes
      .filter((b) => b.year === y && b.categoryKey === k)
      .sort((a, b) => b.importanceLevel - a.importanceLevel || a.id.localeCompare(b.id))[0] ?? null

  const related = unit ? listRelatedCrossCivUnits(unit) : []
  const nextU = unit ? nextDynastyUnit(unit) : null

  const dynastyTitle = unit?.dynastyName?.trim() || unit?.crumbText.split(' · ')[1] || unit?.name || ''

  if (!unit) {
    return (
      <div className="page page-pad">
        <div className="glass card">
          <div className="card-title">未找到朝代详情</div>
          <div className="muted" style={{ marginBottom: 12 }}>
            unitId 无效或暂无数据。
          </div>
          <button className="btn btn-primary" onClick={() => nav('/explore')}>
            返回首页
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="page page-pad">
      <div className="glass card" style={{ position: 'relative' }}>
        {related.length > 0 ? (
          <div className="unit-related-block-web">
            <div className="unit-related-label-web">年份相近的其他地域</div>
            <div className="unit-related-strip-web">
              {related.map((u) => (
                <Link key={u.id} to={`/units/${u.id}`} className="unit-related-chip-web">
                  <span className="unit-related-name-web">{u.dynastyName || u.name}</span>
                  <span className="unit-related-meta-web">{yearLabel(u.startYear)}</span>
                </Link>
              ))}
            </div>
          </div>
        ) : null}

        <div className="unit-hero-web">
          <div className="unit-crumb-web">{unit.crumbText}</div>
          <div className="unit-dynasty-web">{dynastyTitle}</div>
          <div className="unit-title-web">{unit.name}</div>
          {unit.eraText ? <div className="unit-sub-web">{unit.eraText}</div> : null}
          <div className="unit-meta-web">
            <span>
              在位 <b>{unit.durationYears} 年</b>
            </span>
            <span>
              {yearLabel(unit.startYear)} — {yearLabel(unit.endYear)}
            </span>
          </div>
        </div>

        <div className="unit-intro-web">
          <div className="unit-intro-label-web">朝代简介</div>
          <div className="unit-intro-text-web">{unit.summary}</div>
        </div>

        <div className="unit-matrix-web">
          <div className="unit-matrix-hd-web">
            <div className="unit-matrix-hd-time-web" />
            <div className="unit-matrix-hd-cats-web">
              {CATS.map((c) => (
                <div key={c.key} className="unit-cat-web">
                  {c.name}
                  <span className="unit-cat-tip-web">!</span>
                </div>
              ))}
            </div>
          </div>

          <div className="unit-matrix-body-web">
            {years.map((y) => (
              <div key={y} className="unit-year-row-web">
                <div className="unit-year-label-web">
                  <span className="unit-year-tick-web" />
                  {y}
                  <span className="unit-year-tick-web" />
                </div>
                <div className="unit-cells-web">
                  {CATS.map((c) => {
                    const b = cell(y, c.key)
                    if (!b) return <div key={c.key} className="unit-cell-web unit-cell-empty-web" />
                    const hl = b.importanceLevel >= 4
                    return (
                      <Link key={c.key} to={`/boxes/${b.id}`} className={`unit-cell-web ${hl ? 'unit-cell-hl-web' : ''}`}>
                        {b.title}
                      </Link>
                    )
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>

        {nextU ? (
          <div className="unit-next-web">
            <span className="unit-next-label-web">下一朝代</span>
            <Link to={`/units/${nextU.id}`} className="unit-next-link-web">
              {nextU.dynastyName || nextU.name}
              <span className="unit-next-meta-web">{yearLabel(nextU.startYear)} 起</span>
            </Link>
          </div>
        ) : null}

        <div style={{ height: 10 }} />
        <div className="muted" style={{ fontSize: 12, letterSpacing: 0.6 }}>
          王朝层：时间 × 史略五类。点击格子进入<strong>史略盒子</strong>详情（详情 · 关系 · 评述 · 见证）。
        </div>
      </div>
    </div>
  )
}
