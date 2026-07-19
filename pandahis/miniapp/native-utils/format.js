"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.categoryLabel = exports.highlightEmToRich = exports.extractUnitDynastyHint = exports.formatSearchPath = exports.stripHtml = exports.PRD_CATEGORY_KEYS = void 0;
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
function stripHtml(html) {
    if (!html)
        return '';
    return String(html).replace(/<[^>]+>/g, '');
}
exports.stripHtml = stripHtml;
/** 搜索路径统一为「A › B › C」展示 */
function formatSearchPath(path) {
    return String(path || '')
        .split(/[>›/\\|]+/)
        .map((s) => s.trim())
        .filter(Boolean)
        .join(' › ');
}
exports.formatSearchPath = formatSearchPath;
/** 从搜索结果的 unit 路径提取朝代名，供详情页 mock 兜底使用 */
function extractUnitDynastyHint(pathText) {
    const parts = String(pathText || '')
        .split(/[>›/\\|]+/)
        .map((s) => s.trim())
        .filter(Boolean);
    if (parts.length >= 2)
        return parts[parts.length - 1];
    return parts[0] || '';
}
exports.extractUnitDynastyHint = extractUnitDynastyHint;
/** 将搜索高亮 <em> 转为 rich-text 可渲染的 HTML */
function escapeHtml(text) {
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}
function highlightEmToRich(html) {
    const raw = String(html || '');
    if (!raw)
        return '';
    const parts = [];
    const re = /<em>(.*?)<\/em>/gi;
    let last = 0;
    let match;
    while ((match = re.exec(raw))) {
        if (match.index > last)
            parts.push(escapeHtml(raw.slice(last, match.index)));
        parts.push(`<span style="color:#C42828;font-weight:600;">${escapeHtml(match[1])}</span>`);
        last = match.index + match[0].length;
    }
    if (last < raw.length)
        parts.push(escapeHtml(raw.slice(last)));
    return parts.join('');
}
exports.highlightEmToRich = highlightEmToRich;
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
