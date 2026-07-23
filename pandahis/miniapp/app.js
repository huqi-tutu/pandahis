"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const invite_storage_1 = require("./native-utils/invite-storage");
const api_1 = require("./native-utils/api");
const runtime_env_1 = require("./native-utils/runtime-env");
const wx_auth_1 = require("./native-utils/wx-auth");
/** 真机预览清除无效的本机/局域网 API 缓存，避免误连不可达地址 */
function migrateApiBaseUrlForClient() {
    try {
        if ((0, runtime_env_1.getEnvVersion)() !== 'develop')
            return;
        if ((0, runtime_env_1.isDevtoolsClient)())
            return;
        const stored = String(wx.getStorageSync('apiBaseUrl') || '').trim();
        if (!stored)
            return;
        if (/^http:\/\//i.test(stored)) {
            (0, api_1.clearDevelopApiBaseUrl)();
        }
    }
    catch {
        // ignore
    }
}
/** 加载 Noto Serif SC，解决 Android 无内置宋体导致标题字体不一致 */
function loadAppFonts() {
    var _a;
    try {
        const platform = ((_a = wx.getDeviceInfo) === null || _a === void 0 ? void 0 : _a.call(wx).platform) || wx.getSystemInfoSync().platform;
        // 开发者工具无法稳定加载外链字体；真机需在后台配置 downloadFile 合法域名
        if (platform === 'devtools')
            return;
    }
    catch {
        return;
    }
    wx.loadFontFace({
        family: 'Noto Serif SC',
        source: 'url("https://cdn.jsdelivr.net/npm/@fontsource/noto-serif-sc@5.1.1/files/noto-serif-sc-chinese-simplified-700-normal.woff2")',
        weight: '700',
        global: true,
        fail(err) {
            console.warn('[字体] Noto Serif SC 700 加载失败', err);
        },
    });
    wx.loadFontFace({
        family: 'Noto Serif SC',
        source: 'url("https://cdn.jsdelivr.net/npm/@fontsource/noto-serif-sc@5.1.1/files/noto-serif-sc-chinese-simplified-400-normal.woff2")',
        weight: '400',
        global: true,
        fail(err) {
            console.warn('[字体] Noto Serif SC 400 加载失败', err);
        },
    });
}
App({
    globalData: {},
    onLaunch(options) {
        migrateApiBaseUrlForClient();
        loadAppFonts();
        (0, invite_storage_1.stashInviteFromLaunchOptions)(options);
        void (0, wx_auth_1.trySilentWxLogin)();
    },
    onShow(options) {
        (0, invite_storage_1.stashInviteFromLaunchOptions)(options);
    },
    onHide() {
        var _a;
        try {
            const pages = getCurrentPages();
            for (let i = pages.length - 1; i >= 0; i--) {
                const page = pages[i];
                const route = (page === null || page === void 0 ? void 0 : page.route) ? String(page.route) : '';
                if (!route.endsWith('home/index'))
                    continue;
                if (page._syncScrollTopFromDom) {
                    page._syncScrollTopFromDom(() => { var _a; return (_a = page._persistHomeViewportState) === null || _a === void 0 ? void 0 : _a.call(page, true); });
                }
                else {
                    (_a = page._persistHomeViewportState) === null || _a === void 0 ? void 0 : _a.call(page, true);
                }
                break;
            }
        }
        catch {
            // ignore
        }
    },
});
