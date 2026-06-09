"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const api_1 = require("../../native-utils/api");
const router_1 = require("../../native-utils/router");
const share_invite_1 = require("../../native-utils/share-invite");
Page({
    data: {
        targetCount: 4,
        currentCount: 0,
        completed: false,
        rewardClaimed: false,
        durationDays: 90,
        endDateLabel: '',
        slots: [],
        inviteCode: '',
    },
    onShow() {
        if (!(0, api_1.hasToken)()) {
            (0, router_1.navigateTo)(router_1.ROUTES.login);
            return;
        }
        void this.load();
    },
    onInviteFriends() {
        (0, share_invite_1.promptInviteByCode)(this.data.inviteCode, { title: '好友助力' });
    },
    async load() {
        var _a;
        try {
            const [assistRes, inviteRes] = await Promise.all([
                (0, api_1.request)('/membership/assist', { auth: true }),
                (0, api_1.request)('/invite/me', { auth: true }).catch(() => null),
            ]);
            const a = assistRes.data;
            const inviteCode = ((_a = inviteRes === null || inviteRes === void 0 ? void 0 : inviteRes.data) === null || _a === void 0 ? void 0 : _a.inviteCode) || '';
            const slots = this.buildSlots(a.targetCount, a.currentCount);
            const endDateLabel = this.formatEndDate(a.membershipEndAt);
            this.setData({
                targetCount: a.targetCount,
                currentCount: a.currentCount,
                completed: a.completed,
                rewardClaimed: a.rewardClaimed,
                durationDays: a.rewardDurationDays,
                endDateLabel,
                slots,
                inviteCode,
            });
            if (a.completed && !a.rewardClaimed) {
                void this.tryClaim();
            }
        }
        catch (e) {
            wx.showToast({ title: (e === null || e === void 0 ? void 0 : e.message) || '加载失败', icon: 'none' });
        }
    },
    buildSlots(target, current) {
        const slots = [];
        for (let i = 0; i < target; i++) {
            slots.push({
                filled: i < current,
                label: '友',
            });
        }
        return slots;
    },
    formatEndDate(iso) {
        if (!iso)
            return '';
        const d = iso.slice(0, 10);
        const parts = d.split('-');
        if (parts.length === 3)
            return `${parts[0]}-${Number(parts[1])}-${Number(parts[2])}`;
        return d;
    },
    async tryClaim() {
        try {
            const res = await (0, api_1.request)('/membership/assist/claim', {
                method: 'POST',
                auth: true,
            });
            const a = res.data;
            this.setData({
                rewardClaimed: a.rewardClaimed,
                endDateLabel: this.formatEndDate(a.membershipEndAt),
                completed: true,
                slots: this.buildSlots(a.targetCount, a.targetCount),
            });
            wx.showToast({ title: '季度会员已开通', icon: 'success' });
        }
        catch (e) {
            const msg = (e === null || e === void 0 ? void 0 : e.message) || '';
            if (!msg.includes('not completed')) {
                wx.showToast({ title: msg || '领取失败', icon: 'none' });
            }
        }
    },
    onShareAppMessage() {
        const code = (this.data.inviteCode || '').trim();
        const path = code
            ? (0, router_1.buildUrl)(router_1.ROUTES.inviteAccept, { inviteCode: code })
            : router_1.ROUTES.inviteAccept;
        return {
            title: '帮我助力，一起读历史图谱',
            path: path.startsWith('/') ? path : `/${path}`,
        };
    },
    onShareTimeline() {
        const code = (this.data.inviteCode || '').trim();
        return {
            title: '历史图谱 · 邀你助力领会员',
            ...(code ? { query: `inviteCode=${encodeURIComponent(code)}` } : {}),
        };
    },
});
