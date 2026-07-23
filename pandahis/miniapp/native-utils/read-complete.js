"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.unmarkBoxReadComplete = exports.markBoxReadComplete = exports.promptLoginForReadComplete = void 0;
const api_1 = require("./api");
const encode_path_segment_1 = require("./encode-path-segment");
const router_1 = require("./router");
function promptLoginForReadComplete() {
    wx.showModal({
        title: '需要登录',
        content: '登录后可标记读完，并在「我的」中查看已读完列表。',
        confirmText: '去登录',
        success: (r) => {
            if (r.confirm)
                (0, router_1.navigateTo)(router_1.ROUTES.login);
        },
    });
}
exports.promptLoginForReadComplete = promptLoginForReadComplete;
async function markBoxReadComplete(boxId) {
    await (0, api_1.request)(`/boxes/${(0, encode_path_segment_1.encodePathSegment)(boxId)}/read-complete`, { method: 'PUT', auth: true });
}
exports.markBoxReadComplete = markBoxReadComplete;
async function unmarkBoxReadComplete(boxId) {
    await (0, api_1.request)(`/boxes/${(0, encode_path_segment_1.encodePathSegment)(boxId)}/read-complete`, { method: 'DELETE', auth: true });
}
exports.unmarkBoxReadComplete = unmarkBoxReadComplete;
