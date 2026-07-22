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
    var _a, _b, _c;
    try {
        const device = (_a = wx.getDeviceInfo) === null || _a === void 0 ? void 0 : _a.call(wx);
        if ((device === null || device === void 0 ? void 0 : device.platform) === 'devtools')
            return true;
        const appBase = (_b = wx.getAppBaseInfo) === null || _b === void 0 ? void 0 : _b.call(wx);
        const hostEnv = (_c = appBase === null || appBase === void 0 ? void 0 : appBase.host) === null || _c === void 0 ? void 0 : _c.env;
        if (hostEnv === 'WeChatDevTools')
            return true;
    }
    catch {
        // ignore
    }
    return false;
}
exports.isDevtoolsClient = isDevtoolsClient;
