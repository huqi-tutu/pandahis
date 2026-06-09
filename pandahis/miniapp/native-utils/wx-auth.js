"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.loginSuccessToast = exports.trySilentWxLogin = exports.loginWithWxCode = exports.wxLoginCode = void 0;
const api_1 = require("./api");
const invite_storage_1 = require("./invite-storage");
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
    var _a;
    const code = await wxLoginCode();
    const inviteCode = ((_a = options === null || options === void 0 ? void 0 : options.inviteCode) !== null && _a !== void 0 ? _a : (0, invite_storage_1.peekPendingInviteCode)()).trim();
    const res = await (0, api_1.request)('/auth/wx-login', {
        method: 'POST',
        data: inviteCode ? { code, inviteCode } : { code },
    });
    (0, api_1.setToken)(res.data.accessToken);
    if (inviteCode)
        (0, invite_storage_1.clearPendingInviteCode)();
    return res.data;
}
exports.loginWithWxCode = loginWithWxCode;
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
