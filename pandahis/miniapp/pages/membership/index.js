"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const api_1 = require("../../native-utils/api");
const membership_benefits_1 = require("../../native-utils/membership-benefits");
const router_1 = require("../../native-utils/router");
const INVITE_PLAN_ID = 'invite_quarter';
const FALLBACK_PLANS = [
    {
        id: INVITE_PLAN_ID,
        kind: 'invite',
        name: '季卡',
        subtitle: '邀友获取',
        priceYuan: '0',
        priceCent: 0,
        tag: '最划算',
    },
    {
        id: 'quarter',
        kind: 'paid',
        name: '季卡',
        subtitle: '付费订阅',
        priceYuan: '19.9',
        priceCent: 1990,
    },
    {
        id: 'year',
        kind: 'paid',
        name: '年卡',
        subtitle: '付费订阅',
        priceYuan: '49.9',
        priceCent: 4990,
    },
];
Page({
    data: {
        showBack: false,
        isTabPage: false,
        plans: [],
        selectedId: INVITE_PLAN_ID,
        benefits: [...membership_benefits_1.MEMBERSHIP_BENEFITS],
        checkoutLine: '邀友获取 · 季卡 · ¥0',
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
        const pages = getCurrentPages();
        const isTabPage = pages.length <= 1;
        this.setData({ showBack: !isTabPage, isTabPage });
        const tab = typeof this.getTabBar === 'function' ? this.getTabBar() : null;
        if (tab && typeof tab.setSelected === 'function') {
            ;
            tab.setSelected(2);
        }
        void this.loadPlans();
    },
    async loadPlans() {
        try {
            const res = await (0, api_1.request)('/membership/plans');
            const apiPlans = res.data.plans || [];
            const quarter = apiPlans.find((p) => p.id === 'quarter');
            const year = apiPlans.find((p) => p.id === 'year');
            const plans = [
                {
                    id: INVITE_PLAN_ID,
                    kind: 'invite',
                    name: '季卡',
                    subtitle: '邀友获取',
                    priceYuan: '0',
                    priceCent: 0,
                    tag: '最划算',
                },
            ];
            if (quarter) {
                plans.push({
                    id: quarter.id,
                    kind: 'paid',
                    name: quarter.name || '季卡',
                    subtitle: '付费订阅',
                    priceYuan: (quarter.priceCent / 100).toFixed(1).replace(/\.0$/, ''),
                    priceCent: quarter.priceCent,
                });
            }
            if (year) {
                plans.push({
                    id: year.id,
                    kind: 'paid',
                    name: year.name || '年卡',
                    subtitle: '付费订阅',
                    priceYuan: (year.priceCent / 100).toFixed(1).replace(/\.0$/, ''),
                    priceCent: year.priceCent,
                });
            }
            this.setData({ plans: plans.length >= 2 ? plans : FALLBACK_PLANS });
        }
        catch {
            this.setData({ plans: FALLBACK_PLANS });
        }
        this.syncSelection(this.data.selectedId || INVITE_PLAN_ID);
    },
    onSelectPlan(e) {
        const id = e.currentTarget.dataset.id;
        this.syncSelection(id);
    },
    syncSelection(id) {
        const plan = this.data.plans.find((p) => p.id === id);
        if (!plan)
            return;
        const checkoutLine = plan.kind === 'invite'
            ? `邀友获取 · ${plan.name} · ¥${plan.priceYuan}`
            : `付费订阅 · ${plan.name} · ¥${plan.priceYuan}`;
        this.setData({
            selectedId: id,
            checkoutLine,
        });
    },
    requireLogin(next) {
        if ((0, api_1.hasToken)()) {
            next();
            return;
        }
        wx.showModal({
            title: '需要登录',
            content: '登录后可开通会员或发起好友助力',
            confirmText: '去登录',
            success: (r) => {
                if (r.confirm)
                    (0, router_1.navigateTo)(router_1.ROUTES.login);
            },
        });
    },
    onConfirm() {
        this.requireLogin(() => {
            const plan = this.data.plans.find((p) => p.id === this.data.selectedId);
            if (!plan)
                return;
            if (plan.kind === 'invite') {
                (0, router_1.navigateTo)(router_1.ROUTES.inviteAssist);
                return;
            }
            void this.createPaidOrder(plan.id);
        });
    },
    async createPaidOrder(planId) {
        try {
            wx.showLoading({ title: '创建订单…', mask: true });
            const res = await (0, api_1.request)('/orders', {
                method: 'POST',
                auth: true,
                data: { planId },
            });
            const { orderId, payParams } = res.data;
            const isMockPay = (payParams === null || payParams === void 0 ? void 0 : payParams.paySign) === 'mock-sign' ||
                String((payParams === null || payParams === void 0 ? void 0 : payParams.package) || '').includes('mock');
            if (isMockPay) {
                await (0, api_1.request)('/payments/wechat/notify', {
                    method: 'POST',
                    data: {
                        orderId,
                        wxTransactionId: `mock-wx-${orderId}-${Date.now()}`,
                        paidAt: new Date().toISOString(),
                    },
                });
                wx.hideLoading();
                wx.showModal({
                    title: '开通成功',
                    content: `订单 ${orderId} 已完成支付（开发环境模拟），会员权益已生效。`,
                    showCancel: false,
                });
                return;
            }
            wx.hideLoading();
            wx.showModal({
                title: '待接入微信支付',
                content: `订单 ${orderId} 已创建。正式环境将调起微信支付；也可选择「邀友获取」免费开通季卡。`,
                showCancel: false,
            });
        }
        catch (e) {
            wx.hideLoading();
            const msg = e instanceof Error ? e.message : '下单失败';
            wx.showToast({ title: msg, icon: 'none' });
        }
    },
});
