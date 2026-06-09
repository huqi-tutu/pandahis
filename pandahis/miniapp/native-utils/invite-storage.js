"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.clearPendingInviteCode = exports.peekPendingInviteCode = exports.stashInviteFromLaunchOptions = exports.stashInviteCodeFromQuery = exports.parseInviteCodeFromScene = exports.stashInviteCode = exports.PENDING_INVITE_CODE_KEY = void 0;
/** 登录 POST /auth/wx-login 时附带，用于邀请归因 */
exports.PENDING_INVITE_CODE_KEY = 'pendingInviteCode';
const INVITE_CODE_RE = /^[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{6,16}$/;
function normalizeInviteCode(raw) {
    if (raw == null)
        return '';
    const c = String(raw).trim();
    return c;
}
function stashInviteCode(code) {
    const c = normalizeInviteCode(code);
    if (!c)
        return;
    try {
        wx.setStorageSync(exports.PENDING_INVITE_CODE_KEY, c);
    }
    catch {
        // ignore
    }
}
exports.stashInviteCode = stashInviteCode;
/** 小程序码 scene：inviteCode=XXX 或纯邀请码 */
function parseInviteCodeFromScene(scene) {
    if (scene == null || scene === '')
        return '';
    const raw = typeof scene === 'number'
        ? String(scene)
        : decodeURIComponent(String(scene).trim());
    if (!raw)
        return '';
    if (raw.includes('=')) {
        const q = raw.startsWith('?') ? raw.slice(1) : raw;
        const params = {};
        for (const part of q.split('&')) {
            const i = part.indexOf('=');
            if (i < 0)
                continue;
            const k = decodeURIComponent(part.slice(0, i));
            const v = decodeURIComponent(part.slice(i + 1));
            params[k] = v;
        }
        return normalizeInviteCode(params.inviteCode || params.invite_code);
    }
    const bare = normalizeInviteCode(raw);
    return INVITE_CODE_RE.test(bare) ? bare : '';
}
exports.parseInviteCodeFromScene = parseInviteCodeFromScene;
function stashInviteCodeFromQuery(query) {
    if (!query)
        return;
    const raw = query.inviteCode || query.invite_code;
    const c = normalizeInviteCode(raw);
    if (c)
        stashInviteCode(c);
}
exports.stashInviteCodeFromQuery = stashInviteCodeFromQuery;
function stashInviteFromLaunchOptions(options) {
    if (!options)
        return;
    stashInviteCodeFromQuery(options.query);
    const fromScene = parseInviteCodeFromScene(options.scene);
    if (fromScene)
        stashInviteCode(fromScene);
}
exports.stashInviteFromLaunchOptions = stashInviteFromLaunchOptions;
function peekPendingInviteCode() {
    try {
        const v = wx.getStorageSync(exports.PENDING_INVITE_CODE_KEY);
        return typeof v === 'string' ? v.trim() : '';
    }
    catch {
        return '';
    }
}
exports.peekPendingInviteCode = peekPendingInviteCode;
function clearPendingInviteCode() {
    try {
        wx.removeStorageSync(exports.PENDING_INVITE_CODE_KEY);
    }
    catch {
        // ignore
    }
}
exports.clearPendingInviteCode = clearPendingInviteCode;
