"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const api_1 = require("../../native-utils/api");
const note_1 = require("../../native-utils/note");
const nav_metrics_1 = require("../../native-utils/nav-metrics");
const router_1 = require("../../native-utils/router");
const EMPTY_DETAIL = {
    id: 0,
    boxId: '',
    boxTitle: '',
    boxCategoryKey: '',
    boxCategoryName: '',
    civilizationName: '',
    dynastyName: '',
    regimeName: '',
    emperorName: '',
    coordinateText: '',
    sourceType: 'box_detail_selection',
    selectedText: '',
    noteText: '',
    createdAt: '',
};
Page({
    data: {
        hasToken: false,
        loaded: false,
        noteId: 0,
        detail: EMPTY_DETAIL,
        sourceLabel: '',
        createdAtLabel: '',
        remarkLabel: (0, note_1.noteRemarkLabel)(''),
        emptyRemark: true,
        canViewSource: false,
        editVisible: false,
        submitting: false,
        pageTopPadPx: 88,
    },
    onLoad(query) {
        try {
            this.setData({ pageTopPadPx: (0, nav_metrics_1.computePageTopPadPx)() });
        }
        catch {
            this.setData({ pageTopPadPx: 88 });
        }
        this.setData({ noteId: Number(query.id || 0) });
    },
    onShow() {
        const ok = (0, api_1.hasToken)();
        this.setData({ hasToken: ok });
        if (ok)
            void this.load();
        else
            this.setData({ loaded: true, detail: EMPTY_DETAIL });
    },
    goLogin() {
        (0, router_1.navigateTo)(router_1.ROUTES.login);
    },
    applyDetail(detail) {
        const remark = String(detail.noteText || '').trim();
        this.setData({
            detail,
            loaded: true,
            sourceLabel: (0, note_1.noteSourceLabel)(detail.sourceType),
            createdAtLabel: (0, note_1.formatNoteTime)(detail.createdAt),
            remarkLabel: (0, note_1.noteRemarkLabel)(remark),
            emptyRemark: !remark,
            canViewSource: !('error' in (0, note_1.resolveNoteSourceNav)(detail)),
        });
    },
    async load() {
        const id = this.data.noteId;
        if (!id) {
            this.setData({ loaded: true, detail: EMPTY_DETAIL });
            return;
        }
        try {
            const detail = await (0, note_1.fetchNoteDetail)(id);
            this.applyDetail(detail);
        }
        catch {
            this.setData({ loaded: true, detail: EMPTY_DETAIL });
        }
    },
    onViewSource() {
        const detail = this.data.detail;
        if (!detail.id || !this.data.canViewSource)
            return;
        (0, note_1.navigateToNoteSource)(detail);
    },
    onEdit() {
        this.setData({ editVisible: true, submitting: false });
    },
    closeEdit() {
        this.setData({ editVisible: false, submitting: false });
    },
    async onEditSubmit(e) {
        var _a;
        const noteText = String(((_a = e.detail) === null || _a === void 0 ? void 0 : _a.noteText) || '');
        const id = this.data.noteId;
        if (!id || this.data.submitting)
            return;
        this.setData({ submitting: true });
        try {
            const detail = await (0, note_1.updateNote)(id, noteText);
            this.setData({ editVisible: false, submitting: false });
            this.applyDetail(detail);
            wx.showToast({ title: '已保存', icon: 'success' });
        }
        catch (err) {
            this.setData({ submitting: false });
            const msg = err instanceof Error ? err.message : '保存失败';
            wx.showToast({ title: msg, icon: 'none' });
        }
    },
    onDelete() {
        const id = this.data.noteId;
        if (!id)
            return;
        wx.showModal({
            title: '删除笔记',
            content: '删除后划线也会一起去掉，确定删除？',
            confirmText: '删除',
            success: (r) => {
                if (r.confirm)
                    void this.doDelete(id);
            },
        });
    },
    async doDelete(id) {
        try {
            await (0, note_1.deleteNote)(id);
            wx.showToast({ title: '已删除', icon: 'success' });
            setTimeout(() => wx.navigateBack(), 400);
        }
        catch (err) {
            const msg = err instanceof Error ? err.message : '删除失败';
            wx.showToast({ title: msg, icon: 'none' });
        }
    },
});
