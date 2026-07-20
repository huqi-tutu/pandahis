"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.uploadFile = exports.request = exports.hasToken = exports.hasUserLoggedOut = exports.clearToken = exports.setToken = exports.USER_LOGGED_OUT_KEY = exports.getToken = exports.getBaseUrl = exports.ApiError = void 0;
const dev_config_1 = require("./dev-config");
const runtime_env_1 = require("./runtime-env");
class ApiError extends Error {
    constructor(message, detail) {
        super(message);
        this.name = 'ApiError';
        this.detail = detail;
    }
}
exports.ApiError = ApiError;
const PROD_BASE_URL = 'https://www.pandahis.com/api/v1';
function normalizeDevelopBaseUrl(value) {
    const url = String(value || '').trim().replace(/\/$/, '');
    if (!url)
        return '';
    if (/^https:\/\/[a-z0-9.-]+(?::\d+)?(?:\/.*)?$/i.test(url))
        return url;
    const privateHttp = /^http:\/\/(?:localhost|127(?:\.\d{1,3}){3}|10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})(?::\d+)?(?:\/.*)?$/i;
    return privateHttp.test(url) ? url : '';
}
function getBaseUrl() {
    if ((0, runtime_env_1.getEnvVersion)() === 'develop') {
        const stored = normalizeDevelopBaseUrl(wx.getStorageSync('apiBaseUrl'));
        if (stored)
            return stored;
        // 开发者工具可直接访问本机；真机预览默认走生产 HTTPS，
        // 避免 DHCP 改变开发机局域网 IP 后整页数据加载失败。
        if ((0, runtime_env_1.isDevtoolsClient)()) {
            return `http://localhost:${dev_config_1.DEV_API_PORT}/api/v1`;
        }
    }
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
            method: method,
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
                    reject(new ApiError(String(msg), detail));
                    return;
                }
                if (!body || typeof body !== 'object') {
                    const detail = { url, method, status, body };
                    console.error('[api] INVALID_RESPONSE', detail);
                    reject(new ApiError('INVALID_RESPONSE', detail));
                    return;
                }
                if (body.code && body.code !== 'OK') {
                    const detail = { url, method, status, body };
                    console.error('[api] API_ERROR', detail);
                    reject(new ApiError(String(body.message || body.code), detail));
                    return;
                }
                resolve(body);
            },
            fail(err) {
                console.error('[api] REQUEST_FAIL', { url, method, err });
                const msg = (err === null || err === void 0 ? void 0 : err.errMsg) || 'REQUEST_FAIL';
                reject(new ApiError(msg, { url, method, err }));
            },
        });
    });
}
exports.request = request;
/** 上传本地文件（如头像），字段名默认 `file` */
function uploadFile(path, filePath, opts) {
    if (!getToken()) {
        return Promise.reject(new Error('UNAUTHORIZED'));
    }
    const baseUrl = getBaseUrl();
    const url = baseUrl.replace(/\/$/, '') + (path.startsWith('/') ? path : `/${path}`);
    const name = (opts === null || opts === void 0 ? void 0 : opts.name) || 'file';
    const header = {};
    const token = getToken();
    if (token)
        header.Authorization = `Bearer ${token}`;
    return new Promise((resolve, reject) => {
        wx.uploadFile({
            url,
            filePath,
            name,
            formData: opts === null || opts === void 0 ? void 0 : opts.formData,
            header,
            timeout: 60000,
            success(res) {
                const status = res.statusCode || 0;
                let body = null;
                try {
                    body = typeof res.data === 'string' ? JSON.parse(res.data) : res.data;
                }
                catch {
                    body = res.data;
                }
                if (status === 401 || (body === null || body === void 0 ? void 0 : body.code) === 'UNAUTHORIZED') {
                    clearToken();
                    reject(new Error('UNAUTHORIZED'));
                    return;
                }
                if (status >= 400) {
                    const detail = { url, method: 'POST', status, body };
                    console.error('[api] UPLOAD_HTTP_ERROR', detail);
                    const msg = (typeof body === 'object' && body && (body.message || body.code)) ||
                        `HTTP_${status}`;
                    reject(new ApiError(String(msg), detail));
                    return;
                }
                if (!body || typeof body !== 'object') {
                    reject(new ApiError('INVALID_RESPONSE', { url, method: 'POST', status, body }));
                    return;
                }
                if (body.code && body.code !== 'OK') {
                    reject(new ApiError(String(body.message || body.code), { url, method: 'POST', status, body }));
                    return;
                }
                resolve(body);
            },
            fail(err) {
                console.error('[api] UPLOAD_FAIL', { url, err });
                reject(new ApiError((err === null || err === void 0 ? void 0 : err.errMsg) || 'UPLOAD_FAIL', { url, method: 'POST', err }));
            },
        });
    });
}
exports.uploadFile = uploadFile;
