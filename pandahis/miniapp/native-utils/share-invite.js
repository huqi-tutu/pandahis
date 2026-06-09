"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.promptContentShareUnavailable = exports.promptInviteByCode = exports.copyText = exports.INVITE_SHARE_UNAVAILABLE = void 0;
/** 未认证小程序无法使用 open-type="share"，统一走复制邀请码 */
exports.INVITE_SHARE_UNAVAILABLE = '小程序未完成认证，暂无法发送分享卡片。已为你复制邀请码，请粘贴发给好友。';
let lastInvitePromptAt = 0;
function copyText(text) {
    return new Promise((resolve, reject) => {
        wx.setClipboardData({
            data: text,
            success: () => resolve(),
            fail: (err) => reject(err),
        });
    });
}
exports.copyText = copyText;
/**
 * 邀请好友：复制邀请码 + 一次性说明（防抖，避免重复弹窗）
 */
function promptInviteByCode(inviteCode, options) {
    const code = (inviteCode || '').trim();
    if (!code) {
        wx.showToast({ title: '邀请码加载中', icon: 'none' });
        return;
    }
    const now = Date.now();
    if (now - lastInvitePromptAt < 2500) {
        void copyText(code).then(() => wx.showToast({ title: '已复制邀请码', icon: 'none' }));
        return;
    }
    lastInvitePromptAt = now;
    void copyText(code)
        .then(() => {
        wx.showModal({
            title: (options === null || options === void 0 ? void 0 : options.title) || '邀请好友',
            content: `${exports.INVITE_SHARE_UNAVAILABLE}\n\n邀请码：${code}\n\n好友打开小程序 →「邀请加入」页 → 登录后即可助力。`,
            confirmText: '知道了',
            showCancel: false,
        });
    })
        .catch(() => {
        wx.showToast({ title: '复制失败', icon: 'none' });
    });
}
exports.promptInviteByCode = promptInviteByCode;
/** 内容页分享按钮（图谱/盒子）：认证前提示 */
let lastContentShareAt = 0;
function promptContentShareUnavailable() {
    const now = Date.now();
    if (now - lastContentShareAt < 2500) {
        return;
    }
    lastContentShareAt = now;
    wx.showModal({
        title: '分享暂不可用',
        content: '小程序完成微信认证后，即可使用右上角「…」或分享按钮转发内容。',
        confirmText: '知道了',
        showCancel: false,
    });
}
exports.promptContentShareUnavailable = promptContentShareUnavailable;
