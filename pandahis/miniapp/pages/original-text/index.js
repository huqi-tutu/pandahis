"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const api_1 = require("../../native-utils/api");
const encode_path_segment_1 = require("../../native-utils/encode-path-segment");
const router_1 = require("../../native-utils/router");
const nav_metrics_1 = require("../../native-utils/nav-metrics");
/** 与后端约定一致：占位 `{}` / `[]` 视为无原文 */
function isRefMeaningless(ref) {
    if (ref == null)
        return true;
    if (Array.isArray(ref))
        return ref.length === 0;
    if (typeof ref === 'object')
        return Object.keys(ref).length === 0;
    return false;
}
function parseOriginalRef(ref) {
    var _a, _b, _c, _d, _e;
    if (isRefMeaningless(ref))
        return null;
    if (typeof ref === 'string') {
        const t = ref.trim();
        return t ? { title: '母本原文', sourceWork: '', items: [], fallback: t } : null;
    }
    if (typeof ref !== 'object' || ref === null)
        return null;
    const o = ref;
    const title = typeof o.title === 'string' && o.title.trim() ? o.title.trim() : '母本原文';
    const sourceWork = (typeof o.sourceWork === 'string' ? o.sourceWork.trim() : '') ||
        (typeof o.primarySource === 'string' ? o.primarySource.trim() : '');
    const textField = (typeof o.text === 'string' ? o.text.trim() : '') ||
        (typeof o.originalText === 'string' ? o.originalText.trim() : '');
    if (textField) {
        return { title, sourceWork, items: [], fallback: textField };
    }
    if (Array.isArray(o.paragraphs)) {
        const parts = [];
        for (const p of o.paragraphs) {
            if (typeof p === 'string' && p.trim())
                parts.push(p.trim());
            else if (p && typeof p === 'object') {
                const t = String((_a = p.text) !== null && _a !== void 0 ? _a : '').trim();
                if (t)
                    parts.push(t);
            }
        }
        if (parts.length)
            return { title, sourceWork, items: [], fallback: parts.join('\n') };
    }
    const rawItems = o.items;
    const items = [];
    if (Array.isArray(rawItems)) {
        for (const it of rawItems) {
            if (!it || typeof it !== 'object')
                continue;
            const x = it;
            items.push({
                work: String((_b = x.work) !== null && _b !== void 0 ? _b : '').trim(),
                chapter: String((_c = x.chapter) !== null && _c !== void 0 ? _c : '').trim(),
                excerpt: String((_d = x.excerpt) !== null && _d !== void 0 ? _d : '')
                    .trim()
                    .replace(/\\r\\n/g, '\n')
                    .replace(/\\n/g, '\n'),
                url: String((_e = x.url) !== null && _e !== void 0 ? _e : '').trim(),
            });
        }
    }
    const hasStructured = items.some((i) => i.work || i.chapter || i.excerpt || i.url);
    if (!hasStructured)
        return null;
    return { title, sourceWork, items, fallback: '' };
}
Page({
    data: {
        empty: true,
        refTitle: '',
        refSourceWork: '',
        refItems: [],
        refFallback: '',
        pageTopPadPx: 88,
    },
    async onLoad(query) {
        try {
            this.setData({ pageTopPadPx: (0, nav_metrics_1.computePageTopPadPx)() });
        }
        catch {
            this.setData({ pageTopPadPx: 88 });
        }
        const boxId = query.boxId || query.id;
        if (!boxId) {
            this.setData({ empty: true, refTitle: '', refItems: [], refFallback: '' });
            return;
        }
        try {
            const res = await (0, api_1.request)(`/boxes/${(0, encode_path_segment_1.encodePathSegment)(boxId)}/original-ref`, {
                auth: (0, api_1.hasToken)(),
            });
            const parsed = parseOriginalRef(res.data.originalRef);
            if (!parsed) {
                this.setData({ empty: true, refTitle: '', refSourceWork: '', refItems: [], refFallback: '' });
                return;
            }
            const hasContent = parsed.items.length > 0 || parsed.fallback.length > 0;
            this.setData({
                empty: !hasContent,
                refTitle: parsed.title,
                refSourceWork: parsed.sourceWork,
                refItems: parsed.items,
                refFallback: parsed.fallback,
            });
        }
        catch (e) {
            const msg = String((e === null || e === void 0 ? void 0 : e.message) || '');
            if (msg.includes('INSUFFICIENT_READS') || msg.includes('NEED_MEMBERSHIP_OR_READS')) {
                wx.showModal({
                    title: '需要会员或阅读点',
                    content: '开通会员可免扣点阅读；也可去会员页邀友助力或查看阅读点。',
                    confirmText: '去开通',
                    success: (r) => {
                        if (r.confirm)
                            wx.switchTab({ url: router_1.ROUTES.membership });
                    },
                });
            }
            else if (msg === 'UNAUTHORIZED' || msg.includes('login required')) {
                wx.showModal({
                    title: '需要登录',
                    content: '登录后可开通会员或使用阅读点查看原文对照。',
                    confirmText: '去登录',
                    success: (r) => {
                        if (r.confirm)
                            (0, router_1.navigateTo)(router_1.ROUTES.login);
                    },
                });
            }
            else {
                wx.showToast({ title: (e === null || e === void 0 ? void 0 : e.message) || '加载失败', icon: 'none' });
            }
            this.setData({ empty: true, refTitle: '', refSourceWork: '', refItems: [], refFallback: '' });
        }
    },
    copyLink(e) {
        const url = e.currentTarget.dataset.url;
        if (!url)
            return;
        wx.setClipboardData({
            data: url,
            success: () => wx.showToast({ title: '链接已复制', icon: 'none' }),
        });
    },
});
