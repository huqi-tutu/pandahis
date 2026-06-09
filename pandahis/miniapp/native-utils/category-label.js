"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.buildFavoriteSummary = exports.categoryLabel = void 0;
/** 盒子 category_key → 展示名（与后端 FavoriteService 一致） */
function categoryLabel(key) {
    switch (key) {
        case 'junji':
            return '君纪';
        case 'shichen':
            return '士臣';
        case 'minlu':
            return '民录';
        case 'dianzhi':
            return '典制';
        case 'shilue':
            return '史略';
        default:
            return '其他';
    }
}
exports.categoryLabel = categoryLabel;
function buildFavoriteSummary(items) {
    if (!items.length)
        return '暂无';
    const groups = {};
    for (const it of items) {
        const label = categoryLabel(it.categoryKey || '');
        groups[label] = (groups[label] || 0) + 1;
    }
    return Object.entries(groups)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 2)
        .map(([k, v]) => `${k} ${v}`)
        .join(' · ');
}
exports.buildFavoriteSummary = buildFavoriteSummary;
