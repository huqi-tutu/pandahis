"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.request = exports.hasToken = exports.hasUserLoggedOut = exports.clearToken = exports.setToken = exports.USER_LOGGED_OUT_KEY = exports.getToken = exports.getBaseUrl = void 0;
const dev_config_1 = require("./dev-config");
const PROD_BASE_URL = 'https://www.pandahis.com/api/v1';
function isDevtoolsClient() {
    try {
        const info = wx.getSystemInfoSync();
        if (info.platform === 'devtools')
            return true;
        const host = info.host;
        if (host && host.env === 'WeChatDevTools')
            return true;
    }
    catch (_a) {
        // ignore
    }
    return false;
}
/** 开发者工具用 localhost；真机用局域网 IP（见 dev-config.ts） */
function getLocalBaseUrl() {
    if (isDevtoolsClient()) {
        return `http://localhost:${dev_config_1.DEV_API_PORT}/api/v1`;
    }
    return `http://${dev_config_1.DEV_LAN_HOST}:${dev_config_1.DEV_API_PORT}/api/v1`;
}
function isDevelopEnv() {
    try {
        var _a;
        return ((_a = wx.getAccountInfoSync()) === null || _a === void 0 ? void 0 : _a.miniProgram.envVersion) === 'develop';
    }
    catch (_b) {
        return true;
    }
}
function getBaseUrl() {
    if (isDevelopEnv()) {
        return getLocalBaseUrl();
    }
    const stored = String(wx.getStorageSync('apiBaseUrl') || '').trim();
    if (stored)
        return stored;
    return PROD_BASE_URL;
}
exports.getBaseUrl = getBaseUrl;
function getToken() {
    return wx.getStorageSync('accessToken') || '';
}
exports.getToken = getToken;
/** 用户主动退出后为 true，阻止启动时静默自动登录 */
exports.USER_LOGGED_OUT_KEY = 'userLoggedOut';
function setToken(token) {
    wx.setStorageSync('accessToken', token);
    try {
        wx.removeStorageSync(exports.USER_LOGGED_OUT_KEY);
    }
    catch (_a) {
        // ignore
    }
}
exports.setToken = setToken;
function clearToken() {
    wx.removeStorageSync('accessToken');
    try {
        wx.setStorageSync(exports.USER_LOGGED_OUT_KEY, '1');
    }
    catch (_a) {
        // ignore
    }
}
exports.clearToken = clearToken;
function hasUserLoggedOut() {
    try {
        return wx.getStorageSync(exports.USER_LOGGED_OUT_KEY) === '1';
    }
    catch (_a) {
        return false;
    }
}
exports.hasUserLoggedOut = hasUserLoggedOut;
function hasToken() {
    return Boolean(getToken());
}
exports.hasToken = hasToken;
function request(path, opts) {
    if ((opts === null || opts === void 0 ? void 0 : opts.auth) && !getToken()) {
        return Promise.reject(new Error('UNAUTHORIZED'));
    }
    const baseUrl = getBaseUrl();
    const url = baseUrl.replace(/\/$/, '') + (path.startsWith('/') ? path : `/${path}`);
    const method = (opts === null || opts === void 0 ? void 0 : opts.method) || 'GET';
    const header = { 'content-type': 'application/json' };
    const token = getToken();
    if (token)
        header.Authorization = `Bearer ${token}`;
    return new Promise((resolve, reject) => {
        wx.request({
            url,
            method,
            data: opts === null || opts === void 0 ? void 0 : opts.data,
            header,
            timeout: 60000,
            success(res) {
                const status = res.statusCode || 0;
                const body = res.data;
                if (status === 401 || (body === null || body === void 0 ? void 0 : body.code) === 'UNAUTHORIZED') {
                    clearToken();
                    reject(new Error('UNAUTHORIZED'));
                    return;
                }
                if (status >= 400) {
                    const detail = { url, method, status, body };
                    console.error('[api] HTTP_ERROR', detail);
                    const msg = (typeof body === 'object' && body && (body.message || body.code)) ||
                        (typeof body === 'string' && body.slice(0, 200)) ||
                        `HTTP_${status}`;
                    const err = new Error(msg);
                    err.detail = detail;
                    reject(err);
                    return;
                }
                if (!body || typeof body !== 'object') {
                    const detail = { url, method, status, body };
                    console.error('[api] INVALID_RESPONSE', detail);
                    const err = new Error('INVALID_RESPONSE');
                    err.detail = detail;
                    reject(err);
                    return;
                }
                if (body.code && body.code !== 'OK') {
                    const detail = { url, method, status, body };
                    console.error('[api] API_ERROR', detail);
                    const err = new Error(body.message || body.code);
                    err.detail = detail;
                    reject(err);
                    return;
                }
                resolve(body);
            },
            fail(err) {
                console.error('[api] REQUEST_FAIL', { url, method, err });
                const msg = (err === null || err === void 0 ? void 0 : err.errMsg) || (err === null || err === void 0 ? void 0 : err.message) || 'REQUEST_FAIL';
                const e = new Error(msg);
                e.detail = { url, method, err };
                reject(e);
            },
        });
    });
}
exports.request = request;
