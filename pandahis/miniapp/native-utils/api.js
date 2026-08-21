"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.uploadFile = exports.request = exports.hasToken = exports.hasUserLoggedOut = exports.clearToken = exports.clearAccessToken = exports.setToken = exports.USER_LOGGED_OUT_KEY = exports.getToken = exports.useLocalDevApi = exports.useProductionApi = exports.clearDevelopApiBaseUrl = exports.setDevelopApiBaseUrl = exports.probeApiConnectivity = exports.probeApiHealth = exports.getBaseUrl = exports.LOCAL_DEV_BASE_URL = exports.ApiError = void 0;
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
/** 本机联调地址（需在设置或登录页开发区显式启用） */
exports.LOCAL_DEV_BASE_URL = `http://localhost:${dev_config_1.DEV_API_PORT}/api/v1`;
function normalizeDevelopBaseUrl(value) {
    const url = String(value || '').trim().replace(/\/$/, '');
    if (!url)
        return '';
    if (/^https:\/\/[a-z0-9.-]+(?::\d+)?(?:\/.*)?$/i.test(url))
        return url;
    const privateHttp = /^http:\/\/(?:localhost|127(?:\.\d{1,3}){3}|10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})(?::\d+)?(?:\/.*)?$/i;
    return privateHttp.test(url) ? url : '';
}
function isPrivateHttpBaseUrl(url) {
    return /^http:\/\//i.test(url);
}
/** 真机预览无法稳定访问本机/局域网 HTTP，统一走生产 */
function shouldIgnoreStoredBaseOnClient(stored) {
    if ((0, runtime_env_1.isDevtoolsClient)())
        return false;
    if (/localhost|127\.0\.0\.1/i.test(stored))
        return true;
    return isPrivateHttpBaseUrl(stored);
}
function getBaseUrl() {
    const envVersion = (0, runtime_env_1.getEnvVersion)();
    if (envVersion === 'develop') {
        const stored = normalizeDevelopBaseUrl(wx.getStorageSync('apiBaseUrl'));
        if (stored) {
            if (shouldIgnoreStoredBaseOnClient(stored)) {
                return PROD_BASE_URL;
            }
            return stored;
        }
        return PROD_BASE_URL;
    }
    return PROD_BASE_URL;
}
exports.getBaseUrl = getBaseUrl;
/** 设置页连通性检测（基础） */
function probeApiHealth() {
    return request('/health');
}
exports.probeApiHealth = probeApiHealth;
/** 分阶段检测：health → 登录接口 → 朝代概要 → 朝代画布 */
async function probeApiConnectivity() {
    try {
        await probeApiHealth();
    }
    catch (error) {
        return { ok: false, stage: 'health', error };
    }
    try {
        await request('/auth/wx-login', {
            method: 'POST',
            data: { code: 'connectivity-probe-invalid' },
        });
    }
    catch (error) {
        const msg = error instanceof ApiError ? error.message : String(error);
        // 服务端可达且校验 code：说明登录链路通（与 wx.login 后 POST 同域名同路径）
        if (/invalid|expired|wx\.login/i.test(msg)) {
            // continue
        }
        else {
            return { ok: false, stage: 'auth', error };
        }
    }
    try {
        await request('/units/CD_HX_XIA');
    }
    catch (error) {
        return { ok: false, stage: 'unit', error };
    }
    try {
        await request('/units/CD_HX_XIA/swim-matrix');
    }
    catch (error) {
        return { ok: false, stage: 'swim-matrix', error };
    }
    return { ok: true, stage: 'swim-matrix' };
}
exports.probeApiConnectivity = probeApiConnectivity;
function parseResponseBody(raw) {
    if (raw == null)
        return null;
    if (typeof raw === 'object')
        return raw;
    if (typeof raw === 'string') {
        const text = raw.trim();
        if (!text)
            return null;
        try {
            return JSON.parse(text);
        }
        catch {
            return null;
        }
    }
    return null;
}
/** 公开内容 GET 不附带 token，避免登录态触发服务端未迁移的用户表查询导致 500 */
function isPublicContentPath(path) {
    const p = path.split('?')[0];
    // /search、/search/suggest 为可选登录接口：有 token 时必须带上，才能读写搜索历史
    return (/^\/units\//.test(p)
        || /^\/boxes\//.test(p)
        || p.startsWith('/home/')
        || p === '/health'
        || p.startsWith('/membership/plans')
        || p.startsWith('/config/')
        || p.startsWith('/dictionary/')
        || p.startsWith('/wikipedia/'));
}
function shouldAttachBearerToken(path, method, auth) {
    if (!getToken())
        return false;
    if (auth)
        return true;
    if (method === 'GET' && isPublicContentPath(path))
        return false;
    return true;
}
function buildRequestHeaders(path, method, auth, contentType = 'application/json') {
    const header = { 'content-type': contentType };
    const envVersion = (0, runtime_env_1.getEnvVersion)();
    if (envVersion)
        header['X-Miniapp-Env'] = envVersion;
    if (shouldAttachBearerToken(path, method, auth)) {
        header.Authorization = `Bearer ${getToken()}`;
    }
    return header;
}
function setDevelopApiBaseUrl(url) {
    const normalized = normalizeDevelopBaseUrl(url);
    if (!normalized) {
        throw new Error('API 地址无效');
    }
    wx.setStorageSync('apiBaseUrl', normalized);
}
exports.setDevelopApiBaseUrl = setDevelopApiBaseUrl;
function clearDevelopApiBaseUrl() {
    try {
        wx.removeStorageSync('apiBaseUrl');
    }
    catch {
        // ignore
    }
}
exports.clearDevelopApiBaseUrl = clearDevelopApiBaseUrl;
function useProductionApi() {
    clearDevelopApiBaseUrl();
}
exports.useProductionApi = useProductionApi;
function useLocalDevApi() {
    setDevelopApiBaseUrl(exports.LOCAL_DEV_BASE_URL);
}
exports.useLocalDevApi = useLocalDevApi;
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
/** 仅清除令牌（401 / 过期时用这个，不阻断后续静默登录） */
function clearAccessToken() {
    try {
        wx.removeStorageSync('accessToken');
    }
    catch {
        // ignore
    }
}
exports.clearAccessToken = clearAccessToken;
/** 用户主动退出：清令牌并标记不再静默登录 */
function clearToken() {
    clearAccessToken();
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
    const header = buildRequestHeaders(path, method, opts === null || opts === void 0 ? void 0 : opts.auth);
    return new Promise((resolve, reject) => {
        var _a;
        wx.request({
            url,
            method: method,
            data: opts === null || opts === void 0 ? void 0 : opts.data,
            header,
            enableHttp2: false,
            enableQuic: false,
            // 首请求含连接池建连 + 远端 MySQL 时可能 >10s；与后端日志对齐，避免误报 timeout
            timeout: (_a = opts === null || opts === void 0 ? void 0 : opts.timeout) !== null && _a !== void 0 ? _a : 60000,
            success(res) {
                const status = res.statusCode || 0;
                const body = parseResponseBody(res.data);
                if (status === 401 || (body === null || body === void 0 ? void 0 : body.code) === 'UNAUTHORIZED') {
                    if (!(opts === null || opts === void 0 ? void 0 : opts.softAuth)) {
                        clearAccessToken();
                    }
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
    const header = buildRequestHeaders(path, 'POST', true, '');
    delete header['content-type'];
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
                    clearAccessToken();
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
