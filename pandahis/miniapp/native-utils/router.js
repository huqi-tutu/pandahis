"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.redirectTo = exports.navigateTo = exports.buildUrl = exports.SUPPORT_EMAIL = exports.ROUTES = void 0;
exports.ROUTES = {
    home: '/pages/home/index',
    mine: '/pages/my/index',
    search: '/pages/search/index',
    unitDetail: '/pages/unit-detail/index',
    boxDetail: '/pages/box-detail/index',
    login: '/pages/login/index',
    invite: '/pages/invite/index',
    inviteAccept: '/pages/invite-accept/index',
    favorites: '/pages/favorites/index',
    footprints: '/pages/footprints/index',
    originalText: '/pages/original-text/index',
    settings: '/pages/settings/index',
    about: '/pages/about/index',
    membership: '/pages/membership/index',
    inviteAssist: '/pages/invite-assist/index',
    profileEdit: '/pages/profile-edit/index',
};
exports.SUPPORT_EMAIL = 'support@pandahis.com';
function buildUrl(path, query) {
    if (!query)
        return path;
    const pairs = Object.keys(query)
        .sort()
        .flatMap((k) => {
        const v = query[k];
        if (v === undefined || v === null || v === '')
            return [];
        return [`${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`];
    });
    return pairs.length ? `${path}?${pairs.join('&')}` : path;
}
exports.buildUrl = buildUrl;
function navigateTo(path, query) {
    const url = buildUrl(path, query);
    wx.navigateTo({
        url,
        fail(err) {
            console.error('[navigateTo]', url, err);
            wx.showToast({ title: '页面打开失败', icon: 'none' });
        },
    });
}
exports.navigateTo = navigateTo;
function redirectTo(path, query) {
    wx.redirectTo({ url: buildUrl(path, query) });
}
exports.redirectTo = redirectTo;
