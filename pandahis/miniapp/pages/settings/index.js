"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const api_1 = require("../../native-utils/api");
const invite_bind_1 = require("../../native-utils/invite-bind");
const load_error_message_1 = require("../../native-utils/load-error-message");
const nav_metrics_1 = require("../../native-utils/nav-metrics");
const runtime_env_1 = require("../../native-utils/runtime-env");
const router_1 = require("../../native-utils/router");
const APP_VERSION = '1.0.0';
Page({
    data: {
        loggedIn: false,
        apiBase: '',
        bindCode: '',
        bindSubmitting: false,
        pageTopPadPx: 88,
        appVersion: APP_VERSION,
    },
    onLoad() {
        try {
            this.setData({ pageTopPadPx: (0, nav_metrics_1.computePageTopPadPx)() });
        }
        catch {
            this.setData({ pageTopPadPx: 88 });
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
    async testApiConnection() {
        wx.showLoading({ title: '检测中', mask: true });
        const result = await (0, api_1.probeApiConnectivity)();
        wx.hideLoading();
        if (result.ok) {
            wx.showModal({
                title: '连接正常',
                content: `基础、登录、朝代概要、朝代画布接口均正常。\n\n当前接口：\n${(0, api_1.getBaseUrl)()}${(0, api_1.hasToken)() ? '\n\n已保存登录令牌' : '\n\n未登录（请在登录页授权）'}`,
                showCancel: false,
            });
            return;
        }
        const hint = (0, load_error_message_1.formatApiRequestError)(result.error);
        const stageText = result.stage === 'swim-matrix'
            ? '（朝代画布接口失败，详情页无法展示）'
            : result.stage === 'unit'
                ? '（朝代概要接口失败）'
                : result.stage === 'auth'
                    ? '（微信登录接口不可达，登录与用户资料会失败）'
                    : '（基础健康检查失败）';
        wx.showModal({
            title: '连接失败',
            content: `${hint}${stageText}\n\n当前配置：\n${(0, api_1.getBaseUrl)()}`,
            confirmText: '切生产接口',
            cancelText: '关闭',
            success: (r) => {
                if (!r.confirm)
                    return;
                (0, api_1.useProductionApi)();
                this.setData({ apiBase: (0, api_1.getBaseUrl)() });
                wx.showToast({ title: '已切换生产接口', icon: 'success' });
            },
        });
    },
    onApiBaseTap() {
        if ((0, runtime_env_1.getEnvVersion)() !== 'develop') {
            void this.testApiConnection();
            return;
        }
        const items = ['使用生产接口（推荐，手机预览用这个）', '检测接口连接'];
        const localDevIndex = (0, runtime_env_1.isDevtoolsClient)() ? items.push('使用本机接口 localhost:8080') - 1 : -1;
        wx.showActionSheet({
            itemList: items,
            success: (res) => {
                if (res.tapIndex === 0) {
                    (0, api_1.useProductionApi)();
                    wx.showToast({ title: '已切换生产接口', icon: 'success' });
                    this.setData({ apiBase: (0, api_1.getBaseUrl)() });
                }
                else if (res.tapIndex === 1) {
                    void this.testApiConnection();
                }
                else if (res.tapIndex === localDevIndex) {
                    (0, api_1.useLocalDevApi)();
                    wx.showToast({ title: '已切换本机接口', icon: 'success' });
                    this.setData({ apiBase: (0, api_1.getBaseUrl)() });
                }
            },
        });
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
