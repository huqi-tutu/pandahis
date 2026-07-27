"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.calculateSharePosterLayout = exports.MAX_QUOTE_LINES = void 0;
exports.MAX_QUOTE_LINES = 20;
const MIN_POSTER_HEIGHT = 1150;
const QUOTE_LINE_HEIGHT = 58;
const PATH_LINE_HEIGHT = 34;
const CONTENT_BEFORE_QUOTE = 328;
const QUOTE_BOTTOM_GAP = 48;
const SOURCE_FOOTER_SAFE_GAP = 64;
const FOOTER_HEIGHT = 232;
function clampCount(value, maximum) {
    if (!Number.isFinite(value))
        return 0;
    return Math.min(maximum, Math.max(0, Math.floor(value)));
}
function calculateSharePosterLayout(quoteLines, pathLines) {
    const quoteLineCount = clampCount(quoteLines, exports.MAX_QUOTE_LINES);
    const pathLineCount = clampCount(pathLines, 2);
    const sourceTop = CONTENT_BEFORE_QUOTE + quoteLineCount * QUOTE_LINE_HEIGHT + QUOTE_BOTTOM_GAP;
    const sourceBottom = sourceTop + pathLineCount * PATH_LINE_HEIGHT;
    const posterHeight = Math.max(MIN_POSTER_HEIGHT, sourceBottom + SOURCE_FOOTER_SAFE_GAP + FOOTER_HEIGHT);
    return {
        quoteLineCount,
        pathLineCount,
        sourceTop,
        sourceBottom,
        footerTop: posterHeight - FOOTER_HEIGHT,
        posterHeight,
    };
}
exports.calculateSharePosterLayout = calculateSharePosterLayout;
