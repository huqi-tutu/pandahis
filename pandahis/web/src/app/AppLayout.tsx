import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'

const PRD_PROTOTYPE_HREF = '../prd/v3-原型总览(1).html'

function Topbar() {
  const nav = useNavigate()
  const { pathname } = useLocation()

  const title =
    pathname.startsWith('/explore')
      ? '历史图谱'
      : pathname.startsWith('/topics')
        ? '专题'
        : pathname.startsWith('/search')
          ? '搜索'
          : pathname.startsWith('/member')
            ? '会员'
            : pathname.startsWith('/my')
              ? '我的'
              : pathname.startsWith('/login')
                ? '登录'
                : '历史图谱'

  const homeRoot = pathname === '/' || pathname === '/explore'

  return (
    <>
      {/* Desktop header */}
      <header className="desk-header">
        <div className="container desk-header-inner">
          <NavLink to="/" className="desk-brand">
            <span className="brand-dot" aria-hidden="true" />
            <span className="desk-brand-text">历史图谱</span>
          </NavLink>

          <nav className="desk-nav" aria-label="primary">
            <NavLink to="/explore" className={({ isActive }) => `desk-nav-link ${isActive ? 'active' : ''}`} end>
              首页
            </NavLink>
            <NavLink to="/search" className={({ isActive }) => `desk-nav-link ${isActive ? 'active' : ''}`}>
              搜索
            </NavLink>
            <NavLink to="/member" className={({ isActive }) => `desk-nav-link ${isActive ? 'active' : ''}`}>
              会员
            </NavLink>
            <NavLink to="/my" className={({ isActive }) => `desk-nav-link ${isActive ? 'active' : ''}`}>
              我的
            </NavLink>
          </nav>

          <div className="desk-actions">
            <NavLink to="/topics" className="desk-secondary-link">
              专题
            </NavLink>
            <a className="desk-cta" href={PRD_PROTOTYPE_HREF} target="_blank" rel="noreferrer">
              查看原型
            </a>
          </div>
        </div>
      </header>

      {/* Mobile topbar */}
      <header className="topbar mobile-only">
        <div className="container topbar-inner">
          <button
            className="topbar-btn"
            onClick={() => nav(-1)}
            aria-label="back"
            disabled={homeRoot}
            style={{ opacity: homeRoot ? 0.3 : 1 }}
          >
            ‹
          </button>

          <div className="topbar-title">{title}</div>

          <button className="topbar-btn" onClick={() => nav('/search')} aria-label="search">
            ⌕
          </button>
        </div>
      </header>
    </>
  )
}

function Tabbar() {
  return (
    <nav className="tabbar-web mobile-only" aria-label="tabs">
      <NavLink to="/explore" className={({ isActive }) => `tab-web ${isActive ? 'active' : ''}`} end>
        <span className="tab-web-ic">◈</span>
        <span className="tab-web-tx">首页</span>
      </NavLink>
      <NavLink to="/search" className={({ isActive }) => `tab-web ${isActive ? 'active' : ''}`}>
        <span className="tab-web-ic">⌕</span>
        <span className="tab-web-tx">搜索</span>
      </NavLink>
      <NavLink to="/member" className={({ isActive }) => `tab-web ${isActive ? 'active' : ''}`}>
        <span className="tab-web-ic">♛</span>
        <span className="tab-web-tx">会员</span>
      </NavLink>
      <NavLink to="/my" className={({ isActive }) => `tab-web ${isActive ? 'active' : ''}`}>
        <span className="tab-web-ic">◉</span>
        <span className="tab-web-tx">我的</span>
      </NavLink>
    </nav>
  )
}

export function AppLayout() {
  return (
    <div className="app-shell">
      <Topbar />
      <main className="app-main">
        <Outlet />
      </main>
      <Tabbar />
    </div>
  )
}
