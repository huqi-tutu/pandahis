"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const api_1 = require("../../native-utils/api");
const invite_bind_1 = require("../../native-utils/invite-bind");
const invite_storage_1 = require("../../native-utils/invite-storage");
const router_1 = require("../../native-utils/router");
const wx_auth_1 = require("../../native-utils/wx-auth");
Page({
    data: {
        hasPendingInvite: false,
        loggingIn: false,
        inviteCodeInput: '',
    },
    onLoad(query) {
        var _a;
        (0, invite_storage_1.stashInviteCodeFromQuery)(query);
        try {
            const launch = (_a = wx.getLaunchOptionsSync) === null || _a === void 0 ? void 0 : _a.call(wx);
            if (launch)
                (0, invite_storage_1.stashInviteFromLaunchOptions)(launch);
        }
        catch {
            // ignore
        }
        const pending = (0, invite_storage_1.peekPendingInviteCode)();
        this.setData({
            hasPendingInvite: Boolean(pending),
            inviteCodeInput: pending || '',
        });
    },
    onInviteCodeInput(e) {
        const v = (e.detail.value || '').trim().toUpperCase();
        this.setData({ inviteCodeInput: v, hasPendingInvite: Boolean(v) });
        if (v)
            (0, invite_storage_1.stashInviteCode)(v);
    },
    async onShow() {
        const pending = (0, invite_storage_1.peekPendingInviteCode)();
        this.setData({
            hasPendingInvite: Boolean(pending),
            inviteCodeInput: pending || this.data.inviteCodeInput || '',
        });
        if ((0, api_1.hasToken)()) {
            const manual = (this.data.inviteCodeInput || '').trim();
            if (manual) {
                try {
                    const res = await (0, invite_bind_1.bindInviteCode)(manual);
                    if (res.bound) {
                        wx.showToast({ title: '邀请已绑定', icon: 'success' });
                    }
                }
                catch {
                    // 已绑定过等情况静默，仍进入首页
                }
            }
            wx.switchTab({ url: router_1.ROUTES.home });
        }
    },
    goLogin() {
        (0, router_1.navigateTo)(router_1.ROUTES.login);
    },
    async loginHere() {
        if (this.data.loggingIn)
            return;
        this.setData({ loggingIn: true });
        try {
            const manual = (this.data.inviteCodeInput || (0, invite_storage_1.peekPendingInviteCode)() || '').trim();
            if (manual)
                (0, invite_storage_1.stashInviteCode)(manual);
            const data = await (0, wx_auth_1.loginWithWxCode)({ inviteCode: manual || undefined });
            (0, wx_auth_1.loginSuccessToast)(data);
            setTimeout(() => wx.switchTab({ url: router_1.ROUTES.home }), 500);
        }
        catch (e) {
            const msg = typeof (e === null || e === void 0 ? void 0 : e.message) === 'string' ? e.message : '登录失败';
            wx.showToast({ title: msg.length > 20 ? msg.slice(0, 20) + '…' : msg, icon: 'none' });
        }
        finally {
            this.setData({ loggingIn: false });
        }
    },
    goHome() {
        wx.switchTab({ url: router_1.ROUTES.home });
    },
});
