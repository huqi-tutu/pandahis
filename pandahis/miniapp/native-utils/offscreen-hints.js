"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.countOffscreenBottom = exports.countOffscreenRight = exports.dedupeHintItems = void 0;
function dedupeHintItems(items) {
    return items.reduce((result, item) => {
        const index = result.findIndex((candidate) => candidate.id === item.id);
        if (index < 0)
            return [...result, item];
        const current = result[index];
        const merged = {
            ...current,
            rightRpx: Math.max(current.rightRpx, item.rightRpx),
            bottomRpx: Math.max(current.bottomRpx, item.bottomRpx),
            weight: Math.max(current.weight, item.weight),
        };
        return [...result.slice(0, index), merged, ...result.slice(index + 1)];
    }, []);
}
exports.dedupeHintItems = dedupeHintItems;
function countOffscreenRight(items, visibleRightRpx, toleranceRpx = 16) {
    const boundary = visibleRightRpx + toleranceRpx;
    return items.reduce((count, item) => count + (item.rightRpx > boundary ? normalizedWeight(item.weight) : 0), 0);
}
exports.countOffscreenRight = countOffscreenRight;
function countOffscreenBottom(items, visibleBottomRpx, toleranceRpx = 16) {
    const boundary = visibleBottomRpx + toleranceRpx;
    return items.reduce((count, item) => count + (item.bottomRpx > boundary ? normalizedWeight(item.weight) : 0), 0);
}
exports.countOffscreenBottom = countOffscreenBottom;
function normalizedWeight(weight) {
    return Number.isFinite(weight) ? Math.max(1, Math.round(weight)) : 1;
}
