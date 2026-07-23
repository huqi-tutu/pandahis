"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.toReadCompleteCardView = exports.toFootprintCardView = exports.formatVisitTime = exports.splitFavorites = exports.isDynastyFavorite = exports.toFavoriteCardView = exports.formatFavoriteDate = exports.formatYearRange = exports.formatHistoryYear = void 0;
const year_format_1 = require("./year-format");
Object.defineProperty(exports, "formatHistoryYear", { enumerable: true, get: function () { return year_format_1.formatHistoryYear; } });
Object.defineProperty(exports, "formatYearRange", { enumerable: true, get: function () { return year_format_1.formatYearRange; } });
function formatFavoriteDate(iso) {
    if (!iso)
        return '';
    const d = new Date(iso);
    if (Number.isNaN(d.getTime()))
        return '';
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const that = new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
    const diffDays = Math.round((today - that) / 86400000);
    if (diffDays === 0)
        return '今天';
    if (diffDays === 1)
        return '昨天';
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    return `${mm}-${dd}`;
}
exports.formatFavoriteDate = formatFavoriteDate;
function toFavoriteCardView(item) {
    var _a;
    const pathLabel = item.pathLabel ||
        (((_a = item.subText) === null || _a === void 0 ? void 0 : _a.includes('·')) ? item.subText.split('·').slice(1).join('·').trim() : item.subText || '');
    return {
        ...item,
        dateLabel: formatFavoriteDate(item.favoritedAt),
        yearRange: (0, year_format_1.formatYearRange)(item.startYear, item.endYear),
        pathLabel,
    };
}
exports.toFavoriteCardView = toFavoriteCardView;
function isDynastyFavorite(categoryKey) {
    return categoryKey === 'junji';
}
exports.isDynastyFavorite = isDynastyFavorite;
function splitFavorites(items) {
    const dynasty = [];
    const shilue = [];
    for (const raw of items) {
        const card = toFavoriteCardView(raw);
        if (isDynastyFavorite(raw.categoryKey)) {
            dynasty.push(card);
        }
        else {
            shilue.push(card);
        }
    }
    return { dynasty, shilue };
}
exports.splitFavorites = splitFavorites;
/** 足迹访问时间：刚刚 / N 分钟前 / 昨天 / MM-DD */
function formatVisitTime(iso) {
    if (!iso)
        return '';
    const d = new Date(iso);
    if (Number.isNaN(d.getTime()))
        return '';
    const diffMs = Date.now() - d.getTime();
    if (diffMs < 60000)
        return '刚刚';
    if (diffMs < 3600000) {
        const mins = Math.max(1, Math.floor(diffMs / 60000));
        return `${mins} 分钟前`;
    }
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const that = new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
    const diffDays = Math.round((today - that) / 86400000);
    if (diffDays === 0)
        return '今天';
    if (diffDays === 1)
        return '昨天';
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    return `${mm}-${dd}`;
}
exports.formatVisitTime = formatVisitTime;
function toFootprintCardView(item) {
    const pathLabel = item.pathLabel || item.subText || '';
    return {
        ...item,
        timeLabel: formatVisitTime(item.lastViewedAt),
        yearRange: (0, year_format_1.formatYearRange)(item.startYear, item.endYear),
        pathLabel,
    };
}
exports.toFootprintCardView = toFootprintCardView;
function toReadCompleteCardView(item) {
    const pathLabel = item.pathLabel || item.subText || '';
    return {
        ...item,
        timeLabel: formatVisitTime(item.completedAt),
        yearRange: (0, year_format_1.formatYearRange)(item.startYear, item.endYear),
        pathLabel,
    };
}
exports.toReadCompleteCardView = toReadCompleteCardView;
