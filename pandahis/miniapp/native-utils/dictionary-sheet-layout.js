"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.computeDictionarySheetLayout = void 0;
const SCREEN_W = 750;
const H_PAD = 96;
const MAX_CARD = 300;
const MIN_CARD = 88;
const MAX_CONTENT_H = 400;
function pinyinMetrics(cardSize, count) {
    const heightRatio = count >= 4 ? 0.48 : count >= 3 ? 0.42 : 0.38;
    const fontRatio = count >= 4 ? 0.26 : count >= 3 ? 0.23 : 0.21;
    return {
        pinyinHeight: Math.max(56, Math.round(cardSize * heightRatio)),
        pinyinFontSize: Math.max(30, Math.round(cardSize * fontRatio)),
    };
}
function blockHeight(cardSize, pinyinHeight) {
    return pinyinHeight + 20 + cardSize;
}
function buildLayoutStyle(layout) {
    return [
        `--card-size:${layout.cardSize}rpx`,
        `--gap:${layout.gap}rpx`,
        `--row-gap:${layout.rowGap}rpx`,
        `--pinyin-h:${layout.pinyinHeight}rpx`,
        `--pinyin-fs:${layout.pinyinFontSize}rpx`,
        `--char-fs:${layout.charFontSize}rpx`,
    ].join(';');
}
function computeDictionarySheetLayout(count) {
    if (count <= 0) {
        const empty = {
            cols: 1,
            rows: 1,
            cardSize: MAX_CARD,
            gap: 40,
            rowGap: 0,
            pinyinHeight: 112,
            pinyinFontSize: 62,
            charFontSize: 184,
        };
        return { ...empty, layoutStyle: buildLayoutStyle(empty) };
    }
    const rows = count <= 4 ? 1 : 2;
    const cols = rows === 1 ? count : Math.min(4, Math.ceil(count / 2));
    const gap = count <= 2 ? 40 : count <= 4 ? 24 : 16;
    const rowGap = rows > 1 ? 20 : 0;
    const usableW = SCREEN_W - H_PAD;
    let cardSize = Math.floor((usableW - gap * (cols - 1)) / cols);
    cardSize = Math.min(MAX_CARD, cardSize);
    let metrics = pinyinMetrics(cardSize, count);
    let totalH = blockHeight(cardSize, metrics.pinyinHeight) * rows + rowGap * (rows - 1);
    while (cardSize > MIN_CARD && totalH > MAX_CONTENT_H) {
        cardSize -= 4;
        metrics = pinyinMetrics(cardSize, count);
        totalH = blockHeight(cardSize, metrics.pinyinHeight) * rows + rowGap * (rows - 1);
    }
    cardSize = Math.max(MIN_CARD, cardSize);
    metrics = pinyinMetrics(cardSize, count);
    const charFontSize = Math.max(64, Math.round(cardSize * 0.613));
    const base = {
        cols,
        rows,
        cardSize,
        gap,
        rowGap,
        pinyinHeight: metrics.pinyinHeight,
        pinyinFontSize: metrics.pinyinFontSize,
        charFontSize,
    };
    return {
        ...base,
        layoutStyle: buildLayoutStyle(base),
    };
}
exports.computeDictionarySheetLayout = computeDictionarySheetLayout;
