"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const api_1 = require("../../native-utils/api");
const invite_bind_1 = require("../../native-utils/invite-bind");
const router_1 = require("../../native-utils/router");
const APP_VERSION = '1.0.0';
Page({
    data: {
        loggedIn: false,
        apiBase: '',
        bindCode: '',
        bindSubmitting: false,
        headerPadPx: 88,
        appVersion: APP_VERSION,
    },
    onLoad() {
        try {
            const sys = wx.getSystemInfoSync();
            const navPx = 88 * (sys.windowWidth / 750);
            this.setData({ headerPadPx: (sys.statusBarHeight || 20) + navPx });
        }
        catch {
            this.setData({ headerPadPx: 88 });
        }
    },
    onShow() {
        this.setData({
            loggedIn: (0, api_1.hasToken)(),
            apiBase: (0, api_1.getBaseUrl)(),
        });
    },
    onBindInput(e) {
        this.setData({ bindCode: (e.detail.value || '').toUpperCase() });
    },
    async submitBindCode() {
        if (!(0, api_1.hasToken)()) {
            (0, router_1.navigateTo)(router_1.ROUTES.login);
            return;
        }
        if (this.data.bindSubmitting)
            return;
        const code = (this.data.bindCode || '').trim();
        if (!code) {
            wx.showToast({ title: '请输入邀请码', icon: 'none' });
            return;
        }
        this.setData({ bindSubmitting: true });
        try {
            const res = await (0, invite_bind_1.bindInviteCode)(code);
            wx.showToast({
                title: res.message || (res.bound ? '已绑定' : '绑定失败'),
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
    goHelp() {
        wx.showModal({
            title: '帮助与反馈',
            content: `如有问题或建议，请发送邮件至：\n${router_1.SUPPORT_EMAIL}`,
            confirmText: '复制邮箱',
            cancelText: '关闭',
            success: (r) => {
                if (!r.confirm)
                    return;
                wx.setClipboardData({
                    data: router_1.SUPPORT_EMAIL,
                    success: () => wx.showToast({ title: '已复制邮箱', icon: 'success' }),
                });
            },
        });
    },
    goAbout() {
        (0, router_1.navigateTo)(router_1.ROUTES.about);
    },
    goProfileEdit() {
        if (!(0, api_1.hasToken)()) {
            (0, router_1.navigateTo)(router_1.ROUTES.login);
            return;
        }
        (0, router_1.navigateTo)(router_1.ROUTES.profileEdit);
    },
    clearCache() {
        wx.showModal({
            title: '清除缓存',
            content: '将清除本地图片缓存等数据，不会删除登录状态与邀请码。',
            success: (r) => {
                if (!r.confirm)
                    return;
                try {
                    const info = wx.getStorageInfoSync();
                    const keep = new Set(['accessToken', 'apiBaseUrl', 'pendingInviteCode', 'userLoggedOut']);
                    for (const key of info.keys) {
                        if (!keep.has(key))
                            wx.removeStorageSync(key);
                    }
                }
                catch {
                    // ignore
                }
                wx.showToast({ title: '已清除', icon: 'success' });
            },
        });
    },
    logout() {
        wx.showModal({
            title: '退出登录',
            content: '确定退出当前账号？',
            confirmText: '退出',
            success: (r) => {
                if (!r.confirm)
                    return;
                (0, api_1.clearToken)();
                this.setData({ loggedIn: false });
                wx.showToast({ title: '已退出', icon: 'success' });
                setTimeout(() => (0, router_1.navigateTo)(router_1.ROUTES.login), 400);
            },
        });
    },
});
