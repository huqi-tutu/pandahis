"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const api_1 = require("../../native-utils/api");
const membership_benefits_1 = require("../../native-utils/membership-benefits");
const router_1 = require("../../native-utils/router");
const INVITE_PLAN_ID = 'invite_quarter';
Page({
    data: {
        plans: [],
        selectedId: INVITE_PLAN_ID,
        benefits: [...membership_benefits_1.MEMBERSHIP_BENEFITS],
        checkoutLine: '邀友获取 · 季卡 · ¥0',
        confirmText: '确认开通',
    },
    onShow() {
        if (!(0, api_1.hasToken)()) {
            (0, router_1.navigateTo)(router_1.ROUTES.login);
            return;
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
                    priceYuan: (quarter.priceCent / 100).toFixed(1),
                    priceCent: quarter.priceCent,
                });
            }
            if (year) {
                plans.push({
                    id: year.id,
                    kind: 'paid',
                    name: year.name || '年卡',
                    subtitle: '付费订阅',
                    priceYuan: (year.priceCent / 100).toFixed(1),
                    priceCent: year.priceCent,
                    tag: year.tagText || undefined,
                });
            }
            this.setData({ plans });
            this.syncSelection(INVITE_PLAN_ID);
        }
        catch (e) {
            wx.showToast({ title: (e === null || e === void 0 ? void 0 : e.message) || '加载失败', icon: 'none' });
        }
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
            confirmText: plan.kind === 'invite' ? '去邀友助力' : '确认开通',
        });
    },
    onConfirm() {
        const plan = this.data.plans.find((p) => p.id === this.data.selectedId);
        if (!plan)
            return;
        if (plan.kind === 'invite') {
            (0, router_1.navigateTo)(router_1.ROUTES.inviteAssist);
            return;
        }
        void this.createPaidOrder(plan.id);
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
                    success: () => wx.navigateBack(),
                });
                return;
            }
            wx.hideLoading();
            wx.showModal({
                title: '待接入微信支付',
                content: `订单 ${orderId} 已创建。正式环境将调起微信支付；当前可先使用「邀友获取」免费开通季卡。`,
                showCancel: false,
            });
        }
        catch (e) {
            wx.hideLoading();
            wx.showToast({ title: (e === null || e === void 0 ? void 0 : e.message) || '下单失败', icon: 'none' });
        }
    },
});
