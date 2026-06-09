import { useNavigate } from 'react-router-dom'

export function LoginPage() {
  const nav = useNavigate()
  return (
    <div className="page page-pad">
      <div className="glass card login-wrap-web" style={{ position: 'relative' }}>
        <div className="login-logo-web">图谱</div>
        <div className="login-slogan-web">重构全球历史 · 脉络清晰</div>

        <div className="login-form-web">
          <div className="login-input-web">
            <span className="login-input-label-web">+86</span>
            <span className="login-input-sep-web" />
            <span className="login-input-val-web">138 1234 5678</span>
          </div>
          <div className="login-input-web">
            <span className="login-input-ph-web">请输入验证码</span>
            <span className="login-code-btn-web">获取验证码</span>
          </div>
        </div>

        <button className="login-submit-web" onClick={() => nav('/my')}>
          登 录
        </button>

        <div className="login-sep-web">
          <div className="login-sep-line-web" />
          <div className="login-sep-text-web">其他方式</div>
          <div className="login-sep-line-web" />
        </div>

        <div className="login-wechat-web" role="button" tabIndex={0} onClick={() => nav('/my')}>
          ♫
        </div>

        <div className="login-agreement-web">
          登录即代表同意 <a>用户协议</a> 与 <a>隐私政策</a>
        </div>
      </div>
    </div>
  )
}

