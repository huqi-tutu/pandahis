import { useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { animate, stagger } from 'animejs'
import { TOPICS } from '../data/content'
import { useReveal } from '../ui/useReveal'
import { usePrefersReducedMotion } from '../ui/usePrefersReducedMotion'

export function LandingPage() {
  const featured = TOPICS.slice(0, 6)
  const hero = useReveal()
  const topics = useReveal()
  const bottom = useReveal()
  const reducedMotion = usePrefersReducedMotion()
  const heroRef = useRef<HTMLElement | null>(null)

  useEffect(() => {
    if (reducedMotion) return
    const root = heroRef.current
    if (!root) return

    const els = root.querySelectorAll<HTMLElement>('.landing-kicker, .landing-h1, .landing-lead, .landing-actions > *')
    animate(els, {
      opacity: [0, 1],
      translateY: [10, 0],
      filter: ['blur(6px)', 'blur(0px)'],
      duration: 720,
      delay: stagger(70),
      ease: 'outExpo',
    })
  }, [reducedMotion])

  return (
    <div className="page landing-web">
      <section ref={heroRef} className="landing-hero" {...hero.dataAttrs}>
        <div className="landing-hero-grid">
          <div className="landing-copy">
            <div className="landing-kicker">把历史变成可浏览的结构</div>
            <h1 className="landing-h1">
              在一张图上
              <br />
              找到你要的时代与人物
            </h1>
            <p className="landing-lead">
              从图谱层「时空矩阵」进入王朝层与史略层：总览与沉浸两种首页模式，再沿关系与专题扩展阅读。先定位，再漫游。
            </p>

            <div className="landing-actions">
              <Link className="landing-cta" to="/explore">
                开始探索
              </Link>
              <Link className="landing-ghost" to="/topics">
                逛专题
              </Link>
              <a className="landing-ghost" href="../prd/v3-原型总览(1).html" target="_blank" rel="noreferrer">
                看原型
              </a>
            </div>
          </div>

          <div className="landing-demo glass">
            <div className="landing-demo-hd">
              <div className="landing-demo-title">关系图 · 动效预览</div>
              <div className="landing-demo-sub">连线绘制 / 节点弹出 / hover 高亮</div>
            </div>

            <div className="landing-demo-body">
              <svg className="graph-svg-web graph-animate-web" viewBox="0 0 340 320" role="img" aria-label="demo graph">
                {[
                  { x1: 170, y1: 160, x2: 70, y2: 70, d: 0 },
                  { x1: 170, y1: 160, x2: 270, y2: 70, d: 70 },
                  { x1: 170, y1: 160, x2: 60, y2: 200, d: 140 },
                  { x1: 170, y1: 160, x2: 280, y2: 210, d: 210 },
                ].map((l, i) => (
                  <line key={i} className="graph-edge-web" x1={l.x1} y1={l.y1} x2={l.x2} y2={l.y2} style={{ animationDelay: `${l.d}ms` }} />
                ))}

                {[
                  { x: 170, y: 160, r: 34, text: '乌台诗案', center: true, delay: 220 },
                  { x: 70, y: 70, r: 26, text: '苏轼', delay: 280 },
                  { x: 270, y: 70, r: 26, text: '御史台', delay: 340 },
                  { x: 60, y: 200, r: 24, text: '黄州', delay: 400 },
                  { x: 280, y: 210, r: 26, text: '寒食帖', delay: 460 },
                ].map((n, i) => (
                  <g key={i} className="graph-node-group-web" style={{ animationDelay: `${n.delay}ms` }}>
                    <circle className={`graph-node-web ${n.center ? 'center' : ''}`} cx={n.x} cy={n.y} r={n.r} />
                    <text className="graph-text-web" x={n.x} y={n.y + 4}>
                      {n.text.length > 4 ? `${n.text.slice(0, 4)}…` : n.text}
                    </text>
                  </g>
                ))}
              </svg>
            </div>
          </div>
        </div>
      </section>

      <section className="landing-section" {...topics.dataAttrs}>
        <div className="landing-sec-hd">
          <h2>精选专题</h2>
          <Link to="/topics" className="landing-more">
            查看全部 →
          </Link>
        </div>
        <div className="topic-grid-web">
          {featured.map((t) => (
            <Link
              key={t.id}
              to={`/topics/${t.id}`}
              className="topic-card-web"
              onMouseMove={(e) => {
                const el = e.currentTarget
                const r = el.getBoundingClientRect()
                const x = ((e.clientX - r.left) / r.width) * 100
                const y = ((e.clientY - r.top) / r.height) * 100
                el.style.setProperty('--mx', `${x}%`)
                el.style.setProperty('--my', `${y}%`)
              }}
            >
              <div className="topic-title-web">{t.title}</div>
              <div className="topic-sub-web">{t.subtitle}</div>
              <div className="topic-meta-web">
                <span>史略盒子 {t.heroBoxIds.length}+</span>
                <span>·</span>
                <span>朝代入口 {t.heroUnitIds.length}+</span>
              </div>
            </Link>
          ))}
        </div>
      </section>

      <section className="landing-section landing-bottom" {...bottom.dataAttrs}>
        <div className="landing-bottom-card glass">
          <div>
            <div className="landing-bottom-title">把它发给朋友</div>
            <div className="landing-bottom-sub">一个专题页就是一张“可分享的阅读路径”。</div>
          </div>
          <Link className="landing-cta" to="/topics">
            去挑一个专题
          </Link>
        </div>
      </section>
    </div>
  )
}

