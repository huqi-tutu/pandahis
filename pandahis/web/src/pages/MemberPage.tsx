import { useNavigate } from 'react-router-dom'

export function MemberPage() {
  const nav = useNavigate()
  return (
    <div className="page page-pad">
      <div className="vip-banner-web">
        <div className="vip-tag-web">图谱会员</div>
        <div className="vip-title-web">历史无界</div>
        <div className="vip-sub-web">HISTORICAL · UNLIMITED · ACCESS</div>
      </div>

      <div className="glass card" style={{ marginTop: 12 }}>
        <div className="vip-status-web">
          <div className="vip-status-name-web">雄哥</div>
          <div className="vip-status-expired-web">未开通 · 请选择套餐</div>
        </div>

        <div className="vip-plans-web">
          <div className="vip-plan-web">
            <div className="vip-plan-name-web">月度</div>
            <div className="vip-plan-price-web">
              <span className="currency">¥</span>9.9
            </div>
            <div className="vip-plan-unit-web">/ 月</div>
          </div>
          <div className="vip-plan-web">
            <div className="vip-plan-name-web">季度</div>
            <div className="vip-plan-price-web">
              <span className="currency">¥</span>19.9
            </div>
            <div className="vip-plan-unit-web">/ 季</div>
          </div>
          <div className="vip-plan-web selected">
            <div className="vip-plan-tag-web">最划算</div>
            <div className="vip-plan-name-web">年度</div>
            <div className="vip-plan-price-web">
              <span className="currency">¥</span>49.9
            </div>
            <div className="vip-plan-unit-web">/ 年</div>
          </div>
        </div>

        <div className="vip-benefits-web">
          <div className="vip-benefit-web">
            <span className="vip-benefit-icon-web">✦</span>
            <span className="vip-benefit-text-web">解锁全部 14 地域详细图谱</span>
          </div>
          <div className="vip-benefit-web">
            <span className="vip-benefit-icon-web">✦</span>
            <span className="vip-benefit-text-web">跨时空评述 · 多视角对照</span>
          </div>
          <div className="vip-benefit-web">
            <span className="vip-benefit-icon-web">✦</span>
            <span className="vip-benefit-text-web">见证 · 博物馆数字藏品（最多 3 件展示）</span>
          </div>
          <div className="vip-benefit-web">
            <span className="vip-benefit-icon-web">✦</span>
            <span className="vip-benefit-text-web">24 史原文对照 · 无广告</span>
          </div>
        </div>

        <button className="vip-buy-web" onClick={() => nav('/login')}>
          立即购买
        </button>
        <div className="muted" style={{ fontSize: 12, marginTop: 10 }}>
          v1 建议：Web 端展示与引导，支付在小程序完成（强一致）。
        </div>
      </div>
    </div>
  )
}

