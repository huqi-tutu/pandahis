"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const api_1 = require("../../native-utils/api");
const load_error_message_1 = require("../../native-utils/load-error-message");
const nav_metrics_1 = require("../../native-utils/nav-metrics");
const router_1 = require("../../native-utils/router");
Page({
    data: {
        nickname: '',
        avatarUrl: '',
        avatarInitial: '我',
        saving: false,
        avatarUploading: false,
        pageTopPadPx: 88,
        keyboardPadPx: 0,
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
        if (!(0, api_1.hasToken)()) {
            (0, router_1.navigateTo)(router_1.ROUTES.login);
            return;
        }
        void this.load();
    },
    async load() {
        try {
            const res = await (0, api_1.request)('/me', { auth: true });
            const raw = res.data || {};
            const nickname = raw.nickname || '';
            const avatarUrl = raw.avatarUrl || raw.avatar_url || '';
            const initial = nickname ? String(nickname).charAt(0) : '我';
            this.setData({ nickname, avatarUrl, avatarInitial: initial });
        }
        catch (e) {
            const msg = e instanceof Error ? e.message : '';
            console.error('[profile-edit] load failed', e);
            if (msg === 'UNAUTHORIZED') {
                (0, router_1.navigateTo)(router_1.ROUTES.login);
                return;
            }
            wx.showModal({
                title: '加载资料失败',
                content: (0, load_error_message_1.formatApiRequestError)(e),
                showCancel: false,
            });
        }
    },
    onInput(e) {
        const nickname = e.detail.value || '';
        this.setData({
            nickname,
            avatarInitial: nickname.trim() ? nickname.trim().charAt(0) : '我',
        });
    },
    onInputFocus() {
        // 自定义导航页上，额外留白确保输入框不被键盘挡住
    },
    onInputBlur() {
        this.setData({ keyboardPadPx: 0 });
    },
    onKeyboardHeightChange(e) {
        var _a;
        const height = Math.max(0, Math.floor(Number((_a = e.detail) === null || _a === void 0 ? void 0 : _a.height) || 0));
        this.setData({ keyboardPadPx: height });
    },
    async onChooseAvatar(e) {
        var _a, _b, _c;
        if (this.data.avatarUploading)
            return;
        const localPath = ((_a = e.detail) === null || _a === void 0 ? void 0 : _a.avatarUrl) || '';
        if (!localPath) {
            wx.showToast({ title: '未获取到头像', icon: 'none' });
            return;
        }
        const prevAvatarUrl = this.data.avatarUrl;
        this.setData({ avatarUrl: localPath, avatarUploading: true });
        try {
            const res = await (0, api_1.uploadFile)('/me/avatar', localPath, { name: 'file' });
            const nextUrl = ((_b = res.data) === null || _b === void 0 ? void 0 : _b.avatarUrl) || ((_c = res.data) === null || _c === void 0 ? void 0 : _c.avatar_url) || localPath;
            this.setData({ avatarUrl: nextUrl });
            wx.showToast({ title: '头像已更新', icon: 'success' });
        }
        catch (err) {
            this.setData({ avatarUrl: prevAvatarUrl });
            const msg = err instanceof Error ? err.message : '上传失败';
            wx.showToast({
                title: msg.length > 18 ? `${msg.slice(0, 16)}…` : msg,
                icon: 'none',
            });
        }
        finally {
            this.setData({ avatarUploading: false });
        }
    },
    async onSave() {
        if (this.data.saving)
            return;
        const nickname = (this.data.nickname || '').trim();
        if (!nickname) {
            wx.showToast({ title: '请输入昵称', icon: 'none' });
            return;
        }
        this.setData({ saving: true });
        try {
            await (0, api_1.request)('/me/profile', {
                method: 'PATCH',
                auth: true,
                data: { nickname },
            });
            wx.showToast({ title: '已保存', icon: 'success' });
            setTimeout(() => wx.navigateBack(), 400);
        }
        catch (e) {
            const msg = e instanceof Error ? e.message : '保存失败';
            wx.showToast({ title: msg.length > 18 ? `${msg.slice(0, 16)}…` : msg, icon: 'none' });
        }
        finally {
            this.setData({ saving: false });
        }
    },
});
