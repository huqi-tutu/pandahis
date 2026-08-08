"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.redirectTo = exports.navigateTo = exports.buildUrl = exports.SUPPORT_EMAIL = exports.ROUTES = void 0;
exports.ROUTES = {
    home: '/pages/home/index',
    mine: '/pages/my/index',
    search: '/pages/search/index',
    searchResult: '/pages/search-result/index',
    dynastyDetail: '/pages/dynasty-detail/index',
    boxDetail: '/package-graph/pages/box-detail/index',
    login: '/pages/login/index',
    invite: '/pages/invite/index',
    inviteAccept: '/pages/invite-accept/index',
    favorites: '/pages/favorites/index',
    corrections: '/pages/corrections/index',
    footprints: '/pages/footprints/index',
    originalText: '/pages/original-text/index',
    settings: '/pages/settings/index',
    feedback: '/pages/feedback/index',
    about: '/pages/about/index',
    membership: '/pages/membership/index',
    inviteAssist: '/pages/invite-assist/index',
    profileEdit: '/pages/profile-edit/index',
    readCompleted: '/pages/read-completed/index',
    relationDetail: '/pages/relation-detail/index',
    critiqueDetail: '/pages/critique-detail/index',
    relicDetail: '/pages/relic-detail/index',
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
    wx.navigateTo({
        url: buildUrl(path, query),
        fail(err) {
            console.error('[navigateTo]', buildUrl(path, query), err);
            wx.showToast({ title: '页面打开失败', icon: 'none' });
        },
    });
}
exports.navigateTo = navigateTo;
function redirectTo(path, query) {
    wx.redirectTo({ url: buildUrl(path, query) });
}
exports.redirectTo = redirectTo;
