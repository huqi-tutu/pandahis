"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const invite_storage_1 = require("./native-utils/invite-storage");
const wx_auth_1 = require("./native-utils/wx-auth");
App({
    globalData: {},
    onLaunch(options) {
        (0, invite_storage_1.stashInviteFromLaunchOptions)(options);
        void (0, wx_auth_1.trySilentWxLogin)();
    },
    onShow(options) {
        (0, invite_storage_1.stashInviteFromLaunchOptions)(options);
    },
});
