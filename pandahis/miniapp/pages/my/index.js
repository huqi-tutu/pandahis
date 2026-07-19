"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const api_1 = require("../../native-utils/api");
const router_1 = require("../../native-utils/router");
const share_invite_1 = require("../../native-utils/share-invite");
const APP_VERSION = '1.0.0';
/** 兼容 camelCase / snake_case 的 /me 响应 */
function normalizeMe(raw) {
    var _a, _b, _c, _d, _e, _f, _g, _h, _j, _k, _l, _m, _o, _p, _q, _r;
    return {
        nickname: String((_b = (_a = raw.nickname) !== null && _a !== void 0 ? _a : raw['nickname']) !== null && _b !== void 0 ? _b : ''),
        avatarUrl: ((_d = (_c = raw.avatarUrl) !== null && _c !== void 0 ? _c : raw['avatar_url']) !== null && _d !== void 0 ? _d : null),
        phoneMasked: String((_f = (_e = raw.phoneMasked) !== null && _e !== void 0 ? _e : raw['phone_masked']) !== null && _f !== void 0 ? _f : ''),
        favoriteCount: Number((_h = (_g = raw.favoriteCount) !== null && _g !== void 0 ? _g : raw['favorite_count']) !== null && _h !== void 0 ? _h : 0),
        footprintCount: Number((_k = (_j = raw.footprintCount) !== null && _j !== void 0 ? _j : raw['footprint_count']) !== null && _k !== void 0 ? _k : 0),
        learnDaysCount: Number((_m = (_l = raw.learnDaysCount) !== null && _l !== void 0 ? _l : raw['learn_days_count']) !== null && _m !== void 0 ? _m : 0),
        membershipStatus: String((_p = (_o = raw.membershipStatus) !== null && _o !== void 0 ? _o : raw['membership_status']) !== null && _p !== void 0 ? _p : 'NONE'),
        membershipEndAt: ((_r = (_q = raw.membershipEndAt) !== null && _q !== void 0 ? _q : raw['membership_end_at']) !== null && _r !== void 0 ? _r : null),
    };
}
Page({
    data: {
        loggedIn: false,
        isVip: false,
        nickname: '',
        avatarUrl: '',
        avatarInitial: '我',
        phoneLine: '未绑定手机号',
        footprintCount: 0,
        favoriteCount: 0,
        learnDays: 0,
        vipTitle: '开通年度会员',
        vipDesc: '解锁全地域图谱 · 跨时空评述 · 见证 Tab',
        appVersion: APP_VERSION,
        headerPadPx: 88,
    },
    onLoad() {
        // 与 proto-nav 一致：状态栏 + 88rpx 导航行（随屏宽换算 px）
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
        const tab = typeof this.getTabBar === 'function' ? this.getTabBar() : null;
        if (tab && typeof tab.setSelected === 'function')
            tab.setSelected(3);
        void this.refresh();
    },
    setGuestState() {
        this.setData({
            loggedIn: false,
            isVip: false,
            nickname: '',
            avatarUrl: '',
            avatarInitial: '我',
            phoneLine: '未绑定手机号',
            footprintCount: 0,
            favoriteCount: 0,
            learnDays: 0,
            vipTitle: '开通年度会员',
            vipDesc: '解锁全地域图谱 · 跨时空评述 · 见证 Tab',
        });
    },
    async refresh() {
        var _a, _b;
        if (!(0, api_1.hasToken)()) {
            this.setGuestState();
            return;
        }
        try {
            const [meRes, membership] = await Promise.all([
                (0, api_1.request)('/me', { auth: true }),
                (0, api_1.request)('/membership', { auth: true }).catch(() => null),
            ]);
            const me = normalizeMe((meRes.data || {}));
            const phone = me.phoneMasked && me.phoneMasked !== 'null' ? me.phoneMasked : '';
            const initial = (me.nickname || '我').trim().charAt(0) || '我';
            const ms = ((_a = membership === null || membership === void 0 ? void 0 : membership.data) === null || _a === void 0 ? void 0 : _a.status) || me.membershipStatus || 'NONE';
            const endAt = ((_b = membership === null || membership === void 0 ? void 0 : membership.data) === null || _b === void 0 ? void 0 : _b.endAt) || me.membershipEndAt;
            const isVip = String(ms).toUpperCase() === 'ACTIVE';
            const vip = this.vipCopy(ms, endAt);
            this.setData({
                loggedIn: true,
                isVip,
                nickname: me.nickname || '用户',
                avatarUrl: me.avatarUrl || '',
                avatarInitial: initial,
                phoneLine: phone || '未绑定手机号',
                footprintCount: me.footprintCount,
                favoriteCount: me.favoriteCount,
                learnDays: me.learnDaysCount,
                vipTitle: vip.title,
                vipDesc: vip.desc,
            });
        }
        catch (e) {
            const msg = e instanceof Error ? e.message : '';
            console.error('[my] refresh failed', e);
            if (msg === 'UNAUTHORIZED') {
                (0, api_1.clearToken)();
                this.setGuestState();
                return;
            }
            const vip = this.vipCopy('NONE', null);
            this.setData({
                loggedIn: true,
                isVip: false,
                nickname: '用户',
                avatarUrl: '',
                avatarInitial: '我',
                phoneLine: '未绑定手机号',
                footprintCount: 0,
                favoriteCount: 0,
                learnDays: 0,
                vipTitle: vip.title,
                vipDesc: vip.desc,
            });
        }
    },
    vipCopy(status, endAt) {
        const st = String(status || '').toUpperCase();
        const endStr = endAt == null ? '' : String(endAt);
        if (st === 'ACTIVE' && endStr) {
            const d = endStr.slice(0, 10);
            const daysLeft = Math.max(0, Math.ceil((Date.parse(endStr) - Date.now()) / (24 * 60 * 60 * 1000)));
            const tier = daysLeft > 0 && daysLeft <= 120 ? '季度' : '典藏';
            return {
                title: `${tier}会员已开通`,
                desc: `有效期至 ${d} · 评述 / 见证 / 原文免扣阅读点`,
            };
        }
        return {
            title: '开通典藏会员',
            desc: '邀友助力免费季卡 · 或付费订阅 · 深度阅读免扣点',
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
    goCorrections() {
        this.requireLogin(() => (0, router_1.navigateTo)(router_1.ROUTES.corrections));
    },
    goSettings() {
        (0, router_1.navigateTo)(router_1.ROUTES.settings);
    },
    onShareFriend() {
        (0, share_invite_1.promptContentShareUnavailable)();
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
});
