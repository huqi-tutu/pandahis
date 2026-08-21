Component({
    properties: {
        visible: {
            type: Boolean,
            value: false,
        },
        left: {
            type: Number,
            value: 0,
        },
        top: {
            type: Number,
            value: 0,
        },
        placement: {
            type: String,
            value: 'above',
        },
        /** 为 false 时隐藏分享（评述/见证详情页） */
        showShare: {
            type: Boolean,
            value: true,
        },
        /** 为 false 时隐藏笔记（母本原文半屏） */
        showNote: {
            type: Boolean,
            value: true,
        },
    },
    methods: {
        noop() { },
        onCopy() {
            this.triggerEvent('copy');
        },
        onShare() {
            this.triggerEvent('share');
        },
        onQuery() {
            this.triggerEvent('query');
        },
        onNote() {
            this.triggerEvent('note');
        },
        onCorrection() {
            this.triggerEvent('correction');
        },
    },
});
