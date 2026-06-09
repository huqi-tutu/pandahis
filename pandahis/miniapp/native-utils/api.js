"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.request = exports.hasToken = exports.hasUserLoggedOut = exports.clearToken = exports.setToken = exports.USER_LOGGED_OUT_KEY = exports.getToken = exports.getBaseUrl = void 0;
// 正式环境：wx.setStorageSync('apiBaseUrl', 'https://域名/api/v1') 或改下方默认值；见 docs/DEPLOY.md
// const DEFAULT_BASE_URL = 'https://www.pandahis.com/api/v1'
// 本地调试（后端默认端口 8080、context-path /api/v1）；真机预览请换成本机局域网 IP，例如 http://192.168.x.x:8080/api/v1
const DEFAULT_BASE_URL = 'http://localhost:8080/api/v1';
function getBaseUrl() {
    const v = wx.getStorageSync('apiBaseUrl');
    return v || DEFAULT_BASE_URL;
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
    catch {
        // ignore
    }
}
exports.setToken = setToken;
function clearToken() {
    wx.removeStorageSync('accessToken');
    try {
        wx.setStorageSync(exports.USER_LOGGED_OUT_KEY, '1');
    }
    catch {
        // ignore
    }
}
exports.clearToken = clearToken;
function hasUserLoggedOut() {
    try {
        return wx.getStorageSync(exports.USER_LOGGED_OUT_KEY) === '1';
    }
    catch {
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
            // 首请求含连接池建连 + 远端 MySQL 时可能 >10s；与后端日志对齐，避免误报 timeout
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
                    const detail = {
                        url,
                        method,
                        status,
                        body,
                    };
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
