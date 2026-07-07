"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.categoryLabel = exports.PRD_CATEGORY_KEYS = exports.stripHtml = void 0;
function stripHtml(html) {
    if (!html)
        return '';
    return String(html).replace(/<[^>]+>/g, '');
}
exports.stripHtml = stripHtml;
/** 朝代详情固定 10 泳道顺序 */
exports.PRD_CATEGORY_KEYS = [
    'junji',
    'zongqi',
    'wenchen',
    'wujiang',
    'shilue',
    'dianzhi',
    'lunzhu',
    'huanguan',
    'shuzhong',
    'fanzhu',
];
function categoryLabel(key) {
    switch (key) {
        case 'junji':
            return '君王';
        case 'zongqi':
            return '宗戚';
        case 'wenchen':
            return '文臣';
        case 'wujiang':
            return '武将';
        case 'shilue':
            return '事略';
        case 'dianzhi':
            return '典制';
        case 'lunzhu':
            return '论著';
        case 'huanguan':
            return '宦官';
        case 'shuzhong':
            return '庶众';
        case 'fanzhu':
            return '蕃祚';
        case 'shichen':
            return '士臣';
        case 'minlu':
            return '民录';
        default:
            return key || '';
    }
}
exports.categoryLabel = categoryLabel;
