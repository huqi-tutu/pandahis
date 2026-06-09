"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const api_1 = require("../../native-utils/api");
const router_1 = require("../../native-utils/router");
const invite_bind_1 = require("../../native-utils/invite-bind");
const share_invite_1 = require("../../native-utils/share-invite");
Page({
    data: {
        hasToken: false,
        loading: false,
        inviteCode: '',
        readBalance: 0,
        invitedCount: 0,
        inviteRewardReads: 10,
        bindCode: '',
        bindSubmitting: false,
    },
    onShow() {
        const tab = typeof this.getTabBar === 'function' ? this.getTabBar() : null;
        if (tab && typeof tab.setSelected === 'function')
            tab.setSelected(2);
        const loggedIn = (0, api_1.hasToken)();
        this.setData({ hasToken: loggedIn });
        if (loggedIn) {
            void this.loadInviteMe();
        }
        else {
            this.setData({
                loading: false,
                inviteCode: '',
                readBalance: 0,
                invitedCount: 0,
            });
        }
    },
    onInviteFriends() {
        if (this.data.loading || !this.data.inviteCode)
            return;
        (0, share_invite_1.promptInviteByCode)(this.data.inviteCode);
    },
    goLogin() {
        (0, router_1.navigateTo)(router_1.ROUTES.login);
    },
    goHome() {
        wx.switchTab({ url: router_1.ROUTES.home });
    },
    async loadInviteMe() {
        var _a, _b, _c;
        this.setData({ loading: true });
        try {
            const res = await (0, api_1.request)('/invite/me', { auth: true });
            const d = res.data;
            this.setData({
                inviteCode: d.inviteCode || '',
                readBalance: (_a = d.readBalance) !== null && _a !== void 0 ? _a : 0,
                invitedCount: (_b = d.invitedCount) !== null && _b !== void 0 ? _b : 0,
                inviteRewardReads: (_c = d.inviteRewardReads) !== null && _c !== void 0 ? _c : 10,
            });
        }
        catch (e) {
            wx.showToast({ title: (e === null || e === void 0 ? void 0 : e.message) || '加载失败', icon: 'none' });
        }
        finally {
            this.setData({ loading: false });
        }
    },
    onBindInput(e) {
        this.setData({ bindCode: (e.detail.value || '').toUpperCase() });
    },
    async submitBindCode() {
        if (this.data.bindSubmitting)
            return;
        const code = (this.data.bindCode || '').trim();
        if (!code) {
            wx.showToast({ title: '请输入好友邀请码', icon: 'none' });
            return;
        }
        this.setData({ bindSubmitting: true });
        try {
            const res = await (0, invite_bind_1.bindInviteCode)(code);
            wx.showToast({
                title: res.message || (res.bound ? '绑定成功' : '绑定失败'),
                icon: res.bound ? 'success' : 'none',
            });
            if (res.bound)
                this.setData({ bindCode: '' });
        }
        catch (e) {
            const msg = e instanceof Error ? e.message : '提交失败';
            wx.showToast({ title: msg.length > 18 ? `${msg.slice(0, 16)}…` : msg, icon: 'none' });
        }
        finally {
            this.setData({ bindSubmitting: false });
        }
    },
    copyCode() {
        if (this.data.loading)
            return;
        const c = this.data.inviteCode;
        if (!c)
            return;
        void (0, share_invite_1.copyText)(c).then(() => wx.showToast({ title: '已复制', icon: 'none' }));
    },
    onShareAppMessage() {
        const code = (this.data.inviteCode || '').trim();
        const path = code
            ? (0, router_1.buildUrl)(router_1.ROUTES.inviteAccept, { inviteCode: code })
            : router_1.ROUTES.inviteAccept;
        return {
            title: '邀请你一起读历史图谱',
            path: path.startsWith('/') ? path : `/${path}`,
        };
    },
    onShareTimeline() {
        const code = (this.data.inviteCode || '').trim();
        return {
            title: '历史图谱 · 邀请你一起读',
            ...(code ? { query: `inviteCode=${encodeURIComponent(code)}` } : {}),
        };
    },
});
