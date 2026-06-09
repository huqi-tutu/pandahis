"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.categoryLabel = exports.PRD_CATEGORY_KEYS = exports.stripHtml = void 0;
function stripHtml(html) {
    if (!html)
        return '';
    return String(html).replace(/<[^>]+>/g, '');
}
exports.stripHtml = stripHtml;
/** PRD V1.1 王朝层横轴顺序 */
exports.PRD_CATEGORY_KEYS = ['junji', 'shichen', 'dianzhi', 'shilue', 'minlu'];
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
            return '事略';
        default:
            return key || '';
    }
}
exports.categoryLabel = categoryLabel;
