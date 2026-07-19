"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.isDevtoolsClient = exports.isDevelopEnv = exports.getEnvVersion = void 0;
function getEnvVersion() {
    var _a, _b;
    try {
        return ((_b = (_a = wx.getAccountInfoSync()) === null || _a === void 0 ? void 0 : _a.miniProgram) === null || _b === void 0 ? void 0 : _b.envVersion) || '';
    }
    catch {
        return '';
    }
}
exports.getEnvVersion = getEnvVersion;
function isDevelopEnv() {
    return getEnvVersion() === 'develop';
}
exports.isDevelopEnv = isDevelopEnv;
function isDevtoolsClient() {
    var _a;
    try {
        const info = wx.getSystemInfoSync();
        if (info.platform === 'devtools')
            return true;
        if (((_a = info.host) === null || _a === void 0 ? void 0 : _a.env) === 'WeChatDevTools')
            return true;
    }
    catch {
        // ignore
    }
    return false;
}
exports.isDevtoolsClient = isDevtoolsClient;
