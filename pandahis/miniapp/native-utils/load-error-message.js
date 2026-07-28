"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.formatUserFacingError = exports.formatEmptySwimError = exports.formatDynastyLoadError = exports.formatApiErrorDetail = exports.formatApiRequestError = void 0;
const api_1 = require("./api");
const runtime_env_1 = require("./runtime-env");
function extractWxErrMsg(error) {
    var _a;
    if (error instanceof api_1.ApiError) {
        const err = (_a = error.detail) === null || _a === void 0 ? void 0 : _a.err;
        if (err === null || err === void 0 ? void 0 : err.errMsg)
            return err.errMsg;
        return error.message;
    }
    if (error instanceof Error)
        return error.message;
    return String((error === null || error === void 0 ? void 0 : error.message) || error || '');
}
/** 将 wx.request fail / ApiError 转为用户可操作的提示 */
function formatApiRequestError(error) {
    var _a;
    const raw = extractWxErrMsg(error);
    const lower = raw.toLowerCase();
    if (/domain list|合法域名|not in domain/i.test(raw)) {
        return '请求被微信拦截：请在小程序后台「开发管理 → 开发设置 → 服务器域名」添加 request 合法域名 www.pandahis.com（https）。配置生效后请重新编译并扫码预览。';
    }
    if (/ssl|certificate|证书/i.test(raw)) {
        return '服务器 HTTPS 证书校验失败，请联系管理员检查域名证书。';
    }
    if (/^http:\/\//i.test(raw)
        || /localhost|127\.0\.0\.1|192\.168\.|10\.\d|172\.(1[6-9]|2\d|3[01])\./i.test(raw)
        || /refused|无法连接|connect\s*fail|err_connection/i.test(lower)) {
        return '无法连接接口服务器。请打开「我的 → 设置 → 接口地址」，选择「使用生产接口」后点「检测接口连接」确认。';
    }
    if (/timeout|超时/i.test(raw)) {
        return '连接超时，请检查网络后重试。';
    }
    if (/not found|NOT_FOUND|unit not found|不存在/i.test(raw)) {
        if (/favorites\/units/i.test(String(((_a = error === null || error === void 0 ? void 0 : error.detail) === null || _a === void 0 ? void 0 : _a.url) || ''))) {
            return '当前接口尚未支持朝代收藏，需部署最新后端；开发版可在「设置→接口地址」切到本机后端联调。';
        }
        return '未找到该朝代数据，请从首页重新进入或更新小程序后重试。';
    }
    if (/INVALID_RESPONSE|parse|json/i.test(raw)) {
        return '服务器返回格式异常，请稍后重试或在设置页检测「朝代画布接口」。';
    }
    if (/internal error|INTERNAL_ERROR/i.test(raw)) {
        return '服务器内部错误：登录后触发的用户数据查询失败。请退出登录后重试朝代详情，或联系管理员部署 user_box_read_completion 等用户表。';
    }
    if ((0, runtime_env_1.isDevtoolsClient)()) {
        return `请求失败：${raw.slice(0, 160)}`;
    }
    if ((0, runtime_env_1.getEnvVersion)() === 'develop' && raw.trim()) {
        return `加载失败（${raw.slice(0, 120)}）。请在设置页检测接口，或点下方重试。`;
    }
    return '朝代数据暂时无法加载，请检查网络或在设置中确认接口地址为生产环境。';
}
exports.formatApiRequestError = formatApiRequestError;
/** 供复制反馈的技术摘要 */
function formatApiErrorDetail(error, extra) {
    var _a;
    const lines = [
        `time: ${new Date().toISOString()}`,
        `env: ${(0, runtime_env_1.getEnvVersion)() || 'unknown'}`,
        `msg: ${extractWxErrMsg(error)}`,
    ];
    if (error instanceof api_1.ApiError) {
        lines.push(`url: ${error.detail.url}`);
        lines.push(`status: ${String((_a = error.detail.status) !== null && _a !== void 0 ? _a : '')}`);
        if (error.detail.body != null) {
            try {
                lines.push(`body: ${JSON.stringify(error.detail.body).slice(0, 240)}`);
            }
            catch {
                lines.push('body: [unserializable]');
            }
        }
    }
    if (extra) {
        for (const [k, v] of Object.entries(extra)) {
            lines.push(`${k}: ${v}`);
        }
    }
    return lines.join('\n');
}
exports.formatApiErrorDetail = formatApiErrorDetail;
function formatDynastyLoadError(error, develop) {
    const devTools = develop && (0, runtime_env_1.isDevtoolsClient)();
    if (!devTools) {
        return formatApiRequestError(error);
    }
    const message = extractWxErrMsg(error) || '加载失败';
    return `无法加载朝代数据（${message}）。请确认后端已启动且已导入 historical_dynasty / historical_box 数据。`;
}
exports.formatDynastyLoadError = formatDynastyLoadError;
function formatEmptySwimError(develop) {
    const devTools = develop && (0, runtime_env_1.isDevtoolsClient)();
    if (!devTools) {
        return '该朝代画布暂时无法展示，请稍后重试。';
    }
    return '该朝代画布暂无数据（swim-matrix 泳道为空）。请检查后端 swim-matrix 导入。';
}
exports.formatEmptySwimError = formatEmptySwimError;
function formatUserFacingError(error, develop, fallback = '操作失败，请稍后重试') {
    if (develop && error instanceof Error && error.message.trim()) {
        return error.message.trim();
    }
    return fallback;
}
exports.formatUserFacingError = formatUserFacingError;
