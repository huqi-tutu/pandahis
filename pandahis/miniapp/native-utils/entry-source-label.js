"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.formatDetailSourceLabel = exports.formatEntrySourceLabel = void 0;
/** 史略条目来源：API entrySource → 展示文案 */
function formatEntrySourceLabel(value) {
    const v = String(value || '').trim().toLowerCase();
    if (v === 'supplement')
        return '模型补全';
    if (v === 'extract')
        return '历史著作标注';
    return '';
}
exports.formatEntrySourceLabel = formatEntrySourceLabel;
/** 史略详情来源：API detailSource → 展示文案 */
function formatDetailSourceLabel(value) {
    const v = String(value || '').trim().toLowerCase();
    if (v === 'compose')
        return '大模型撰写';
    if (v === 'translate')
        return '史料顺译';
    return '';
}
exports.formatDetailSourceLabel = formatDetailSourceLabel;
