"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.buildSharePosterSheetState = exports.fetchShareUserProfile = exports.formatShareExcerptDate = void 0;
const api_1 = require("./api");
function formatShareExcerptDate() {
    const now = new Date();
    return `${now.getFullYear()}/${now.getMonth() + 1}/${now.getDate()}`;
}
exports.formatShareExcerptDate = formatShareExcerptDate;
async function fetchShareUserProfile() {
    var _a, _b, _c, _d;
    if (!(0, api_1.hasToken)()) {
        return { nickname: '历史读者', avatarUrl: '' };
    }
    try {
        const meRes = await (0, api_1.request)('/me', { auth: true });
        const raw = (meRes.data || {});
        return {
            nickname: String((_b = (_a = raw.nickname) !== null && _a !== void 0 ? _a : raw['nickname']) !== null && _b !== void 0 ? _b : '历史读者'),
            avatarUrl: String((_d = (_c = raw.avatarUrl) !== null && _c !== void 0 ? _c : raw['avatar_url']) !== null && _d !== void 0 ? _d : ''),
        };
    }
    catch {
        return { nickname: '历史读者', avatarUrl: '' };
    }
}
exports.fetchShareUserProfile = fetchShareUserProfile;
async function buildSharePosterSheetState(quoteText, sourceLine1, sourceLine2) {
    const profile = await fetchShareUserProfile();
    return {
        sharePosterVisible: true,
        sharePosterQuote: quoteText,
        sharePosterSourceLine1: sourceLine1,
        sharePosterSourceLine2: sourceLine2,
        sharePosterUserName: profile.nickname,
        sharePosterUserAvatar: profile.avatarUrl,
        sharePosterExcerptDate: formatShareExcerptDate(),
    };
}
exports.buildSharePosterSheetState = buildSharePosterSheetState;
