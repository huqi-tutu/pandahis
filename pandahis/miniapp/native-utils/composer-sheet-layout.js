"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.composerSheetViewModel = exports.shouldShowQuoteToggle = exports.estimateQuoteLines = exports.quoteClampStyle = exports.quoteClampLines = exports.readComposerSheetMetrics = exports.rpxToPx = exports.formatSheetCoordinate = exports.SHEET_COORDINATE_SEP = exports.QUOTE_COLLAPSE_MAX_LINES = void 0;
exports.QUOTE_COLLAPSE_MAX_LINES = 15;
exports.SHEET_COORDINATE_SEP = ' · ';
const REST_MAX_RATIO = 0.85;
const WINDOW_SHRUNK_PX = 40;
const PADDING_TOP_RPX = 28;
const PADDING_BOTTOM_RPX = 28;
const HEADER_RPX = 80;
const COMPOSER_CHROME_RPX = 200;
const TEXTAREA_REST_RPX = 220;
const TEXTAREA_KEYBOARD_RPX = 168;
const TEXTAREA_MIN_RPX = 128;
const TEXTAREA_FLOOR_PX = 40;
const MIN_BODY_PX = 56;
const QUOTE_FONT_RPX = 26;
const CARD_INSET_RPX = 56;
const QUOTE_INSET_RPX = 36;
function formatSheetCoordinate(civilizationName, dynastyName, boxTitle) {
    const parts = [];
    for (const raw of [civilizationName, dynastyName, boxTitle]) {
        const part = String(raw || '').trim();
        if (!part)
            continue;
        if (parts[parts.length - 1] === part)
            continue;
        parts.push(part);
    }
    return parts.join(exports.SHEET_COORDINATE_SEP);
}
exports.formatSheetCoordinate = formatSheetCoordinate;
function rpxToPx(rpx, windowWidth) {
    const width = windowWidth > 0 ? windowWidth : 375;
    return Math.round((rpx * width) / 750);
}
exports.rpxToPx = rpxToPx;
function readComposerSheetMetrics() {
    try {
        const sys = wx.getSystemInfoSync();
        const windowHeight = Math.max(1, Math.floor(Number(sys.windowHeight) || 667));
        const windowWidth = Math.max(1, Math.floor(Number(sys.windowWidth) || 375));
        const insets = sys.safeAreaInsets;
        let safeAreaBottom = 0;
        if (typeof (insets === null || insets === void 0 ? void 0 : insets.bottom) === 'number') {
            safeAreaBottom = Math.max(0, Math.floor(insets.bottom));
        }
        else if (sys.safeArea && typeof sys.screenHeight === 'number') {
            safeAreaBottom = Math.max(0, Math.floor(sys.screenHeight - sys.safeArea.bottom));
        }
        return { windowHeight, windowWidth, safeAreaBottom };
    }
    catch {
        return { windowHeight: 667, windowWidth: 375, safeAreaBottom: 0 };
    }
}
exports.readComposerSheetMetrics = readComposerSheetMetrics;
function quoteClampLines(input) {
    if (input.mode !== 'edit')
        return 0;
    if (input.keyboardOpen)
        return 0;
    if (!input.quoteNeedsCollapse)
        return 0;
    if (input.quoteExpanded)
        return 0;
    return exports.QUOTE_COLLAPSE_MAX_LINES;
}
exports.quoteClampLines = quoteClampLines;
function quoteClampStyle(maxLines) {
    if (maxLines <= 0)
        return '';
    return [
        'display:-webkit-box',
        '-webkit-box-orient:vertical',
        `-webkit-line-clamp:${maxLines}`,
        'overflow:hidden',
        'text-overflow:ellipsis',
    ].join(';');
}
exports.quoteClampStyle = quoteClampStyle;
function estimateQuoteLines(selectedText, windowWidth) {
    const content = String(selectedText || '');
    if (!content)
        return 0;
    const fontPx = Math.max(1, rpxToPx(QUOTE_FONT_RPX, windowWidth));
    const innerPx = Math.max(fontPx, windowWidth - rpxToPx(CARD_INSET_RPX + QUOTE_INSET_RPX, windowWidth));
    const charsPerLine = Math.max(1, Math.floor(innerPx / fontPx));
    return content.split('\n').reduce((sum, line) => {
        const length = Array.from(line).length;
        if (length <= 0)
            return sum + 1;
        return sum + Math.ceil(length / charsPerLine);
    }, 0);
}
exports.estimateQuoteLines = estimateQuoteLines;
function shouldShowQuoteToggle(selectedText, mode, windowWidth) {
    if (mode !== 'edit')
        return false;
    return estimateQuoteLines(selectedText, windowWidth) > exports.QUOTE_COLLAPSE_MAX_LINES;
}
exports.shouldShowQuoteToggle = shouldShowQuoteToggle;
function composerSheetViewModel(input) {
    const windowHeight = Math.max(1, Math.floor(Number(input.windowHeight) || 667));
    const windowWidth = Math.max(1, Math.floor(Number(input.windowWidth) || 375));
    const restWindowHeight = Math.max(1, Math.floor(Number(input.restWindowHeight) || windowHeight));
    const keyboardHeight = Math.max(0, Math.floor(Number(input.keyboardHeight) || 0));
    const safeAreaBottom = Math.max(0, Math.floor(Number(input.safeAreaBottom) || 0));
    const mode = input.mode === 'view' ? 'view' : 'edit';
    const keyboardOpen = keyboardHeight > 0 || restWindowHeight - windowHeight > WINDOW_SHRUNK_PX;
    const windowShrunk = restWindowHeight - windowHeight > WINDOW_SHRUNK_PX;
    const keyboardLiftPx = windowShrunk ? 0 : keyboardHeight;
    const availablePx = Math.max(0, windowShrunk ? windowHeight : restWindowHeight - keyboardLiftPx);
    const cardMaxHeightPx = keyboardOpen ? availablePx : Math.floor(restWindowHeight * REST_MAX_RATIO);
    const cardPaddingBottomPx = rpxToPx(PADDING_BOTTOM_RPX, windowWidth) + (keyboardOpen ? 0 : safeAreaBottom);
    const paddingTopPx = rpxToPx(PADDING_TOP_RPX, windowWidth);
    const headerPx = rpxToPx(HEADER_RPX, windowWidth);
    const composerExtraPx = mode === 'edit' ? rpxToPx(COMPOSER_CHROME_RPX, windowWidth) : 0;
    const reservedPx = paddingTopPx + cardPaddingBottomPx + headerPx + composerExtraPx;
    let textareaHeightPx = 0;
    if (mode === 'edit') {
        const preferred = rpxToPx(keyboardOpen ? TEXTAREA_KEYBOARD_RPX : TEXTAREA_REST_RPX, windowWidth);
        const minTextareaPx = rpxToPx(TEXTAREA_MIN_RPX, windowWidth);
        const room = cardMaxHeightPx - reservedPx;
        if (room <= 0) {
            textareaHeightPx = TEXTAREA_FLOOR_PX;
        }
        else {
            const bodyBudget = Math.min(MIN_BODY_PX, Math.max(0, room - minTextareaPx));
            textareaHeightPx = Math.max(minTextareaPx, Math.min(preferred, room - bodyBudget));
            if (room < minTextareaPx) {
                textareaHeightPx = Math.max(TEXTAREA_FLOOR_PX, room);
            }
        }
    }
    const chromeHeightPx = reservedPx + textareaHeightPx;
    const bodyMaxHeightPx = Math.max(0, cardMaxHeightPx - chromeHeightPx);
    const quoteNeedsCollapse = shouldShowQuoteToggle(input.selectedText, mode, windowWidth);
    const quoteMaxLines = quoteClampLines({
        mode,
        keyboardOpen,
        quoteExpanded: Boolean(input.quoteExpanded),
        quoteNeedsCollapse,
    });
    const showQuoteToggle = quoteNeedsCollapse && !keyboardOpen;
    const cardHeightStyle = keyboardOpen ? `${cardMaxHeightPx}px` : 'auto';
    const bodyStyleParts = [`max-height:${bodyMaxHeightPx}px`];
    if (keyboardOpen)
        bodyStyleParts.push(`height:${bodyMaxHeightPx}px`);
    return {
        keyboardOpen,
        keyboardLiftPx,
        keyboardHeight,
        cardMaxHeightPx,
        cardPaddingBottomPx,
        cardStyle: [
            `margin-bottom:${keyboardLiftPx}px`,
            `max-height:${cardMaxHeightPx}px`,
            `height:${cardHeightStyle}`,
            `padding-bottom:${cardPaddingBottomPx}px`,
        ].join(';'),
        bodyStyle: bodyStyleParts.join(';'),
        bodyMaxHeightPx,
        chromeHeightPx,
        textareaHeightPx,
        quoteMaxLines,
        quoteClampClass: quoteMaxLines > 0 ? `is-clamp-${quoteMaxLines}` : '',
        quoteClampStyle: quoteClampStyle(quoteMaxLines),
        showQuoteToggle,
        quoteToggleLabel: input.quoteExpanded ? '收起' : '展开',
    };
}
exports.composerSheetViewModel = composerSheetViewModel;
