import { Link } from 'react-router-dom'
import { TOPICS } from '../data/content'

export function TopicsPage() {
  return (
    <div className="page page-pad">
      <div className="glass card" style={{ position: 'relative' }}>
        <div className="card-title">专题</div>
        <div className="muted" style={{ fontSize: 13, lineHeight: 1.7, marginBottom: 12 }}>
          从关键词出发，把内容组织成可分享的落地页。当前专题由 Excel 内容自动生成。
        </div>

        <div className="topic-grid-web">
          {TOPICS.map((t) => (
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

        {TOPICS.length === 0 ? <div className="muted">暂无专题（数据不足以生成）。</div> : null}
      </div>
    </div>
  )
}

