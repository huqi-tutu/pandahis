"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.formatYearRange = exports.formatHistoryYear = void 0;
/** 历史年份展示：公元前用 -XX */
function formatHistoryYear(y) {
    if (!Number.isFinite(y))
        return '';
    if (y === 0)
        return '公元0';
    if (y < 0)
        return '-' + Math.abs(y);
    return String(y);
}
exports.formatHistoryYear = formatHistoryYear;
function formatYearRange(start, end, sep) {
    if (sep === void 0) { sep = ' — '; }
    var s = start != null ? start : 0;
    var e = end != null ? end : s;
    return formatHistoryYear(s) + sep + formatHistoryYear(e);
}
exports.formatYearRange = formatYearRange;
