"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const api_1 = require("../../native-utils/api");
const invite_storage_1 = require("../../native-utils/invite-storage");
const load_error_message_1 = require("../../native-utils/load-error-message");
const wx_auth_1 = require("../../native-utils/wx-auth");
const router_1 = require("../../native-utils/router");
const runtime_env_1 = require("../../native-utils/runtime-env");
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
        agreed: false,
        devVisible: false,
        apiBase: '',
        guestTop: 0,
        guestHeight: 32,
    },
    _countdownTimer: null,
    onLoad(query) {
        const reauth = query.reauth === '1' || query.reauth === 'true';
        if (reauth) {
            (0, api_1.clearToken)();
        }
        // 「立即体验」与右上角胶囊按钮上下居中对齐
        const rect = wx.getMenuButtonBoundingClientRect();
        this.setData({
            reauth,
            devVisible: (0, runtime_env_1.isDevtoolsClient)(),
            guestTop: rect.top,
            guestHeight: rect.height,
        });
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
            apiBase: (0, api_1.getBaseUrl)(),
        });
        if ((0, api_1.hasToken)() && !this.data.reauth) {
            void (0, api_1.request)('/me', { auth: true, softAuth: true })
                .then(() => (0, wx_auth_1.leaveAfterLogin)(0))
                .catch(() => {
                (0, api_1.clearAccessToken)();
                this.setData({ hasToken: false });
            });
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
    toggleAgree() {
        this.setData({ agreed: !this.data.agreed });
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
        (0, api_1.useLocalDevApi)();
        (0, api_1.setToken)('dev-local-token');
        this.setData({ apiBase: (0, api_1.getBaseUrl)() });
        wx.showToast({ title: '本机 API + dev Token', icon: 'success' });
        (0, wx_auth_1.leaveAfterLogin)();
    },
    useProdApi() {
        (0, api_1.useProductionApi)();
        this.setData({ apiBase: (0, api_1.getBaseUrl)() });
        wx.showToast({ title: '已切换生产 API', icon: 'success' });
    },
    useLocalApi() {
        (0, api_1.useLocalDevApi)();
        this.setData({ apiBase: (0, api_1.getBaseUrl)() });
        wx.showToast({ title: '已切换本机 API', icon: 'success' });
    },
    async loginWx() {
        if (this.data.loggingIn)
            return;
        if (!this.data.agreed) {
            wx.showToast({ title: '请先勾选同意用户协议与隐私政策', icon: 'none' });
            return;
        }
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
            const msg = (0, load_error_message_1.formatApiRequestError)(e);
            wx.showModal({
                title: '登录失败',
                content: `${msg}\n\n当前接口：${(0, api_1.getBaseUrl)()}`,
                showCancel: false,
            });
        }
        finally {
            this.setData({ loggingIn: false });
        }
    },
});
