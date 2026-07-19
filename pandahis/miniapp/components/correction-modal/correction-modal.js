"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const correction_1 = require("../../native-utils/correction");
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
    },
    observers: {
        'visible, mode, reason, status, sourceType, submittedAt': function syncFields(visible, mode, reason, status, sourceType, submittedAt) {
            if (!visible)
                return;
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
        onSubmit() {
            if (this.properties.submitting)
                return;
            this.triggerEvent('submit', { reason: this.data.draftReason.trim() });
        },
    },
});
