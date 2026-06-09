"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.bindInviteCode = void 0;
const api_1 = require("./api");
async function bindInviteCode(inviteCode) {
    const res = await (0, api_1.request)('/invite/bind', {
        method: 'POST',
        auth: true,
        data: { inviteCode: inviteCode.trim().toUpperCase() },
    });
    return res.data;
}
exports.bindInviteCode = bindInviteCode;
