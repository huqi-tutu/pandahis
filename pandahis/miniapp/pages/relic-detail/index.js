"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const api_1 = require("../../native-utils/api");
const correction_1 = require("../../native-utils/correction");
const encode_path_segment_1 = require("../../native-utils/encode-path-segment");
const nav_metrics_1 = require("../../native-utils/nav-metrics");
const selection_bar_position_1 = require("../../native-utils/selection-bar-position");
const SOURCE_TYPE = 'relic_detail_selection';
Page({
    data: {
        relicId: 0,
        navTitle: '',
        name: '',
        museum: '',
        detail: '',
        imageUrl: '',
        boxId: '',
        boxTitle: '',
        civilizationName: '',
        dynastyName: '',
        pageTopPadPx: 88,
        selectionBarVisible: false,
        selectionBarLeft: 0,
        selectionBarTop: 0,
        selectionBarPlacement: 'above',
        selectionBarText: '',
        selectionMountKey: 1,
        dictionaryVisible: false,
        dictionaryQuery: '',
        correctionVisible: false,
        correctionSubmitting: false,
        correctionSelectedText: '',
    },
    _selectionContext: null,
    async onLoad(query) {
        try {
            this.setData({ pageTopPadPx: (0, nav_metrics_1.computePageTopPadPx)() });
        }
        catch {
            this.setData({ pageTopPadPx: 88 });
        }
        const relicId = Number(query.relicId || 0);
        if (relicId > 0) {
            this.setData({ relicId });
            await this.loadById(relicId);
            return;
        }
        const name = decodeURIComponent(query.name || '');
        const navTitle = decodeURIComponent(query.navTitle || '') || name || '见证';
        const boxTitle = decodeURIComponent(query.boxTitle || '') || navTitle.replace(/・见证$/, '') || name;
        this.setData({
            navTitle,
            name,
            museum: decodeURIComponent(query.museum || ''),
            detail: decodeURIComponent(query.detail || ''),
            imageUrl: decodeURIComponent(query.imageUrl || ''),
            boxId: decodeURIComponent(query.boxId || ''),
            boxTitle,
            civilizationName: decodeURIComponent(query.civilizationName || ''),
            dynastyName: decodeURIComponent(query.dynastyName || ''),
        });
    },
    async loadById(relicId) {
        try {
            wx.showLoading({ title: '加载中', mask: true });
            const res = await (0, api_1.request)(`/relics/${(0, encode_path_segment_1.encodePathSegment)(String(relicId))}`);
            wx.hideLoading();
            const d = res.data || {};
            const boxTitle = String(d.boxTitle || '').trim();
            const name = String(d.name || '').trim();
            this.setData({
                relicId,
                boxId: String(d.boxId || '').trim(),
                boxTitle,
                civilizationName: String(d.civilizationName || '').trim(),
                dynastyName: String(d.dynastyName || '').trim(),
                navTitle: boxTitle ? `${boxTitle}・见证` : '见证',
                name,
                museum: String(d.museum || '').trim(),
                detail: String(d.description || d.summary || '').trim(),
                imageUrl: String(d.imageUrl || '').trim(),
            });
        }
        catch (err) {
            wx.hideLoading();
            const msg = err instanceof Error ? err.message : '加载失败';
            wx.showToast({ title: msg, icon: 'none' });
        }
    },
    onReady() {
        this.bindBodySelectionContext();
    },
    bindBodySelectionContext() {
        wx.createSelectorQuery()
            .in(this)
            .select('#relicBodySelection')
            .context((res) => {
            var _a;
            this._selectionContext = (_a = res === null || res === void 0 ? void 0 : res.context) !== null && _a !== void 0 ? _a : null;
        })
            .exec();
    },
    clearBodySelection() {
        const ctx = this._selectionContext;
        if (ctx && typeof ctx.removeSelection === 'function') {
            try {
                ctx.removeSelection();
                return;
            }
            catch {
                // fallback below
            }
        }
        this.setData({ selectionMountKey: this.data.selectionMountKey + 1 }, () => {
            this.bindBodySelectionContext();
        });
    },
    hideSelectionBar() {
        this.setData({
            selectionBarVisible: false,
            selectionBarText: '',
        });
        this.clearBodySelection();
    },
    onPageTap() {
        if (this.data.selectionBarVisible)
            this.hideSelectionBar();
    },
    onDetailSelectionChange(e) {
        const detail = (e.detail || {});
        const selected = String(detail.selectedString || '').trim();
        if (detail.isCollapsed || !selected) {
            this.hideSelectionBar();
            return;
        }
        const anchor = (0, selection_bar_position_1.resolveSelectionBarAnchor)(detail.firstRangeRect, {
            left: this.data.selectionBarLeft,
            top: this.data.selectionBarTop,
            placement: this.data.selectionBarPlacement,
        }, { buttonCount: 3 });
        this.setData({
            selectionBarVisible: true,
            selectionBarText: selected,
            selectionBarLeft: anchor.left,
            selectionBarTop: anchor.top,
            selectionBarPlacement: anchor.placement,
        });
    },
    onSelectionCopy() {
        const text = this.data.selectionBarText;
        this.hideSelectionBar();
        if (!text)
            return;
        wx.setClipboardData({
            data: text,
            success: () => wx.showToast({ title: '已复制', icon: 'success' }),
        });
    },
    onSelectionQuery() {
        const text = this.data.selectionBarText;
        this.hideSelectionBar();
        if (!text)
            return;
        this.clearBodySelection();
        this.setData({
            dictionaryVisible: true,
            dictionaryQuery: text,
        });
    },
    closeDictionary() {
        this.setData({ dictionaryVisible: false, dictionaryQuery: '' });
        this.clearBodySelection();
    },
    onSelectionCorrection() {
        const text = this.data.selectionBarText;
        this.hideSelectionBar();
        if (!text)
            return;
        (0, correction_1.requireLoginForCorrection)(() => {
            this.setData({
                correctionVisible: true,
                correctionSubmitting: false,
                correctionSelectedText: text,
            });
        });
    },
    closeCorrection() {
        this.setData({ correctionVisible: false, correctionSubmitting: false });
        this.clearBodySelection();
    },
    async onCorrectionSubmit(e) {
        var _a;
        const reason = String(((_a = e.detail) === null || _a === void 0 ? void 0 : _a.reason) || '');
        const boxId = this.data.boxId;
        const relicId = Number(this.data.relicId || 0);
        if (!boxId || this.data.correctionSubmitting) {
            if (!boxId)
                wx.showToast({ title: '缺少史略信息，无法提交', icon: 'none' });
            return;
        }
        if (!(relicId > 0)) {
            wx.showToast({ title: '缺少见证信息，无法提交', icon: 'none' });
            return;
        }
        this.setData({ correctionSubmitting: true });
        try {
            await (0, correction_1.submitCorrection)({
                boxId,
                sourceType: SOURCE_TYPE,
                reason,
                selectedText: this.data.correctionSelectedText,
                sourceRefId: relicId,
            });
            wx.showToast({ title: '提交成功，感谢反馈', icon: 'success' });
            this.setData({ correctionVisible: false, correctionSubmitting: false });
        }
        catch (err) {
            this.setData({ correctionSubmitting: false });
            const msg = err instanceof Error ? err.message : '提交失败，请稍后重试';
            wx.showToast({ title: msg, icon: 'none' });
        }
    },
});
