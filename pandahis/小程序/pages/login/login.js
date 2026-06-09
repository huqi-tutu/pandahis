Page({
  data: {
    phone: '',
    code: '',
    countdown: 0
  },

  onGetUserInfo(e) {
    if (e.detail.errMsg === 'getUserInfo:ok') {
      wx.showToast({ title: '登录成功', icon: 'success', duration: 1000 })
      setTimeout(() => {
        wx.switchTab({ url: '/pages/home-matrix/home-matrix' })
      }, 1000)
    }
  },

  onPhoneInput(e) {
    this.setData({ phone: e.detail.value })
  },

  onCodeInput(e) {
    this.setData({ code: e.detail.value })
  },

  sendCode() {
    if (this.data.countdown > 0) return
    const phone = this.data.phone
    if (!phone || phone.length !== 11) {
      wx.showToast({ title: '请输入正确的手机号', icon: 'none' })
      return
    }
    this.setData({ countdown: 60 })
    wx.showToast({ title: '验证码已发送', icon: 'success', duration: 1500 })

    const timer = setInterval(() => {
      const c = this.data.countdown - 1
      this.setData({ countdown: c })
      if (c <= 0) clearInterval(timer)
    }, 1000)
  },

  loginByPhone() {
    const { phone, code } = this.data
    if (!phone || phone.length !== 11) {
      wx.showToast({ title: '请输入手机号', icon: 'none' })
      return
    }
    if (!code || code.length < 4) {
      wx.showToast({ title: '请输入验证码', icon: 'none' })
      return
    }
    wx.showLoading({ title: '登录中…' })
    setTimeout(() => {
      wx.hideLoading()
      wx.showToast({ title: '登录成功', icon: 'success' })
      setTimeout(() => {
        wx.switchTab({ url: '/pages/home-matrix/home-matrix' })
      }, 800)
    }, 1200)
  },

  guestBrowse() {
    wx.switchTab({ url: '/pages/home-matrix/home-matrix' })
  },

  openAgreement() {
    wx.showToast({ title: '用户协议', icon: 'none' })
  },

  openPrivacy() {
    wx.showToast({ title: '隐私政策', icon: 'none' })
  }
})
