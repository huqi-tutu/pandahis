"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const dictionary_1 = require("../../native-utils/dictionary");
const dictionary_sheet_layout_1 = require("../../native-utils/dictionary-sheet-layout");
const HAN_CHAR_RE = /[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF]/;
const EMPTY_LAYOUT = (0, dictionary_sheet_layout_1.computeDictionarySheetLayout)(0);
function extractHanChars(text) {
    return Array.from(text).filter((ch) => HAN_CHAR_RE.test(ch));
}
function toEntryVm(entry, index, fallbackChars) {
    const displayCharacter = String(entry.character || '').trim() || fallbackChars[index] || '';
    return {
        displayCharacter,
        displayPinyin: entry.pinyin || '暂无读音',
        pinyin: entry.pinyin,
    };
}
function toEntries(result, query) {
    const fallbackChars = extractHanChars(query);
    const raw = result.entries || [];
    if (raw.length > 0) {
        return raw.map((entry, index) => toEntryVm(entry, index, fallbackChars));
    }
    return fallbackChars.map((ch, index) => toEntryVm({ character: ch, pinyin: null }, index, fallbackChars));
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
        layout: EMPTY_LAYOUT,
    },
    observers: {
        'visible, query': function handleVisibleQuery(visible, query) {
            if (!visible) {
                this.setData({
                    loading: false,
                    errorText: '',
                    entries: [],
                    layout: EMPTY_LAYOUT,
                });
                return;
            }
            const text = String(query || '').trim();
            if (!text) {
                this.setData({
                    loading: false,
                    errorText: '请先选中要查询的文字',
                    entries: [],
                    layout: EMPTY_LAYOUT,
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
                layout: EMPTY_LAYOUT,
            });
            try {
                const result = await (0, dictionary_1.lookupDictionary)(text);
                const entries = toEntries(result, text);
                const layout = (0, dictionary_sheet_layout_1.computeDictionarySheetLayout)(entries.length);
                this.setData({
                    loading: false,
                    entries,
                    layout,
                    errorText: entries.length === 0 ? '未找到可查询的汉字' : '',
                });
            }
            catch (err) {
                this.setData({
                    loading: false,
                    errorText: formatDictionaryError(err),
                    entries: [],
                    layout: EMPTY_LAYOUT,
                });
            }
        },
    },
});
