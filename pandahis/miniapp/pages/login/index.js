"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const api_1 = require("../../native-utils/api");
const invite_storage_1 = require("../../native-utils/invite-storage");
const wx_auth_1 = require("../../native-utils/wx-auth");
const router_1 = require("../../native-utils/router");
Page({
    data: {
        loggingIn: false,
        pendingInvite: '',
        inviteCodeInput: '',
        hasToken: false,
        reauth: false,
        phone: '',
        code: '',
        countdown: 0,
    },
    _countdownTimer: null,
    onLoad(query) {
        const reauth = query.reauth === '1' || query.reauth === 'true';
        if (reauth) {
            (0, api_1.clearToken)();
        }
        this.setData({ reauth });
    },
    onUnload() {
        if (this._countdownTimer)
            clearInterval(this._countdownTimer);
    },
    onInviteCodeInput(e) {
        const v = (e.detail.value || '').trim().toUpperCase();
        this.setData({ inviteCodeInput: v });
        if (v)
            (0, invite_storage_1.stashInviteCode)(v);
    },
    onPhoneInput(e) {
        this.setData({ phone: (e.detail.value || '').trim() });
    },
    onCodeInput(e) {
        this.setData({ code: (e.detail.value || '').trim() });
    },
    onShow() {
        const pendingInvite = (0, invite_storage_1.peekPendingInviteCode)();
        this.setData({
            pendingInvite,
            inviteCodeInput: pendingInvite || '',
            hasToken: (0, api_1.hasToken)(),
        });
        if ((0, api_1.hasToken)()) {
            (0, wx_auth_1.leaveAfterLogin)(0);
        }
    },
    sendCode() {
        if (this.data.countdown > 0)
            return;
        const phone = (this.data.phone || '').trim();
        if (!/^1\d{10}$/.test(phone)) {
            wx.showToast({ title: '请输入有效手机号', icon: 'none' });
            return;
        }
        wx.showToast({ title: '短信登录暂未开放', icon: 'none' });
    },
    loginByPhone() {
        wx.showToast({ title: '手机号登录暂未开放', icon: 'none' });
    },
    guestBrowse() {
        wx.switchTab({ url: router_1.ROUTES.home });
    },
    openAgreement() {
        wx.showModal({
            title: '用户服务协议',
            content: '完整协议页面即将上线，登录即表示您同意平台服务条款。',
            showCancel: false,
        });
    },
    openPrivacy() {
        wx.showModal({
            title: '隐私政策',
            content: '完整隐私政策页面即将上线，我们重视您的个人信息保护。',
            showCancel: false,
        });
    },
    loginDev() {
        (0, api_1.setToken)('dev-local-token');
        wx.showToast({ title: '已写入 Token', icon: 'success' });
        (0, wx_auth_1.leaveAfterLogin)();
    },
    async loginWx() {
        if (this.data.loggingIn)
            return;
        this.setData({ loggingIn: true });
        try {
            const manual = (this.data.inviteCodeInput || (0, invite_storage_1.peekPendingInviteCode)() || '').trim();
            if (manual)
                (0, invite_storage_1.stashInviteCode)(manual);
            const data = await (0, wx_auth_1.loginWithWxCode)({ inviteCode: manual || undefined });
            this.setData({ reauth: false, hasToken: true });
            (0, wx_auth_1.loginSuccessToast)(data);
            (0, wx_auth_1.leaveAfterLogin)();
        }
        catch (e) {
            const msg = typeof (e === null || e === void 0 ? void 0 : e.message) === 'string' ? e.message : '登录失败';
            wx.showToast({ title: msg.length > 20 ? msg.slice(0, 20) + '…' : msg, icon: 'none' });
        }
        finally {
            this.setData({ loggingIn: false });
        }
    },
});
