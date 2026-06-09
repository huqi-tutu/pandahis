import { Link, useNavigate, useParams } from 'react-router-dom'
import { BOXES, UNITS, getTopic } from '../data/content'

export function TopicDetailPage() {
  const nav = useNavigate()
  const { topicId } = useParams()
  const topic = topicId ? getTopic(topicId) : null

  if (!topic) {
    return (
      <div className="page page-pad">
        <div className="glass card">
          <div className="card-title">未找到专题</div>
          <div className="muted" style={{ marginBottom: 12 }}>
            topicId 无效或暂无数据。
          </div>
          <button className="btn btn-primary" onClick={() => nav('/topics')}>
            返回专题列表
          </button>
        </div>
      </div>
    )
  }

  const heroBoxes = topic.heroBoxIds.map((id) => BOXES.find((b) => b.id === id)).filter(Boolean)
  const heroUnits = topic.heroUnitIds.map((id) => UNITS.find((u) => u.id === id)).filter(Boolean)

  return (
    <div className="page page-pad">
      <div className="glass card" style={{ position: 'relative' }}>
        <div className="topic-hero-web">
          <div className="topic-hero-kicker-web">专题</div>
          <div className="topic-hero-title-web">{topic.title}</div>
          <div className="topic-hero-sub-web">{topic.subtitle}</div>
        </div>

        <div className="topic-section-web">
          <div className="topic-section-title-web">推荐史略盒子</div>
          <div className="topic-list-web">
            {heroBoxes.map((b) => (
              <Link key={b!.id} to={`/boxes/${b!.id}`} className="topic-item-web">
                <div className="topic-item-title-web">{b!.title}</div>
                <div className="topic-item-desc-web">{b!.detail.join('')}</div>
              </Link>
            ))}
          </div>
        </div>

        <div className="topic-section-web">
          <div className="topic-section-title-web">相关朝代入口</div>
          <div className="topic-unit-row-web">
            {heroUnits.map((u) => (
              <Link key={u!.id} to={`/units/${u!.id}`} className="topic-unit-pill-web">
                {u!.name}
              </Link>
            ))}
          </div>
        </div>

        <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>
          提示：专题来自 Excel 自动生成，可作为 SEO/投放落地页模板。
        </div>
      </div>
    </div>
  )
}

