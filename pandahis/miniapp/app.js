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
    onHide() {
        try {
            const pages = getCurrentPages();
            for (let i = pages.length - 1; i >= 0; i--) {
                const page = pages[i];
                const route = page && page.route ? String(page.route) : '';
                if (!route.endsWith('home/index'))
                    continue;
                if (typeof page._syncScrollTopFromDom === 'function') {
                    page._syncScrollTopFromDom(() => {
                        if (typeof page._persistHomeViewportState === 'function') {
                            page._persistHomeViewportState(true);
                        }
                    });
                }
                else if (typeof page._persistHomeViewportState === 'function') {
                    page._persistHomeViewportState(true);
                }
                break;
            }
        }
        catch (_a) {
            // ignore
        }
    },
});
