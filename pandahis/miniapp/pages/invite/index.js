"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const api_1 = require("../../native-utils/api");
const brand_assets_1 = require("../../native-utils/brand-assets");
const router_1 = require("../../native-utils/router");
const share_invite_1 = require("../../native-utils/share-invite");
const nav_metrics_1 = require("../../native-utils/nav-metrics");
Page({
    data: {
        loading: false,
        loadError: false,
        inviteCode: '',
        invitedCount: 0,
        earnedReads: 0,
        inviteRewardReads: 100,
        canShare: false,
        invitees: [],
        pageTopPadPx: 88,
        showRules: false,
        heroCardBgUrl: brand_assets_1.INVITE_HERO_CARD_BG_URL,
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
        const tab = typeof this.getTabBar === 'function' ? this.getTabBar() : null;
        if (tab && typeof tab.setSelected === 'function') {
            ;
            tab.setSelected(2);
        }
        try {
            wx.showShareMenu({
                withShareTicket: true,
                menus: ['shareAppMessage', 'shareTimeline'],
            });
        }
        catch {
            // ignore
        }
        if (!(0, api_1.hasToken)()) {
            this.setData({
                loading: false,
                loadError: false,
                inviteCode: '',
                invitedCount: 0,
                earnedReads: 0,
                canShare: false,
                invitees: [],
            });
            (0, router_1.navigateTo)(router_1.ROUTES.login, { from: 'invite' });
            return;
        }
        void this.loadInviteMe();
    },
    noop() { },
    onRetryLoad() {
        void this.loadInviteMe();
    },
    onOpenRules() {
        this.setData({ showRules: true });
    },
    onCloseRules() {
        this.setData({ showRules: false });
    },
    onInviteFriends() {
        if (!this.data.inviteCode) {
            wx.showToast({ title: '邀请码加载中', icon: 'none' });
            return;
        }
        (0, share_invite_1.promptInviteByCode)(this.data.inviteCode);
    },
    formatRegisteredAt(iso) {
        if (!iso)
            return '—';
        const t = Date.parse(iso);
        if (Number.isNaN(t)) {
            const d = iso.slice(0, 10);
            return d || '—';
        }
        const date = new Date(t);
        const y = date.getFullYear();
        const m = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        return `${y}-${m}-${day}`;
    },
    mapInvitees(list, fallbackReward) {
        return (list || []).map((item, index) => {
            const nickname = (item.nickname || '').trim() || '好友';
            const reward = typeof item.rewardReads === 'number' ? item.rewardReads : fallbackReward;
            return {
                key: `${item.registeredAt || ''}-${index}`,
                nickname,
                avatarUrl: (item.avatarUrl || '').trim(),
                initial: nickname.charAt(0) || '友',
                registeredLabel: this.formatRegisteredAt(item.registeredAt),
                rewardLabel: reward > 0 ? `+${reward}点` : '',
            };
        });
    },
    async loadInviteMe() {
        var _a, _b;
        this.setData({ loading: true, loadError: false });
        try {
            const res = await (0, api_1.request)('/invite/me', { auth: true });
            const d = res.data;
            const inviteCode = d.inviteCode || '';
            const inviteRewardReads = (_a = d.inviteRewardReads) !== null && _a !== void 0 ? _a : 100;
            const invitedCount = (_b = d.invitedCount) !== null && _b !== void 0 ? _b : 0;
            // 邀请累计获得 ≈ 成功邀请数 × 单次奖励（与「余额」区分，避免消费后数字回落）
            const earnedReads = invitedCount * inviteRewardReads;
            this.setData({
                inviteCode,
                invitedCount,
                earnedReads,
                inviteRewardReads,
                canShare: Boolean(inviteCode),
                invitees: this.mapInvitees(d.invitees, inviteRewardReads),
                loadError: false,
            });
        }
        catch (e) {
            const msg = e instanceof Error ? e.message : '加载失败';
            this.setData({ loadError: true, invitees: [] });
            wx.showToast({ title: msg, icon: 'none' });
        }
        finally {
            this.setData({ loading: false });
        }
    },
    onShareAppMessage() {
        const code = (this.data.inviteCode || '').trim();
        const path = code
            ? (0, router_1.buildUrl)(router_1.ROUTES.inviteAccept, { inviteCode: code })
            : router_1.ROUTES.inviteAccept;
        return {
            title: `邀请你一起读${brand_assets_1.APP_DISPLAY_NAME}`,
            path: path.startsWith('/') ? path : `/${path}`,
            imageUrl: brand_assets_1.INVITE_SHARE_COVER_URL,
        };
    },
    onShareTimeline() {
        const code = (this.data.inviteCode || '').trim();
        return {
            title: `${brand_assets_1.APP_DISPLAY_NAME} · 邀请你一起读`,
            ...(code ? { query: `inviteCode=${encodeURIComponent(code)}` } : {}),
        };
    },
});
