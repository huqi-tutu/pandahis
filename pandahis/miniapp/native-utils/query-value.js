"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.decodeQueryValue = void 0;
/**
 * 安全解码 navigateTo query 参数。
 * 部分真机环境下 onLoad 仍可能拿到带 %XX 的字符串，需与 encode-path-segment 一致地循环解码。
 */
function decodeQueryValue(raw) {
    let s = String(raw || '').trim();
    if (!s)
        return '';
    for (let i = 0; i < 3; i++) {
        try {
            const d = decodeURIComponent(s.replace(/\+/g, ' '));
            if (d === s)
                break;
            s = d;
        }
        catch {
            break;
        }
    }
    return s;
}
exports.decodeQueryValue = decodeQueryValue;
