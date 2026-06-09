import { Link, useNavigate } from 'react-router-dom'

export function MyPage() {
  const nav = useNavigate()
  return (
    <div className="page page-pad">
      <div className="glass card">
        <div className="mine-hero-web">
          <div className="avatar-web">雄</div>
          <div className="mine-info-web">
            <div className="mine-name-web">雄哥</div>
            <div className="mine-phone-web">138 **** 8888</div>
          </div>
          <button className="topbar-btn" aria-label="edit">
            ✎
          </button>
        </div>

        <div className="mine-vip-web" onClick={() => nav('/member')} role="button" tabIndex={0}>
          <div className="mine-vip-icon-web">♛</div>
          <div className="mine-vip-main-web">
            <div className="mine-vip-title-web">开通年度会员</div>
            <div className="mine-vip-sub-web">解锁完整图谱层 · 跨时空评述 · 史略见证</div>
          </div>
          <div className="mine-vip-arrow-web">›</div>
        </div>

        <div className="mine-list-web">
          <Link to="/topics" className="mine-item-web mine-item-link-web">
            <div className="mine-item-icon-web">✦</div>
            <div className="mine-item-label-web">专题</div>
            <div className="mine-item-value-web">扩展阅读</div>
            <div className="mine-item-arrow-web">›</div>
          </Link>
          <div className="mine-item-web" onClick={() => nav('/login')} role="button" tabIndex={0}>
            <div className="mine-item-icon-web">⧗</div>
            <div className="mine-item-label-web">我的足迹</div>
            <div className="mine-item-value-web">127 条</div>
            <div className="mine-item-arrow-web">›</div>
          </div>
          <div className="mine-item-web" onClick={() => nav('/login')} role="button" tabIndex={0}>
            <div className="mine-item-icon-web">♡</div>
            <div className="mine-item-label-web">我的收藏</div>
            <div className="mine-item-value-web">23 条</div>
            <div className="mine-item-arrow-web">›</div>
            </div>
          <div className="mine-item-web">
            <div className="mine-item-icon-web">⚙</div>
            <div className="mine-item-label-web">设置</div>
            <div className="mine-item-value-web" />
            <div className="mine-item-arrow-web">›</div>
          </div>
          <div className="mine-item-web">
            <div className="mine-item-icon-web">?</div>
            <div className="mine-item-label-web">帮助与反馈</div>
            <div className="mine-item-value-web" />
            <div className="mine-item-arrow-web">›</div>
          </div>
          <div className="mine-item-web">
            <div className="mine-item-icon-web">ⓘ</div>
            <div className="mine-item-label-web">关于我们</div>
            <div className="mine-item-value-web">v1.0.0</div>
            <div className="mine-item-arrow-web">›</div>
          </div>
        </div>

        <div className="mine-logout-web" onClick={() => nav('/login')} role="button" tabIndex={0}>
          退出登录
        </div>
      </div>
    </div>
  )
}

