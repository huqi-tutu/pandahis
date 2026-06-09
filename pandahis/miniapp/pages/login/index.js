"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const api_1 = require("../../native-utils/api");
const invite_storage_1 = require("../../native-utils/invite-storage");
const wx_auth_1 = require("../../native-utils/wx-auth");
Page({
    data: {
        loggingIn: false,
        pendingInvite: '',
        inviteCodeInput: '',
        hasToken: false,
        reauth: false,
    },
    onLoad(query) {
        const reauth = (query === null || query === void 0 ? void 0 : query.reauth) === '1' || (query === null || query === void 0 ? void 0 : query.reauth) === 'true';
        if (reauth) {
            (0, api_1.clearToken)();
        }
        this.setData({ reauth });
    },
    onInviteCodeInput(e) {
        const v = (e.detail.value || '').trim().toUpperCase();
        this.setData({ inviteCodeInput: v });
        if (v)
            (0, invite_storage_1.stashInviteCode)(v);
    },
    onShow() {
        const pendingInvite = (0, invite_storage_1.peekPendingInviteCode)();
        this.setData({
            pendingInvite,
            inviteCodeInput: pendingInvite || '',
            hasToken: (0, api_1.hasToken)(),
        });
        if ((0, api_1.hasToken)() && !this.data.reauth) {
            wx.navigateBack({ fail: () => wx.switchTab({ url: '/pages/home/index' }) });
        }
    },
    loginDev() {
        (0, api_1.setToken)('dev-local-token');
        wx.showToast({ title: '已写入 Token', icon: 'success' });
        setTimeout(() => wx.navigateBack(), 500);
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
            (0, wx_auth_1.loginSuccessToast)(data);
            setTimeout(() => wx.navigateBack(), 500);
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
