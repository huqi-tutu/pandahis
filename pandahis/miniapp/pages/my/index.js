"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const api_1 = require("../../native-utils/api");
const category_label_1 = require("../../native-utils/category-label");
const router_1 = require("../../native-utils/router");
const APP_VERSION = '0.1.0';
Page({
    data: {
        loggedIn: false,
        nickname: '',
        avatarUrl: '',
        avatarInitial: '我',
        phoneLine: '未绑定手机号',
        footprintSummary: '—',
        favoriteSummary: '—',
        vipTitle: '开通年度会员',
        vipDesc: '解锁全地域图谱 · 跨时空评述 · 见证 Tab',
        appVersion: APP_VERSION,
    },
    onShow() {
        const tab = typeof this.getTabBar === 'function' ? this.getTabBar() : null;
        if (tab && typeof tab.setSelected === 'function')
            tab.setSelected(3);
        void this.refresh();
    },
    async refresh() {
        var _a, _b;
        if (!(0, api_1.hasToken)()) {
            this.setData({
                loggedIn: false,
                nickname: '',
                avatarUrl: '',
                avatarInitial: '我',
                phoneLine: '未绑定手机号',
                footprintSummary: '—',
                favoriteSummary: '—',
                vipTitle: '开通年度会员',
                vipDesc: '解锁全地域图谱 · 跨时空评述 · 见证 Tab',
            });
            return;
        }
        try {
            const [meRes, membership] = await Promise.all([
                (0, api_1.request)('/me', { auth: true }),
                (0, api_1.request)('/membership', { auth: true }).catch(() => null),
            ]);
            const me = meRes.data;
            const phone = me.phoneMasked && me.phoneMasked !== 'null' ? me.phoneMasked : '';
            const initial = (me.nickname || '我').trim().charAt(0) || '我';
            let favoriteSummary = `${me.favoriteCount} 项`;
            if (me.favoriteCount > 0) {
                try {
                    const favRes = await (0, api_1.request)('/favorites/boxes?page=1&pageSize=50', { auth: true });
                    favoriteSummary = (0, category_label_1.buildFavoriteSummary)(favRes.data.items || []);
                }
                catch {
                    favoriteSummary = `${me.favoriteCount} 项`;
                }
            }
            else {
                favoriteSummary = '暂无';
            }
            const ms = ((_a = membership === null || membership === void 0 ? void 0 : membership.data) === null || _a === void 0 ? void 0 : _a.status) || me.membershipStatus || 'NONE';
            const endAt = ((_b = membership === null || membership === void 0 ? void 0 : membership.data) === null || _b === void 0 ? void 0 : _b.endAt) || me.membershipEndAt;
            const vip = this.vipCopy(ms, endAt);
            this.setData({
                loggedIn: true,
                nickname: me.nickname || '用户',
                avatarUrl: me.avatarUrl || '',
                avatarInitial: initial,
                phoneLine: phone || '未绑定手机号',
                footprintSummary: `${me.footprintCount} 条`,
                favoriteSummary,
                vipTitle: vip.title,
                vipDesc: vip.desc,
            });
        }
        catch (e) {
            const msg = (e && e.message) || '';
            if (msg === 'UNAUTHORIZED') {
                (0, api_1.clearToken)();
            }
            this.setData({ loggedIn: false });
        }
    },
    vipCopy(status, endAt) {
        if (status === 'ACTIVE' && endAt) {
            const d = endAt.slice(0, 10);
            return {
                title: '年度会员已开通',
                desc: `有效期至 ${d} · 畅享全部深度 Tab`,
            };
        }
        return {
            title: '开通年度会员',
            desc: '解锁全地域图谱 · 跨时空评述 · 见证 Tab',
        };
    },
    requireLogin(action) {
        if (!(0, api_1.hasToken)()) {
            this.goLogin();
            return;
        }
        action();
    },
    goLogin() {
        (0, router_1.navigateTo)(router_1.ROUTES.login, { reauth: '1' });
    },
    onEditProfile() {
        this.requireLogin(() => (0, router_1.navigateTo)(router_1.ROUTES.profileEdit));
    },
    goMembership() {
        wx.switchTab({ url: router_1.ROUTES.membership });
    },
    goFootprints() {
        this.requireLogin(() => (0, router_1.navigateTo)(router_1.ROUTES.footprints));
    },
    goFavorites() {
        this.requireLogin(() => (0, router_1.navigateTo)(router_1.ROUTES.favorites));
    },
    goSettings() {
        (0, router_1.navigateTo)(router_1.ROUTES.settings);
    },
    goHelp() {
        const email = 'support@pandahis.com';
        wx.showModal({
            title: '帮助与反馈',
            content: `如有问题或建议，请发送邮件至：\n${email}`,
            confirmText: '复制邮箱',
            cancelText: '关闭',
            success: (r) => {
                if (!r.confirm)
                    return;
                wx.setClipboardData({
                    data: email,
                    success: () => wx.showToast({ title: '已复制邮箱', icon: 'success' }),
                });
            },
        });
    },
    goAbout() {
        (0, router_1.navigateTo)(router_1.ROUTES.about);
    },
    logout() {
        wx.showModal({
            title: '退出登录',
            content: '退出后需重新登录才能使用收藏、足迹与邀请功能。',
            confirmText: '退出',
            success: (r) => {
                if (!r.confirm)
                    return;
                (0, api_1.clearToken)();
                void this.refresh();
                wx.showToast({ title: '已退出', icon: 'success' });
            },
        });
    },
});
