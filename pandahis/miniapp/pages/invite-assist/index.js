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
        deadlineLabel: '',
        assistExpired: false,
        slots: [],
        inviteCode: '',
        canShare: true,
        headerPadPx: 88,
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
        if (!(0, api_1.hasToken)()) {
            (0, router_1.navigateTo)(router_1.ROUTES.login);
            return;
        }
        void this.load();
    },
    onInviteFriends() {
        if (!this.data.inviteCode) {
            wx.showToast({ title: '邀请码加载中', icon: 'none' });
            return;
        }
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
            const participants = a.participants || [];
            const endDateLabel = this.formatEndDate(a.membershipEndAt);
            const deadlineLabel = this.formatEndDate(a.assistDeadlineAt);
            const assistExpired = this.isExpired(a.assistDeadlineAt) && !a.rewardClaimed;
            const slots = this.buildSlots(a.targetCount, participants, a.rewardClaimed ? a.targetCount : a.currentCount);
            this.setData({
                targetCount: a.targetCount,
                currentCount: a.rewardClaimed ? a.targetCount : a.currentCount,
                completed: a.completed,
                rewardClaimed: a.rewardClaimed,
                durationDays: a.rewardDurationDays || 90,
                endDateLabel,
                deadlineLabel,
                assistExpired,
                slots,
                inviteCode,
                canShare: Boolean(inviteCode),
            });
            if (a.completed && !a.rewardClaimed && !assistExpired) {
                void this.tryClaim();
            }
        }
        catch (e) {
            const msg = e instanceof Error ? e.message : '加载失败';
            wx.showToast({ title: msg, icon: 'none' });
        }
    },
    buildSlots(target, participants, filledCount) {
        const slots = [];
        for (let i = 0; i < target; i++) {
            const filled = i < filledCount;
            const p = participants[i];
            if (filled && p) {
                const name = (p.nickname || '').trim();
                slots.push({
                    filled: true,
                    label: name ? name.charAt(0) : '友',
                    avatarUrl: (p.avatarUrl || '').trim(),
                });
            }
            else if (filled) {
                slots.push({ filled: true, label: '友', avatarUrl: '' });
            }
            else {
                slots.push({ filled: false, label: '', avatarUrl: '' });
            }
        }
        return slots;
    },
    isExpired(iso) {
        if (!iso)
            return false;
        const t = Date.parse(iso);
        return !Number.isNaN(t) && t < Date.now();
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
            const participants = a.participants || [];
            this.setData({
                rewardClaimed: a.rewardClaimed,
                endDateLabel: this.formatEndDate(a.membershipEndAt),
                completed: true,
                currentCount: a.targetCount,
                slots: this.buildSlots(a.targetCount, participants, a.targetCount),
            });
            wx.showToast({ title: '季度会员已开通', icon: 'success' });
        }
        catch (e) {
            const msg = e instanceof Error ? e.message : '';
            if (msg.includes('expired')) {
                this.setData({ assistExpired: true });
                wx.showToast({ title: '助力活动已过期', icon: 'none' });
                return;
            }
            if (!msg.includes('not completed') && !msg.includes('已完成')) {
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
