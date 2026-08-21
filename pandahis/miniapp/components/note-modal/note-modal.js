"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const note_1 = require("../../native-utils/note");
const composer_sheet_layout_1 = require("../../native-utils/composer-sheet-layout");
function sheetPatch(component, override = {}) {
    var _a, _b, _c, _d;
    const metrics = (0, composer_sheet_layout_1.readComposerSheetMetrics)();
    const quoteExpanded = (_a = override.quoteExpanded) !== null && _a !== void 0 ? _a : Boolean(component.data.quoteExpanded);
    const restWindowHeight = override.restWindowHeight ||
        Number(component.data.restWindowHeight) ||
        metrics.windowHeight;
    const vm = (0, composer_sheet_layout_1.composerSheetViewModel)({
        ...metrics,
        keyboardHeight: (_b = override.keyboardHeight) !== null && _b !== void 0 ? _b : (Math.max(0, Number(component.data.keyboardHeight) || 0)),
        restWindowHeight,
        mode: String((_c = override.mode) !== null && _c !== void 0 ? _c : (component.properties.mode || 'edit')),
        selectedText: String((_d = override.selectedText) !== null && _d !== void 0 ? _d : (component.properties.selectedText || '')),
        quoteExpanded,
    });
    return {
        ...vm,
        quoteExpanded,
        restWindowHeight,
    };
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
        boxTitle: {
            type: String,
            value: '',
        },
        civilizationName: {
            type: String,
            value: '',
        },
        dynastyName: {
            type: String,
            value: '',
        },
        selectedText: {
            type: String,
            value: '',
        },
        noteText: {
            type: String,
            value: '',
        },
        submitting: {
            type: Boolean,
            value: false,
        },
    },
    data: {
        draftNote: '',
        remarkDisplay: (0, note_1.noteRemarkLabel)(''),
        keyboardHeight: 0,
        keyboardOpen: false,
        keyboardLiftPx: 0,
        restWindowHeight: 0,
        cardStyle: '',
        bodyStyle: '',
        textareaHeightPx: 110,
        quoteExpanded: false,
        quoteMaxLines: 0,
        quoteClampClass: '',
        quoteClampStyle: '',
        showQuoteToggle: false,
        quoteToggleLabel: '展开',
        sheetOpen: false,
        coordinateText: '',
    },
    lifetimes: {
        attached() {
            this._onKeyboardHeight = (res) => {
                if (!this.properties.visible)
                    return;
                const height = Math.max(0, Math.floor(Number(res === null || res === void 0 ? void 0 : res.height) || 0));
                this.setData(sheetPatch(this, { keyboardHeight: height }));
            };
            if (typeof wx.onKeyboardHeightChange === 'function') {
                wx.onKeyboardHeightChange(this._onKeyboardHeight);
            }
        },
        detached() {
            if (this._onKeyboardHeight && typeof wx.offKeyboardHeightChange === 'function') {
                wx.offKeyboardHeightChange(this._onKeyboardHeight);
            }
        },
    },
    observers: {
        'visible, mode, noteText, selectedText, civilizationName, dynastyName, boxTitle': function syncFields(visible, mode, noteText, selectedText, civilizationName, dynastyName, boxTitle) {
            const metrics = (0, composer_sheet_layout_1.readComposerSheetMetrics)();
            const coordinateText = (0, composer_sheet_layout_1.formatSheetCoordinate)(civilizationName, dynastyName, boxTitle);
            if (!visible) {
                this.setData({
                    remarkDisplay: (0, note_1.noteRemarkLabel)(noteText),
                    coordinateText,
                    sheetOpen: false,
                    ...sheetPatch(this, {
                        keyboardHeight: 0,
                        quoteExpanded: false,
                        restWindowHeight: metrics.windowHeight,
                        mode,
                        selectedText,
                    }),
                });
                return;
            }
            const opening = !this.data.sheetOpen;
            const patch = {
                remarkDisplay: (0, note_1.noteRemarkLabel)(noteText),
                coordinateText,
                sheetOpen: true,
                ...sheetPatch(this, {
                    keyboardHeight: opening ? 0 : this.data.keyboardHeight,
                    quoteExpanded: opening ? false : this.data.quoteExpanded,
                    restWindowHeight: opening ? metrics.windowHeight : this.data.restWindowHeight,
                    mode,
                    selectedText,
                }),
            };
            if (mode === 'edit') {
                patch.draftNote = String(noteText || '').slice(0, note_1.NOTE_TEXT_MAX);
            }
            this.setData(patch);
        },
    },
    methods: {
        noop() { },
        hideKeyboard() {
            if (!this.data.keyboardOpen)
                return;
            if (typeof wx.hideKeyboard === 'function')
                wx.hideKeyboard();
        },
        onSheetTap() {
            this.hideKeyboard();
        },
        onBackdropTap() {
            if (this.data.keyboardOpen) {
                this.hideKeyboard();
                return;
            }
            this.triggerEvent('close');
        },
        onClose() {
            this.triggerEvent('close');
        },
        onNoteInput(e) {
            const value = String(e.detail.value || '').slice(0, note_1.NOTE_TEXT_MAX);
            this.setData({ draftNote: value });
        },
        onToggleQuote() {
            if (this.data.keyboardOpen)
                return;
            this.setData(sheetPatch(this, { quoteExpanded: !this.data.quoteExpanded }));
        },
        onKeyboardHeightChange(e) {
            var _a;
            const height = Math.max(0, Math.floor(Number((_a = e.detail) === null || _a === void 0 ? void 0 : _a.height) || 0));
            this.setData(sheetPatch(this, { keyboardHeight: height }));
        },
        onSubmit() {
            if (this.properties.submitting)
                return;
            this.triggerEvent('submit', { noteText: String(this.data.draftNote || '').trim() });
        },
    },
});
