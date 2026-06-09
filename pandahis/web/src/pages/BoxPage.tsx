import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { CATEGORY_LABELS, getBox, getUnit, yearLabel } from '../data/content'
import { animate, stagger } from 'animejs'
import { usePrefersReducedMotion } from '../ui/usePrefersReducedMotion'

type TabKey = 'detail' | 'graph' | 'critique' | 'relic'

export function BoxPage() {
  const nav = useNavigate()
  const { boxId } = useParams()
  const box = boxId ? getBox(boxId) : null
  const unit = box ? getUnit(box.unitId) : null
  const [tab, setTab] = useState<TabKey>('detail')
  const [graphVersion, setGraphVersion] = useState(0)
  const reducedMotion = usePrefersReducedMotion()
  const svgRef = useRef<SVGSVGElement | null>(null)

  const subText = useMemo(() => {
    if (!box || !unit) return ''
    const cat = CATEGORY_LABELS[box.categoryKey] ?? box.categoryKey
    return `${yearLabel(box.year)} · ${unit.crumbText.split(' · ')[0]} · ${cat}`
  }, [box, unit])

  const witnessRelics = useMemo(() => (box ? box.relics.slice(0, 3) : []), [box])

  if (!box || !unit) {
    return (
      <div className="page page-pad">
        <div className="glass card">
          <div className="card-title">未找到史略盒子</div>
          <div className="muted" style={{ marginBottom: 12 }}>
            boxId 无效或暂无数据。
          </div>
          <button className="btn btn-primary" onClick={() => nav('/explore')}>
            返回首页
          </button>
        </div>
      </div>
    )
  }

  useEffect(() => {
    if (reducedMotion) return
    if (tab !== 'graph') return
    const svg = svgRef.current
    if (!svg) return

    const edges = Array.from(svg.querySelectorAll<SVGLineElement>('.graph-edge-web'))
    const labels = Array.from(svg.querySelectorAll<SVGTextElement>('.graph-edge-label-web'))
    const groups = Array.from(svg.querySelectorAll<SVGGElement>('.graph-node-group-web'))

    // reset to initial state
    for (const l of edges) {
      const len = Math.hypot(Number(l.x2.baseVal.value) - Number(l.x1.baseVal.value), Number(l.y2.baseVal.value) - Number(l.y1.baseVal.value))
      l.style.strokeDasharray = String(len)
      l.style.strokeDashoffset = String(len)
      l.style.opacity = '1'
    }
    for (const t of labels) {
      t.style.opacity = '0'
      t.style.transform = 'translateY(-2px)'
      t.style.transformOrigin = 'center'
    }
    for (const g of groups) {
      g.style.opacity = '0'
      g.style.transform = 'translateY(8px) scale(0.98)'
      g.style.transformOrigin = 'center'
    }

    // animate (anime.js): draw edges -> pop nodes -> fade labels
    animate(edges as any, {
      // We manually set dasharray/dashoffset above; just animate to 0.
      strokeDashoffset: 0,
      duration: 700,
      delay: stagger(70),
      ease: 'inOutSine',
    } as any)

    animate(groups, {
      opacity: [0, 1],
      translateY: [8, 0],
      scale: [0.98, 1],
      duration: 520,
      delay: stagger(60, { start: 160 }),
      ease: 'outBack',
    })

    animate(labels, {
      opacity: [0, 1],
      translateY: [-2, 0],
      duration: 480,
      delay: stagger(80, { start: 240 }),
      ease: 'outQuad',
    })
  }, [graphVersion, reducedMotion, tab])

  return (
    <div className="page page-pad">
      <div className="glass card" style={{ position: 'relative', overflow: 'hidden' }}>
        <div className="box-hero-web">
          <div>
            <div className="box-title-web">{box.title}</div>
            <div className="box-sub-web">{subText}</div>
          </div>
          <button className="box-fav-web" aria-label="favorite">
            ♥
          </button>
        </div>

        <div className="box-tabs-web" role="tablist" aria-label="box tabs">
          <button className={`box-tab-web ${tab === 'detail' ? 'active' : ''}`} onClick={() => setTab('detail')}>
            详情
          </button>
          <button
            className={`box-tab-web ${tab === 'graph' ? 'active' : ''}`}
            onClick={() => {
              setTab('graph')
              setGraphVersion((v) => v + 1)
            }}
          >
            关系
          </button>
          <button className={`box-tab-web ${tab === 'critique' ? 'active' : ''}`} onClick={() => setTab('critique')}>
            评述
          </button>
          <button className={`box-tab-web ${tab === 'relic' ? 'active' : ''}`} onClick={() => setTab('relic')}>
            见证
          </button>
        </div>

        {tab === 'detail' ? (
          <div className="box-body-web">
            {box.detail.map((p, idx) => (
              <p key={idx} className="box-p-web">
                {p}
              </p>
            ))}
            <div className="box-original-btn-web">📜 查看 24 史原文对照</div>
          </div>
        ) : null}

        {tab === 'graph' ? (
          <div className="box-body-web">
            <div className="graph-wrap-web">
              <svg
                key={graphVersion}
                ref={svgRef}
                className="graph-svg-web graph-animate-web"
                viewBox="0 0 340 480"
                role="img"
                aria-label="graph"
              >
                {box.graph.edges.map((e, i) => {
                  const fromIdx = box.graph.nodes.findIndex((n) => n.key === e.from)
                  const toIdx = box.graph.nodes.findIndex((n) => n.key === e.to)
                  if (fromIdx < 0 || toIdx < 0) return null
                  const from = coords(fromIdx)
                  const to = coords(toIdx)
                  return (
                    <line
                      key={i}
                      className="graph-edge-web"
                      x1={from.x}
                      y1={from.y}
                      x2={to.x}
                      y2={to.y}
                      style={{ animationDelay: `${i * 70}ms` }}
                    />
                  )
                })}

                {box.graph.edges.map((e, i) => {
                  const fromIdx = box.graph.nodes.findIndex((n) => n.key === e.from)
                  const toIdx = box.graph.nodes.findIndex((n) => n.key === e.to)
                  if (fromIdx < 0 || toIdx < 0) return null
                  const from = coords(fromIdx)
                  const to = coords(toIdx)
                  return (
                    <text
                      key={i}
                      className="graph-edge-label-web"
                      x={(from.x + to.x) / 2}
                      y={(from.y + to.y) / 2 - 6}
                      style={{ animationDelay: `${(i + 1) * 90}ms` }}
                    >
                      {e.label}
                    </text>
                  )
                })}

                {box.graph.nodes.map((n, idx) => {
                  const c = coords(idx)
                  const isCenter = n.key === box.graph.center
                  const r = isCenter ? 36 : 28
                  return (
                    <g key={n.key} className="graph-node-group-web" style={{ animationDelay: `${160 + idx * 60}ms` }}>
                      <circle className={`graph-node-web ${isCenter ? 'center' : ''}`} cx={c.x} cy={c.y} r={r} />
                      <text className="graph-text-web" x={c.x} y={c.y + 4}>
                        {n.name.length > 4 ? `${n.name.slice(0, 4)}…` : n.name}
                      </text>
                      {n.badge ? (
                        <text className="graph-badge-web" x={c.x} y={c.y + 18}>
                          {n.badge}
                        </text>
                      ) : null}
                    </g>
                  )
                })}
              </svg>
            </div>
          </div>
        ) : null}

        {tab === 'critique' ? (
          <div className="box-body-web">
            <p className="muted" style={{ fontSize: 12, marginBottom: 12, letterSpacing: 0.4 }}>
              评述含「其他声音」；以下为示例条目（著作年排序可在接入真实数据后实现）。
            </p>
            <div className="critique-list-web">
              {box.critiques.map((c, idx) => (
                <div key={idx} className="critique-card-web">
                  <div className="critique-head-web">
                    <div className="critique-author-web">{c.author}</div>
                    <div className="critique-era-web">{c.eraText}</div>
                  </div>
                  <div className="critique-body-web">{c.content}</div>
                  <div className="critique-source-web">{c.source}</div>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        {tab === 'relic' ? (
          <div className="box-body-web">
            <div className="relics-list-web">
              {witnessRelics.map((r, idx) => (
                <div key={idx} className="relic-card-web">
                  <div className="relic-img-web">{r.name.slice(0, 3)}</div>
                  <div className="relic-info-web">
                    <div className="relic-name-web">{r.name}</div>
                    <div className="relic-desc-web">{r.description}</div>
                    <div className="relic-museum-web">◎ {r.museum}</div>
                  </div>
                </div>
              ))}
            </div>
            {box.relics.length === 0 ? (
              <p className="muted" style={{ fontSize: 13, marginTop: 8 }}>
                暂无见证条目（PRD：最多展示 3 件文物）。
              </p>
            ) : null}
          </div>
        ) : null}

        <div style={{ height: 10 }} />
        <div className="muted" style={{ fontSize: 12, letterSpacing: 0.6, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <span>
            所属朝代：<Link to={`/units/${unit.id}`}>{unit.dynastyName || unit.name}</Link>
          </span>
          <span>史略层：详情 · 关系 · 评述 · 见证</span>
        </div>
      </div>
    </div>
  )
}

function coords(idx: number) {
  // fixed radial slots similar to prototype
  const center = { x: 170, y: 240 }
  if (idx === 0) return center
  const angles = [-90, -55, -20, 15, 50, 85, 120, 155, 190, 225, 260]
  const a = (angles[(idx - 1) % angles.length]! * Math.PI) / 180
  const r = 150
  return { x: center.x + Math.cos(a) * r, y: center.y + Math.sin(a) * r }
}

