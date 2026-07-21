"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const dictionary_1 = require("../../native-utils/dictionary");
function windowHeightPx() {
    try {
        const sys = wx.getSystemInfoSync();
        return sys.windowHeight || 667;
    }
    catch {
        return 667;
    }
}
function toEntryVm(entry) {
    return {
        ...entry,
        displayPinyin: entry.pinyin || '暂无读音',
    };
}
function formatDictionaryError(err) {
    const message = err instanceof Error ? err.message : '';
    if (/not found/i.test(message) || message === 'NOT_FOUND') {
        return '读音服务尚未上线到当前环境，请稍后重试';
    }
    if (message === 'UNAUTHORIZED') {
        return '需要登录后再查询';
    }
    return message || '查询失败，请稍后重试';
}
Component({
    properties: {
        visible: {
            type: Boolean,
            value: false,
        },
        query: {
            type: String,
            value: '',
        },
    },
    data: {
        loading: false,
        errorText: '',
        entries: [],
        cardMaxHeightPx: Math.floor(windowHeightPx() * 0.42),
    },
    observers: {
        'visible, query': function handleVisibleQuery(visible, query) {
            if (!visible) {
                this.setData({
                    loading: false,
                    errorText: '',
                    entries: [],
                });
                return;
            }
            const text = String(query || '').trim();
            if (!text) {
                this.setData({
                    loading: false,
                    errorText: '请先选中要查询的文字',
                    entries: [],
                });
                return;
            }
            this.fetchLookup(text);
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
        async fetchLookup(text) {
            this.setData({
                loading: true,
                errorText: '',
                entries: [],
            });
            try {
                const result = await (0, dictionary_1.lookupDictionary)(text);
                const entries = (result.entries || []).map(toEntryVm);
                this.setData({
                    loading: false,
                    entries,
                    errorText: entries.length === 0 ? '未找到可查询的汉字' : '',
                });
            }
            catch (err) {
                this.setData({
                    loading: false,
                    errorText: formatDictionaryError(err),
                    entries: [],
                });
            }
        },
    },
});
