"use strict";
/** 按本地日历日分组的列表工具（足迹 / 已读完等） */
Object.defineProperty(exports, "__esModule", { value: true });
exports.appendGroupedItems = exports.groupByDateKey = exports.formatClockTime = exports.formatDateSectionLabel = exports.toLocalDateKey = void 0;
/** 本地日历日 key：YYYY-MM-DD */
function toLocalDateKey(iso, now = new Date()) {
    if (!iso)
        return '';
    const d = new Date(iso);
    if (Number.isNaN(d.getTime()))
        return '';
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    // now 仅用于类型稳定；key 不依赖 now
    void now;
    return `${y}-${m}-${day}`;
}
exports.toLocalDateKey = toLocalDateKey;
/** 二级标题：今天 / 昨天 / YYYY年M月D日 */
function formatDateSectionLabel(dateKey, now = new Date()) {
    if (!dateKey)
        return '';
    const parts = dateKey.split('-').map((x) => Number(x));
    if (parts.length !== 3 || parts.some((n) => !Number.isFinite(n)))
        return dateKey;
    const [y, m, d] = parts;
    const that = new Date(y, m - 1, d).getTime();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const diffDays = Math.round((today - that) / 86400000);
    if (diffDays === 0)
        return '今天';
    if (diffDays === 1)
        return '昨天';
    if (y === now.getFullYear())
        return `${m}月${d}日`;
    return `${y}年${m}月${d}日`;
}
exports.formatDateSectionLabel = formatDateSectionLabel;
/** 卡片内时钟：HH:mm */
function formatClockTime(iso) {
    if (!iso)
        return '';
    const d = new Date(iso);
    if (Number.isNaN(d.getTime()))
        return '';
    const hh = String(d.getHours()).padStart(2, '0');
    const mm = String(d.getMinutes()).padStart(2, '0');
    return `${hh}:${mm}`;
}
exports.formatClockTime = formatClockTime;
function groupByDateKey(items, getIso) {
    const order = [];
    const map = new Map();
    for (const item of items) {
        const key = toLocalDateKey(getIso(item)) || 'unknown';
        if (!map.has(key)) {
            map.set(key, []);
            order.push(key);
        }
        map.get(key).push(item);
    }
    return order.map((dateKey) => ({
        dateKey,
        dateLabel: dateKey === 'unknown' ? '未知日期' : formatDateSectionLabel(dateKey),
        items: map.get(dateKey) || [],
    }));
}
exports.groupByDateKey = groupByDateKey;
/** 追加分页结果时合并同日分组（保持既有组顺序，新日期接在末尾） */
function appendGroupedItems(existing, incoming, getIso, getId) {
    if (!incoming.length)
        return existing;
    const next = existing.map((g) => ({
        ...g,
        items: [...g.items],
    }));
    const indexByKey = new Map(next.map((g, i) => [g.dateKey, i]));
    const seen = new Set();
    for (const g of next) {
        for (const item of g.items)
            seen.add(getId(item));
    }
    for (const item of incoming) {
        const id = getId(item);
        if (seen.has(id))
            continue;
        seen.add(id);
        const dateKey = toLocalDateKey(getIso(item)) || 'unknown';
        const idx = indexByKey.get(dateKey);
        if (idx === undefined) {
            indexByKey.set(dateKey, next.length);
            next.push({
                dateKey,
                dateLabel: dateKey === 'unknown' ? '未知日期' : formatDateSectionLabel(dateKey),
                items: [item],
            });
        }
        else {
            next[idx] = {
                ...next[idx],
                items: [...next[idx].items, item],
            };
        }
    }
    return next;
}
exports.appendGroupedItems = appendGroupedItems;
