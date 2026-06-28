"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const invite_storage_1 = require("./native-utils/invite-storage");
const wx_auth_1 = require("./native-utils/wx-auth");
function migrateDevApiBaseUrl() {
    try {
        var _a;
        const env = (_a = wx.getAccountInfoSync()) === null || _a === void 0 ? void 0 : _a.miniProgram.envVersion;
        if (env !== 'develop')
            return;
        wx.removeStorageSync('apiBaseUrl');
    }
    catch (_b) {
        // ignore
    }
}
App({
    globalData: {},
    onLaunch(options) {
        migrateDevApiBaseUrl();
        (0, invite_storage_1.stashInviteFromLaunchOptions)(options);
        void (0, wx_auth_1.trySilentWxLogin)();
    },
    onShow(options) {
        (0, invite_storage_1.stashInviteFromLaunchOptions)(options);
    },
});
