"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.formatEntrySourceLabel = void 0;
/** 数据来源：API entrySource → 展示文案 */
function formatEntrySourceLabel(value) {
    const v = String(value || '').trim().toLowerCase();
    if (v === 'supplement')
        return '模型补全';
    if (v === 'extract')
        return '历史著作标注';
    return '';
}
exports.formatEntrySourceLabel = formatEntrySourceLabel;
