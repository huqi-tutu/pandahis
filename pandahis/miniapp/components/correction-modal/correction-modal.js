"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const correction_1 = require("../../native-utils/correction");
function windowHeightPx() {
    try {
        const sys = wx.getSystemInfoSync();
        return sys.windowHeight || 667;
    }
    catch {
        return 667;
    }
}
Component({
    properties: {
        visible: {
            type: Boolean,
            value: false,
        },
        mode: {
            type: String,
            value: 'edit',
        },
        civilizationName: {
            type: String,
            value: '',
        },
        dynastyName: {
            type: String,
            value: '',
        },
        boxTitle: {
            type: String,
            value: '',
        },
        selectedText: {
            type: String,
            value: '',
        },
        reason: {
            type: String,
            value: '',
        },
        status: {
            type: String,
            value: 'pending',
        },
        sourceType: {
            type: String,
            value: '',
        },
        submittedAt: {
            type: String,
            value: '',
        },
        submitting: {
            type: Boolean,
            value: false,
        },
    },
    data: {
        draftReason: '',
        sourceLabel: '',
        statusLabel: '',
        reasonDisplay: '（未填写）',
        submittedAtDisplay: '',
        keyboardHeight: 0,
        cardMaxHeightPx: Math.floor(windowHeightPx() * 0.85),
        scrollIntoView: '',
    },
    observers: {
        'visible, mode, reason, status, sourceType, submittedAt': function syncFields(visible, mode, reason, status, sourceType, submittedAt) {
            if (!visible) {
                this.setData({
                    keyboardHeight: 0,
                    cardMaxHeightPx: Math.floor(windowHeightPx() * 0.85),
                    scrollIntoView: '',
                });
                return;
            }
            const patch = {
                sourceLabel: (0, correction_1.correctionSourceLabel)(sourceType),
                statusLabel: (0, correction_1.correctionStatusLabel)(status),
                reasonDisplay: (reason || '').trim() || '（未填写）',
                submittedAtDisplay: (0, correction_1.formatCorrectionTime)(submittedAt),
            };
            if (mode === 'edit') {
                patch.draftReason = (reason || '').slice(0, 500);
            }
            this.setData(patch);
        },
    },
    methods: {
        noop() { },
        onBackdropTap() {
            this.triggerEvent('close');
        },
        onClose() {
            this.triggerEvent('close');
        },
        onReasonInput(e) {
            const value = String(e.detail.value || '').slice(0, 500);
            this.setData({ draftReason: value });
        },
        onReasonFocus() {
            this.setData({ scrollIntoView: 'correction-reason-field' });
        },
        onKeyboardHeightChange(e) {
            var _a;
            const height = Math.max(0, Math.floor(Number((_a = e.detail) === null || _a === void 0 ? void 0 : _a.height) || 0));
            const winH = windowHeightPx();
            const maxH = height > 0 ? Math.max(280, winH - height - 12) : Math.floor(winH * 0.85);
            this.setData({
                keyboardHeight: height,
                cardMaxHeightPx: maxH,
                scrollIntoView: height > 0 ? 'correction-reason-field' : '',
            });
        },
        onSubmit() {
            if (this.properties.submitting)
                return;
            this.triggerEvent('submit', { reason: this.data.draftReason.trim() });
        },
    },
});
