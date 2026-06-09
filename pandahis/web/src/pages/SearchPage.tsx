import { useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { SEARCH_SUGGEST, searchAll } from '../data/content'

export function SearchPage() {
  const nav = useNavigate()
  const [params, setParams] = useSearchParams()
  const [q, setQ] = useState(() => params.get('q') ?? '')

  const results = useMemo(() => searchAll(q), [q])

  const showResults = q.trim().length > 0

  return (
    <div className="page page-pad">
      <div className="glass card" style={{ position: 'relative' }}>
        <div className="searchbar-web">
          <button className="topbar-btn" onClick={() => nav(-1)} aria-label="back">
            ‹
          </button>
          <div className="search-input-web">
            <span style={{ opacity: 0.65 }}>⌕</span>
            <input
              value={q}
              onChange={(e) => {
                const v = e.target.value
                setQ(v)
                setParams((p) => {
                  if (!v.trim()) p.delete('q')
                  else p.set('q', v)
                  return p
                })
              }}
              placeholder="年代 / 人物 / 事件"
            />
          </div>
          <button className="topbar-btn" onClick={() => setQ('')} aria-label="clear">
            ✕
          </button>
        </div>

        {!showResults ? (
          <>
            <div className="search-sec-web">
              <div className="search-sec-title-web">热门搜索</div>
              <div className="search-tags-web">
                {SEARCH_SUGGEST.hot.map((h) => (
                  <button
                    key={h.keyword}
                    className={`search-tag-web ${h.hot ? 'hot' : ''}`}
                    onClick={() => {
                      setQ(h.keyword)
                      setParams((p) => (p.set('q', h.keyword), p))
                    }}
                  >
                    {h.keyword}
                  </button>
                ))}
              </div>
            </div>

            <div className="search-sec-web">
              <div className="search-sec-title-web">历史记录</div>
              <div className="search-history-web">
                {SEARCH_SUGGEST.history.map((k) => (
                  <div key={k} className="search-history-item-web">
                    <button
                      className="search-history-key-web"
                      onClick={() => {
                        setQ(k)
                        setParams((p) => (p.set('q', k), p))
                      }}
                    >
                      {k}
                    </button>
                    <span className="x">✕</span>
                  </div>
                ))}
              </div>
              <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>
                说明：当前为 demo 静态数据（未接入账号系统）。
              </div>
            </div>
          </>
        ) : (
          <>
            <div className="result-count-web">找到 {results.length} 条相关内容</div>
            <div className="result-cards-web">
              {results.map((r) => {
                const to = r.type === 'box' ? `/boxes/${r.id}` : `/units/${r.id}`
                return (
                  <Link key={`${r.type}:${r.id}`} to={to} className="result-card-web">
                    <div className="result-card-path-web">{r.pathText}</div>
                    <div className="result-card-title-web">{r.title}</div>
                    <div className="result-card-desc-web">{r.desc}</div>
                  </Link>
                )
              })}
              {results.length === 0 ? <div className="muted">暂未找到内容</div> : null}
            </div>
          </>
        )}
      </div>
    </div>
  )
}

