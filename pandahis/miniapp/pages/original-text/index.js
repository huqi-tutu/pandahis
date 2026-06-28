"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const api_1 = require("../../native-utils/api");
const encode_path_segment_1 = require("../../native-utils/encode-path-segment");
const router_1 = require("../../native-utils/router");
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
    var _a, _b, _c, _d;
    if (isRefMeaningless(ref))
        return null;
    if (typeof ref === 'string') {
        const t = ref.trim();
        return t ? { title: '原文', items: [], fallback: t } : null;
    }
    if (typeof ref !== 'object' || ref === null)
        return null;
    const o = ref;
    const title = typeof o.title === 'string' && o.title.trim() ? o.title.trim() : '史料原文';
    const rawItems = o.items;
    const items = [];
    if (Array.isArray(rawItems)) {
        for (const it of rawItems) {
            if (!it || typeof it !== 'object')
                continue;
            const x = it;
            items.push({
                work: String((_a = x.work) !== null && _a !== void 0 ? _a : '').trim(),
                chapter: String((_b = x.chapter) !== null && _b !== void 0 ? _b : '').trim(),
                excerpt: String((_c = x.excerpt) !== null && _c !== void 0 ? _c : '')
                    .trim()
                    .replace(/\\r\\n/g, '\n')
                    .replace(/\\n/g, '\n'),
                url: String((_d = x.url) !== null && _d !== void 0 ? _d : '').trim(),
            });
        }
    }
    const hasStructured = items.some((i) => i.work || i.chapter || i.excerpt || i.url);
    if (!hasStructured) {
        try {
            const fallback = JSON.stringify(ref, null, 2);
            return { title, items: [], fallback };
        }
        catch {
            return { title, items: [], fallback: String(ref) };
        }
    }
    return { title, items, fallback: '' };
}
Page({
    data: {
        empty: true,
        refTitle: '',
        refItems: [],
        refFallback: '',
        headerPadPx: 88,
    },
    async onLoad(query) {
        try {
            const sys = wx.getSystemInfoSync();
            const navPx = 88 * (sys.windowWidth / 750);
            this.setData({ headerPadPx: (sys.statusBarHeight || 20) + navPx });
        }
        catch (_e) {
            this.setData({ headerPadPx: 88 });
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
                this.setData({ empty: true, refTitle: '', refItems: [], refFallback: '' });
                return;
            }
            const hasContent = parsed.items.length > 0 || parsed.fallback.length > 0;
            this.setData({
                empty: !hasContent,
                refTitle: parsed.title,
                refItems: parsed.items,
                refFallback: parsed.fallback,
            });
        }
        catch (e) {
            const msg = String((e === null || e === void 0 ? void 0 : e.message) || '');
            if (msg.includes('INSUFFICIENT_READS')) {
                wx.showModal({
                    title: '阅读点数不足',
                    content: '去「邀请」页邀请好友可获得阅读点数。',
                    confirmText: '去邀请',
                    success: (r) => {
                        if (r.confirm)
                            wx.switchTab({ url: router_1.ROUTES.invite });
                    },
                });
            }
            else if (msg === 'UNAUTHORIZED' || msg.includes('login required')) {
                wx.showModal({
                    title: '需要登录',
                    content: '登录后可使用阅读点数查看原文对照。',
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
            this.setData({ empty: true, refTitle: '', refItems: [], refFallback: '' });
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
