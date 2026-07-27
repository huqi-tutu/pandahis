"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.parseHistoryYearSpan = exports.formatHistoryYearToken = exports.parseHistoryYear = exports.formatYearRange = exports.formatHistoryYear = void 0;
/** 历史年份展示：公元前用 前XX */
function formatHistoryYear(y) {
    if (!Number.isFinite(y))
        return '';
    if (y === 0)
        return '公元0';
    if (y < 0)
        return `前${Math.abs(y)}`;
    return String(y);
}
exports.formatHistoryYear = formatHistoryYear;
function formatYearRange(start, end, sep = ' — ') {
    const s = start !== null && start !== void 0 ? start : 0;
    const e = end !== null && end !== void 0 ? end : s;
    return `${formatHistoryYear(s)}${sep}${formatHistoryYear(e)}`;
}
exports.formatYearRange = formatYearRange;
/** 解析年份字符串（数据 -221、展示 前221年、约前1600年 等） */
function parseHistoryYear(input) {
    if (typeof input === 'number')
        return input;
    const raw = String(input || '').trim();
    if (!raw)
        return NaN;
    if (raw === '至今' || raw === '今')
        return 2025;
    const s = raw.replace(/约/g, '').trim();
    const century = s.match(/^(-?)(\d+)世纪$/);
    if (century) {
        const neg = century[1] === '-';
        const c = parseInt(century[2], 10);
        return neg ? -(c * 100 - 50) : (c - 1) * 100 + 50;
    }
    if (s.startsWith('前')) {
        const n = parseInt(s.replace(/^前/, '').replace(/年$/, ''), 10);
        return Number.isFinite(n) ? -n : NaN;
    }
    const n = parseInt(s.replace(/年$/, ''), 10);
    return Number.isFinite(n) ? n : NaN;
}
exports.parseHistoryYear = parseHistoryYear;
/** 格式化范围片段（保留约、至今） */
function formatHistoryYearToken(token) {
    const raw = String(token || '').trim();
    if (!raw)
        return '';
    if (raw === '至今' || raw === '今')
        return '至今';
    const approx = raw.includes('约');
    const year = parseHistoryYear(raw);
    if (!Number.isFinite(year))
        return raw;
    const formatted = formatHistoryYear(year);
    return approx ? `约${formatted}` : formatted;
}
exports.formatHistoryYearToken = formatHistoryYearToken;
/** 从展示用范围字符串解析起止年（兼容 前221年 — 前206年 与旧版 -221 — -206） */
function parseHistoryYearSpan(range) {
    const parts = String(range || '').split(/\s*[—–]\s*/);
    if (parts.length < 2)
        return null;
    const start = parseHistoryYear(parts[0]);
    const end = parseHistoryYear(parts[parts.length - 1]);
    if (!Number.isFinite(start) || !Number.isFinite(end))
        return null;
    return { start, end };
}
exports.parseHistoryYearSpan = parseHistoryYearSpan;
