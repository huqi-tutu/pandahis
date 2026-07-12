"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.loginSuccessToast = exports.trySilentWxLogin = exports.leaveAfterLogin = exports.loginWithWxCode = exports.wxLoginCode = void 0;
const api_1 = require("./api");
const invite_storage_1 = require("./invite-storage");
const router_1 = require("./router");
function wxLoginCode() {
    return new Promise((resolve, reject) => {
        wx.login({
            success: (res) => {
                if (res.code)
                    resolve(res.code);
                else
                    reject(new Error('未取得 code'));
            },
            fail: () => reject(new Error('wx.login 失败')),
        });
    });
}
exports.wxLoginCode = wxLoginCode;
/** 调用后端 /auth/wx-login，写入 accessToken */
async function loginWithWxCode(options) {
    var _a, _b;
    const code = await wxLoginCode();
    const inviteCode = ((_a = options === null || options === void 0 ? void 0 : options.inviteCode) !== null && _a !== void 0 ? _a : (0, invite_storage_1.peekPendingInviteCode)()).trim();
    const res = await (0, api_1.request)('/auth/wx-login', {
        method: 'POST',
        data: inviteCode ? { code, inviteCode } : { code },
    });
    const accessToken = (_b = res.data) === null || _b === void 0 ? void 0 : _b.accessToken;
    if (!accessToken || typeof accessToken !== 'string') {
        throw new Error('登录响应异常，未获取到令牌');
    }
    (0, api_1.setToken)(accessToken);
    if (inviteCode)
        (0, invite_storage_1.clearPendingInviteCode)();
    return res.data;
}
exports.loginWithWxCode = loginWithWxCode;
/** 登录成功后离开登录页：优先返回上一页，失败则切到「我的」Tab */
function leaveAfterLogin(delayMs = 400) {
    const go = () => {
        const pages = getCurrentPages();
        const prev = pages.length > 1 ? pages[pages.length - 2] : null;
        const notifyPrev = () => {
            const r = prev === null || prev === void 0 ? void 0 : prev.refresh;
            if (typeof r === 'function')
                void r.call(prev);
        };
        if (pages.length > 1) {
            wx.navigateBack({
                success: notifyPrev,
                fail: () => wx.switchTab({ url: router_1.ROUTES.mine }),
            });
            return;
        }
        wx.switchTab({ url: router_1.ROUTES.mine });
    };
    if (delayMs > 0) {
        setTimeout(go, delayMs);
    }
    else {
        go();
    }
}
exports.leaveAfterLogin = leaveAfterLogin;
/** 启动时静默登录：已有 token 则跳过；用户主动退出后不再自动登录 */
async function trySilentWxLogin() {
    if ((0, api_1.hasToken)())
        return true;
    if ((0, api_1.hasUserLoggedOut)())
        return false;
    try {
        await loginWithWxCode();
        return true;
    }
    catch {
        return false;
    }
}
exports.trySilentWxLogin = trySilentWxLogin;
function loginSuccessToast(data) {
    if (data.inviteRecorded) {
        wx.showToast({ title: '登录成功，邀请已生效', icon: 'success' });
        return;
    }
    if (data.newUser) {
        wx.showToast({ title: '注册成功', icon: 'success' });
        return;
    }
    wx.showToast({ title: '登录成功', icon: 'success' });
}
exports.loginSuccessToast = loginSuccessToast;
