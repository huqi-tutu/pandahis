"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const api_1 = require("../../native-utils/api");
const feedback_1 = require("../../native-utils/feedback");
const nav_metrics_1 = require("../../native-utils/nav-metrics");
const router_1 = require("../../native-utils/router");
Page({
    data: {
        pageTopPadPx: 88,
        keyboardPadPx: 0,
        typeOptions: feedback_1.FEEDBACK_TYPES.map((x) => ({ ...x })),
        feedbackType: 'feature',
        content: '',
        contentLength: 0,
        contentMax: feedback_1.FEEDBACK_CONTENT_MAX,
        images: [],
        imageMax: feedback_1.FEEDBACK_IMAGE_MAX,
        dailyLimit: feedback_1.FEEDBACK_DAILY_LIMIT,
        canSubmit: false,
        submitting: false,
    },
    onLoad() {
        try {
            this.setData({ pageTopPadPx: (0, nav_metrics_1.computePageTopPadPx)() });
        }
        catch {
            this.setData({ pageTopPadPx: 88 });
        }
        this.ensureLogin({ replace: true });
    },
    onShow() {
        this.ensureLogin({ replace: false });
    },
    ensureLogin(opts) {
        if ((0, api_1.hasToken)())
            return true;
        wx.showModal({
            title: '需要登录',
            content: '登录后可提交帮助与反馈。',
            showCancel: false,
            success: () => {
                if (opts.replace)
                    (0, router_1.redirectTo)(router_1.ROUTES.login);
                else
                    (0, router_1.navigateTo)(router_1.ROUTES.login);
            },
        });
        return false;
    },
    onTypeTap(e) {
        const value = String(e.currentTarget.dataset.value || '');
        if (!value || value === this.data.feedbackType)
            return;
        this.setData({ feedbackType: value });
    },
    onContentInput(e) {
        const content = String(e.detail.value || '');
        this.setData({
            content,
            contentLength: content.length,
            canSubmit: content.trim().length > 0 && !this.data.submitting,
        });
    },
    onPickImages() {
        if (!this.ensureLogin({ replace: false }))
            return;
        const remain = feedback_1.FEEDBACK_IMAGE_MAX - this.data.images.length;
        if (remain <= 0)
            return;
        wx.chooseMedia({
            count: remain,
            mediaType: ['image'],
            sourceType: ['album'],
            sizeType: ['compressed'],
            success: (res) => {
                const picked = (res.tempFiles || [])
                    .map((f) => f.tempFilePath)
                    .filter(Boolean)
                    .map((localPath) => ({ localPath }));
                if (!picked.length)
                    return;
                this.setData({ images: [...this.data.images, ...picked].slice(0, feedback_1.FEEDBACK_IMAGE_MAX) });
            },
        });
    },
    onRemoveImage(e) {
        const index = Number(e.currentTarget.dataset.index);
        if (!Number.isFinite(index))
            return;
        const images = this.data.images.filter((_, i) => i !== index);
        this.setData({ images });
    },
    onPreview(e) {
        const index = Number(e.currentTarget.dataset.index);
        const urls = this.data.images.map((x) => x.localPath);
        if (!urls.length)
            return;
        wx.previewImage({
            current: urls[index] || urls[0],
            urls,
        });
    },
    async onSubmit() {
        if (this.data.submitting)
            return;
        if (!this.ensureLogin({ replace: false }))
            return;
        const content = (this.data.content || '').trim();
        if (!content) {
            wx.showToast({ title: '请填写问题描述', icon: 'none' });
            return;
        }
        if (content.length > feedback_1.FEEDBACK_CONTENT_MAX) {
            wx.showToast({ title: `最多 ${feedback_1.FEEDBACK_CONTENT_MAX} 字`, icon: 'none' });
            return;
        }
        this.setData({ submitting: true, canSubmit: false });
        wx.showLoading({ title: '提交中', mask: true });
        try {
            const images = [...this.data.images];
            const imageUrls = [];
            for (let i = 0; i < images.length; i += 1) {
                const img = images[i];
                if (img.remoteUrl) {
                    imageUrls.push(img.remoteUrl);
                    continue;
                }
                const url = await (0, feedback_1.uploadFeedbackImage)(img.localPath);
                images[i] = { ...img, remoteUrl: url };
                this.setData({ images: [...images] });
                imageUrls.push(url);
            }
            await (0, feedback_1.submitFeedback)({
                feedbackType: this.data.feedbackType,
                content,
                imageUrls,
            });
            wx.hideLoading();
            wx.showToast({ title: '已提交', icon: 'success' });
            setTimeout(() => wx.navigateBack({ fail: () => (0, router_1.navigateTo)(router_1.ROUTES.settings) }), 500);
        }
        catch (err) {
            wx.hideLoading();
            const msg = err instanceof Error ? err.message : '提交失败';
            wx.showToast({
                title: msg.length > 20 ? `${msg.slice(0, 18)}…` : msg,
                icon: 'none',
            });
        }
        finally {
            this.setData({
                submitting: false,
                canSubmit: (this.data.content || '').trim().length > 0,
            });
        }
    },
});
