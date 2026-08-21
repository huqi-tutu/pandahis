"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const api_1 = require("../../native-utils/api");
const encode_path_segment_1 = require("../../native-utils/encode-path-segment");
const favorite_unit_1 = require("../../native-utils/favorite-unit");
const router_1 = require("../../native-utils/router");
const query_value_1 = require("../../native-utils/query-value");
const year_format_1 = require("../../native-utils/year-format");
const entry_source_label_1 = require("../../native-utils/entry-source-label");
const share_poster_open_1 = require("../../native-utils/share-poster-open");
const selection_bar_position_1 = require("../../native-utils/selection-bar-position");
const correction_1 = require("../../native-utils/correction");
const load_error_message_1 = require("../../native-utils/load-error-message");
const feature_flags_1 = require("../../native-utils/feature-flags");
const matrix_adapter_1 = require("../home/matrix-adapter");
const runtime_env_1 = require("../../native-utils/runtime-env");
const offscreen_hints_1 = require("../../native-utils/offscreen-hints");
const chip_badge_tokens_1 = require("../../native-utils/chip-badge-tokens");
const format_1 = require("../../native-utils/format");
const { buildSwimMatrixFromMock, buildHeroFromMock, normalizeDynastyKey, isDegradedMockFallback, } = require('./swim-local-fallback');
const PRIORITY_OPTIONS = [
    { value: 'p0', label: '极简' },
    { value: 'p1', label: '简略' },
    { value: 'p2', label: '丰富' },
    { value: 'p3', label: '详尽' },
];
function priorityLabel(priority) {
    const hit = PRIORITY_OPTIONS.find((item) => item.value === priority);
    return (hit === null || hit === void 0 ? void 0 : hit.label) || '详尽';
}
const MAX_LANE_ROWS = 10;
const GRID_RPX = 8;
const LANE_ROW_HEIGHT_RPX = 44;
const LANE_ROW_GAP_RPX = 16;
const LANE_TRACK_PAD_VERTICAL_RPX = 24;
const CHIP_MAX_RPX = 288;
const CHIP_MIN_RPX = 80;
const CHIP_HEIGHT_RPX = 52;
/** 胶囊左右 padding 合计（与 SCSS 14+14 对齐） */
const CHIP_PAD_H_RPX = 28;
const CHIP_TITLE_RPX_PER_CHAR = 24;
/** Badge 左右 padding 合计（与 SCSS 8+8 对齐） */
const CHIP_TAG_PAD_H_RPX = 16;
const CHIP_TAG_RPX_PER_CHAR = 20;
const CHIP_INNER_GAP_RPX = 4;
const CHIP_GAP_RPX = 16;
const ROW_GAP_RPX = 16;
const EDGE_GAP_RPX = 24;
const MORE_WIDTH_RPX = 112;
const MORE_GAP_RPX = 20;
const CANVAS_PAD_LEFT_RPX = 40;
const BAND_GAP_RPX = 24;
const BAND_PAD_RPX = 16;
const MIN_BAND_HEIGHT_RPX = 56;
/** 时间轴行 / 吸顶占位块高度（与 dyn-panel-axis-spacer 一致） */
const PANEL_AXIS_BLOCK_RPX = 86;
/** 外框吸顶解绑滞后（px），仅防临界抖动，不能大到露出「过冲再弹回」 */
const AXIS_PIN_HYSTERESIS_PX = 2;
const CONTINUATION_CUE_THROTTLE_MS = 120;
const CONTINUATION_CUE_TOLERANCE_RPX = 16;
const CONTINUATION_CUE_BOTTOM_RESERVE_RPX = 48;
function roundScrollLeft(left) {
    return Math.round(left);
}
function snapRpx(value) {
    if (value <= 0)
        return 0;
    return Math.max(GRID_RPX, Math.round(value / GRID_RPX) * GRID_RPX);
}
function laneTrackHeight(rowCount) {
    const rows = Math.max(1, rowCount || 1);
    return LANE_TRACK_PAD_VERTICAL_RPX + rows * CHIP_HEIGHT_RPX + (rows - 1) * ROW_GAP_RPX;
}
const MIN_BUCKET_YEARS = 10;
const MAX_BUCKET_YEARS = 30;
function resolveBucketYears(span, overflowCount) {
    if (overflowCount <= 0)
        return span;
    if (span <= MAX_BUCKET_YEARS)
        return span;
    const minBuckets = Math.max(1, Math.ceil(overflowCount / 12));
    const maxBuckets = Math.max(minBuckets, Math.ceil(overflowCount / 5));
    const targetBuckets = Math.min(Math.floor(span / MIN_BUCKET_YEARS), Math.floor((minBuckets + maxBuckets) / 2));
    const bucketYears = Math.ceil(span / Math.max(1, targetBuckets));
    return Math.max(MIN_BUCKET_YEARS, Math.min(MAX_BUCKET_YEARS, bucketYears));
}
const BUCKET_CHIP_TITLE = '查看更多';
/** 与后端 UnitSwimMatrixService 一致：君王/诸侯锚定在在位起始年 */
const ANCHOR_AT_START_LANE_KEYS = new Set(['junji', 'zhuhou']);
function parseBucketMemberCount(title) {
    const match = String(title || '').match(/\+(\d+)$/);
    return match ? Number(match[1]) : 0;
}
function bucketTitle(laneLabel, count) {
    return BUCKET_CHIP_TITLE;
}
function usesAnchorAtStart(laneKey) {
    return ANCHOR_AT_START_LANE_KEYS.has(String(laneKey || '').trim());
}
function anchorYearOfBar(bar, laneKey) {
    if (usesAnchorAtStart(laneKey)) {
        if (typeof bar.startYear === 'number')
            return bar.startYear;
        if (typeof bar.peakYear === 'number')
            return bar.peakYear;
        return 0;
    }
    if (typeof bar.peakYear === 'number')
        return bar.peakYear;
    if (typeof bar.startYear === 'number')
        return bar.startYear;
    return 0;
}
function placeBucketChips(rows, overflow, laneKey, laneLabel, startYear, endYear, sheetWidthRpx, percentForYear) {
    if (!overflow.length)
        return rows;
    const span = Math.max(1, endYear - startYear);
    const bucketYears = resolveBucketYears(span, overflow.length);
    const gapPct = CHIP_GAP_RPX / sheetWidthRpx * 100;
    const nextRows = rows.map((row) => [...row]);
    const rowEnds = nextRows.map((row) => Math.max(0, ...row.map((bar) => bar._rightPct)));
    let bucketRowIndex = -1;
    let cursor = startYear;
    let bucketIndex = 0;
    while (cursor < endYear) {
        const bucketEnd = Math.min(endYear, cursor + bucketYears);
        const members = overflow.filter((bar) => {
            const y = anchorYearOfBar(bar, laneKey);
            return y >= cursor && y < bucketEnd;
        });
        if (members.length) {
            const countTag = buildOverlayCountTag(laneLabel, members.length);
            const title = BUCKET_CHIP_TITLE;
            const chipW = estimateChipWidthRpx(title, countTag);
            const chipPct = chipW / sheetWidthRpx * 100;
            const anchorYear = Math.floor((cursor + bucketEnd) / 2);
            const centerPct = percentForYear(anchorYear);
            const edgePct = EDGE_GAP_RPX / sheetWidthRpx * 100;
            const maxLeft = 100 - (chipW + EDGE_GAP_RPX) / sheetWidthRpx * 100;
            const left = Math.max(edgePct, Math.min(maxLeft, centerPct - chipPct / 2));
            const bucketBar = {
                title,
                chipTag: countTag,
                boxId: `BUCKET_${laneKey}_${bucketIndex}`,
                left: `${left.toFixed(2)}%`,
                width: `${chipPct.toFixed(2)}%`,
                unitLeft: `${left.toFixed(2)}%`,
                unitWidth: `${chipPct.toFixed(2)}%`,
                chipLeft: `${left.toFixed(2)}%`,
                chipWidth: `${chipW}rpx`,
                lineLeftW: '0rpx',
                lineRightL: '0rpx',
                lineRightW: '0rpx',
                priority: 'p3',
                type: 'overflow_bucket',
                timeRange: `${(0, year_format_1.formatHistoryYear)(cursor)} — ${(0, year_format_1.formatHistoryYear)(bucketEnd)}`,
                startYear: cursor,
                endYear: bucketEnd,
                peakYear: anchorYear,
                heightRpx: CHIP_HEIGHT_RPX,
                _leftPct: left,
                _rightPct: left + chipPct,
                _priorityRank: 3,
                _globalIdNumber: 0,
            };
            let assigned = -1;
            if (bucketRowIndex === -1) {
                for (let rowIndex = 0; rowIndex < nextRows.length; rowIndex++) {
                    if (rowEnds[rowIndex] + gapPct <= bucketBar._leftPct) {
                        assigned = rowIndex;
                        rowEnds[rowIndex] = bucketBar._rightPct;
                        nextRows[rowIndex] = [...nextRows[rowIndex], bucketBar].sort((a, b) => a._leftPct - b._leftPct);
                        break;
                    }
                }
            }
            else if (rowEnds[bucketRowIndex] + gapPct <= bucketBar._leftPct) {
                assigned = bucketRowIndex;
                rowEnds[bucketRowIndex] = bucketBar._rightPct;
                nextRows[bucketRowIndex] = [...nextRows[bucketRowIndex], bucketBar]
                    .sort((a, b) => a._leftPct - b._leftPct);
            }
            if (assigned === -1) {
                if (bucketRowIndex === -1) {
                    bucketRowIndex = nextRows.length;
                    nextRows.push([bucketBar]);
                    rowEnds.push(bucketBar._rightPct);
                }
                else {
                    rowEnds[bucketRowIndex] = Math.max(rowEnds[bucketRowIndex], bucketBar._rightPct);
                    nextRows[bucketRowIndex] = [...nextRows[bucketRowIndex], bucketBar]
                        .sort((a, b) => a._leftPct - b._leftPct);
                }
            }
            bucketIndex += 1;
        }
        cursor = bucketEnd;
    }
    return nextRows;
}
function collectMatrixBoxIds(swim) {
    var _a;
    const ids = [];
    for (const lane of (swim === null || swim === void 0 ? void 0 : swim.lanes) || []) {
        const fullView = (_a = lane.priorityViews) === null || _a === void 0 ? void 0 : _a.p3;
        const rows = (fullView === null || fullView === void 0 ? void 0 : fullView.collapsedRows) || lane.collapsedRows || [];
        for (const row of rows) {
            for (const bar of row) {
                if (bar === null || bar === void 0 ? void 0 : bar.boxId)
                    ids.push(bar.boxId);
            }
        }
        for (const bar of (fullView === null || fullView === void 0 ? void 0 : fullView.extraBars) || lane.extraBars || []) {
            if (bar === null || bar === void 0 ? void 0 : bar.boxId)
                ids.push(bar.boxId);
        }
    }
    return Array.from(new Set(ids));
}
function findSwimBar(swim, boxId) {
    var _a;
    if (!((_a = swim === null || swim === void 0 ? void 0 : swim.lanes) === null || _a === void 0 ? void 0 : _a.length) || !boxId)
        return null;
    for (const lane of swim.lanes) {
        const rows = lane.collapsedRows || [];
        for (const row of rows) {
            for (const bar of row) {
                if ((bar === null || bar === void 0 ? void 0 : bar.boxId) === boxId)
                    return bar;
            }
        }
        for (const bar of lane.extraBars || []) {
            if ((bar === null || bar === void 0 ? void 0 : bar.boxId) === boxId)
                return bar;
        }
    }
    return null;
}
function parseConcurrentLabel(label) {
    const sep = label.indexOf('·');
    if (sep < 0)
        return { civ: '', title: String(label || '').trim() };
    return { civ: label.slice(0, sep).trim(), title: label.slice(sep + 1).trim() };
}
function isHuaxiaCivName(civ) {
    return String(civ || '').trim() === '华夏';
}
function resolveConcurrentTabs(swim, currentUnitId, heroCivLine, dynastyTitle) {
    var _a;
    if ((_a = swim.concurrentTabs) === null || _a === void 0 ? void 0 : _a.length)
        return swim.concurrentTabs;
    const selfLabel = `${heroCivLine || '华夏'}·${dynastyTitle}`;
    return (swim.concurrentItems || []).map((label) => {
        const parsed = parseConcurrentLabel(label);
        const civ = parsed.civ || heroCivLine || '华夏';
        const title = parsed.title || label;
        const isSelf = label === selfLabel || (civ === heroCivLine && title === dynastyTitle);
        const dynastyId = isSelf
            ? currentUnitId
            : ((0, matrix_adapter_1.resolveDetailUnitIds)('', title)[0] || '');
        return { label, civilizationName: civ, dynastyId };
    });
}
function resolveActiveConcurrentIndex(tabs, unitId, selfLabel) {
    const byId = tabs.findIndex((tab) => tab.dynastyId && tab.dynastyId === unitId);
    if (byId >= 0)
        return byId;
    const byLabel = tabs.findIndex((tab) => tab.label === selfLabel);
    if (byLabel >= 0)
        return byLabel;
    return 0;
}
function continuationWeight(bar) {
    var _a;
    if (bar.type !== 'overflow_bucket')
        return 1;
    const count = parseInt(((_a = String(bar.chipTag || '').match(/^\d+/)) === null || _a === void 0 ? void 0 : _a[0]) || '1', 10);
    return Number.isFinite(count) ? Math.max(1, count) : 1;
}
function buildContinuationItems(swim) {
    var _a;
    const sheetWidthRpx = swim.sheetWidthRpx || 1440;
    const padLeftRpx = (_a = swim.canvasPadLeftRpx) !== null && _a !== void 0 ? _a : CANVAS_PAD_LEFT_RPX;
    const items = (swim.lanes || []).flatMap((lane) => (lane.collapsedRows || []).flatMap((row) => row.map((bar) => {
        const leftPct = parseFloat(String(bar.left || '0').replace('%', ''));
        const chipWidthRpx = parseFloat(String(bar.chipWidth || '0').replace('rpx', ''));
        const topRpx = Number(bar.topRpx || 0);
        const heightRpx = Number(bar.heightRpx || CHIP_HEIGHT_RPX);
        return {
            id: bar.boxId,
            rightRpx: padLeftRpx
                + (Number.isFinite(leftPct) ? leftPct : 0) / 100 * sheetWidthRpx
                + (Number.isFinite(chipWidthRpx) ? chipWidthRpx : 0),
            bottomRpx: topRpx + heightRpx / 2,
            weight: continuationWeight(bar),
        };
    })));
    return (0, offscreen_hints_1.dedupeHintItems)(items);
}
function percentForYearOnSwim(swim, year) {
    const clamped = Math.max(swim.startYear, Math.min(swim.endYear, year));
    const segments = swim.timeSegments || [];
    if (segments.length) {
        for (const seg of segments) {
            if (clamped < seg.startYear || clamped > seg.endYear)
                continue;
            const segLeft = parseFloat(String(seg.left).replace('%', ''));
            const segWidth = parseFloat(String(seg.width).replace('%', ''));
            const segSpan = Math.max(1, seg.endYear - seg.startYear);
            return segLeft + ((clamped - seg.startYear) / segSpan) * segWidth;
        }
    }
    const span = Math.max(1, swim.endYear - swim.startYear);
    return ((clamped - swim.startYear) / span) * 100;
}
function splitIntroParagraphs(intro) {
    const text = (intro || '').trim() || '空';
    return text.split(/\n\n+/).map((p) => p.trim()).filter(Boolean);
}
function slimSwimMatrixForView(swim) {
    return {
        ...swim,
        lanes: (swim.lanes || []).map((lane) => {
            const { priorityViews, ...rest } = lane;
            return rest;
        }),
    };
}
function warnIfDegradedMock(swim) {
    if (!isDegradedMockFallback(swim))
        return;
    wx.showToast({
        title: '朝代数据加载失败，仅显示本地君王数据',
        icon: 'none',
        duration: 3500,
    });
}
function tryLoadLocalMock(dynastyName, unitId) {
    var _a;
    const key = normalizeDynastyKey(dynastyName);
    if (!key)
        return null;
    try {
        const swimMatrix = buildSwimMatrixFromMock(key);
        if (!((_a = swimMatrix === null || swimMatrix === void 0 ? void 0 : swimMatrix.lanes) === null || _a === void 0 ? void 0 : _a.length))
            return null;
        const hero = buildHeroFromMock(swimMatrix, unitId || key, key);
        return { hero, swim: swimMatrix };
    }
    catch (err) {
        console.warn('[dynasty-detail] local mock failed', err);
        return null;
    }
}
/* ── 生成20年间隔时间轴刻度 ── */
const TARGET_TICK_SPACING_RPX = 96;
const MIN_LABEL_SPACING_RPX = 104;
function niceTickStep(raw) {
    if (raw <= 1)
        return 1;
    if (raw <= 2)
        return 2;
    if (raw <= 5)
        return 5;
    if (raw <= 10)
        return 10;
    if (raw <= 20)
        return 20;
    if (raw <= 25)
        return 25;
    if (raw <= 50)
        return 50;
    if (raw <= 100)
        return 100;
    if (raw <= 200)
        return 200;
    if (raw <= 500)
        return 500;
    return 1000;
}
function computeTickStep(span, sheetWidthRpx) {
    const yearsPerTickGrid = (TARGET_TICK_SPACING_RPX / Math.max(1, sheetWidthRpx)) * span;
    const yearsPerTickLabel = (MIN_LABEL_SPACING_RPX / Math.max(1, sheetWidthRpx)) * span;
    return niceTickStep(Math.max(yearsPerTickGrid, yearsPerTickLabel));
}
function roundUpToStep(year, step) {
    if (step <= 1)
        return year;
    const rem = ((year % step) + step) % step;
    if (rem === 0)
        return year;
    return year + (step - rem);
}
function generateTimelineTicks(startYear, endYear, originalSheetWidthRpx) {
    const span = endYear - startYear;
    const newSheetWidthRpx = Math.round(originalSheetWidthRpx);
    const ticks = [];
    const step = computeTickStep(span, newSheetWidthRpx);
    ticks.push({ label: (0, year_format_1.formatHistoryYear)(startYear), left: '0%', edgeStart: true, hideLabel: false });
    let tickYear = roundUpToStep(startYear + 1, step);
    while (tickYear < endYear) {
        const left = ((tickYear - startYear) / span) * 100;
        const hideLabel = tickYear - startYear < step || endYear - tickYear < step;
        ticks.push({ label: (0, year_format_1.formatHistoryYear)(tickYear), left: `${left}%`, hideLabel });
        tickYear += step;
    }
    // 泳道网格线：与时间轴刻度对齐，起点/终点也各自补一条，避免边界处刻度与网格线脱节
    const gridLines = [
        { left: '0%' },
        ...ticks.filter(t => t.left !== '0%').map(t => ({ left: t.left })),
        { left: '100%' },
    ];
    return { ticks, endLabel: (0, year_format_1.formatHistoryYear)(endYear), sheetWidthRpx: newSheetWidthRpx, gridLines };
}
function visibleLength(value) {
    const trimmed = String(value || '').trim();
    return Array.from(trimmed).length;
}
function formatPriorityLabel(priority) {
    const p = String(priority || '').trim().toLowerCase();
    if (!p)
        return '';
    return p.toUpperCase();
}
function formatCoordinateLabel(raw) {
    return String(raw !== null && raw !== void 0 ? raw : '').trim();
}
function formatCoordinatePath(bar) {
    return [
        formatCoordinateLabel(bar === null || bar === void 0 ? void 0 : bar.civilizationName),
        formatCoordinateLabel(bar === null || bar === void 0 ? void 0 : bar.dynastyName),
        formatCoordinateLabel(bar === null || bar === void 0 ? void 0 : bar.regimeName),
        formatCoordinateLabel(bar === null || bar === void 0 ? void 0 : bar.emperorName),
    ]
        .filter(Boolean)
        .join('・');
}
function formatPeakSummary(year, reason) {
    const y = String(year !== null && year !== void 0 ? year : '').trim();
    const r = String(reason !== null && reason !== void 0 ? reason : '').trim();
    if (y && r)
        return `${y}，${r}`;
    return y || r;
}
function splitTimeRangeLabels(bar, fallbackRange) {
    if ((bar === null || bar === void 0 ? void 0 : bar.startYear) != null && (bar === null || bar === void 0 ? void 0 : bar.endYear) != null) {
        return {
            start: (0, year_format_1.formatHistoryYear)(bar.startYear),
            end: (0, year_format_1.formatHistoryYear)(bar.endYear),
        };
    }
    const parts = String(fallbackRange || '').split(/\s*[—–]\s*/);
    if (parts.length >= 2) {
        return {
            start: (0, year_format_1.formatHistoryYearToken)(parts[0]),
            end: (0, year_format_1.formatHistoryYearToken)(parts[parts.length - 1]),
        };
    }
    const single = (0, year_format_1.formatHistoryYearToken)(String(fallbackRange || '').trim());
    return { start: single, end: '' };
}
function estimateChipWidthRpx(title, chipTag) {
    const titleLen = visibleLength(title);
    const tag = String(chipTag || '').trim();
    let tagW = 0;
    if (tag) {
        tagW = CHIP_TAG_PAD_H_RPX + visibleLength(tag) * CHIP_TAG_RPX_PER_CHAR + CHIP_INNER_GAP_RPX;
    }
    const raw = CHIP_PAD_H_RPX + titleLen * CHIP_TITLE_RPX_PER_CHAR + tagW;
    return snapRpx(Math.max(CHIP_MIN_RPX, Math.min(CHIP_MAX_RPX, raw)));
}
function chipWidthRpxFromBar(bar) {
    return estimateChipWidthRpx(bar.title, bar.chipTag);
}
/** 后端仍返回旧固定宽时，按宽度差回推 left，保持峰值年居中 */
function adjustLeftForChipWidth(bar, chipW, sheetWidthRpx) {
    const apiMatch = String(bar.chipWidth || '').match(/^(\d+)rpx$/);
    const apiW = apiMatch ? parseInt(apiMatch[1], 10) : chipW;
    const leftStr = bar.left || bar.unitLeft || '0%';
    const leftPct = parseFloat(String(leftStr).replace('%', ''));
    if (!Number.isFinite(leftPct) || apiW >= chipW)
        return leftStr;
    const shiftPct = ((chipW - apiW) / 2) / sheetWidthRpx * 100;
    return `${Math.max(0, leftPct - shiftPct).toFixed(2)}%`;
}
function chipHeightRpx(bar) {
    return bar.heightRpx || CHIP_HEIGHT_RPX;
}
function withBucketChipMeta(bar, laneLabel = '') {
    if (bar.type !== 'overflow_bucket')
        return bar;
    if (bar.title === BUCKET_CHIP_TITLE && bar.chipTag)
        return bar;
    let count = 0;
    const tagMatch = String(bar.chipTag || '').match(/^(\d+)位/);
    if (tagMatch)
        count = Number(tagMatch[1]);
    if (!count)
        count = parseBucketMemberCount(bar.title);
    return {
        ...bar,
        title: BUCKET_CHIP_TITLE,
        chipTag: buildOverlayCountTag(laneLabel, count),
    };
}
function buildOverlayCountTag(label, count) {
    const category = String(label || '史略').trim();
    return `${Math.max(0, count)}位${category}`;
}
function hasLaneContent(lane) {
    var _a, _b;
    if (((_a = lane.totalCount) !== null && _a !== void 0 ? _a : 0) > 0)
        return true;
    if (((_b = lane.visibleCount) !== null && _b !== void 0 ? _b : 0) > 0)
        return true;
    const rows = lane.collapsedRows || [];
    return rows.some((row) => (row || []).length > 0);
}
function orderSwimLanes(lanes) {
    const byKey = new Map(lanes.map((lane) => [lane.key, lane]));
    return format_1.PRD_CATEGORY_KEYS
        .map((key) => byKey.get(key))
        .filter((lane) => !!lane);
}
function resolveCanvasHeightRpx(categoryBands) {
    if (!categoryBands.length) {
        return snapRpx(MIN_BAND_HEIGHT_RPX + BAND_PAD_RPX * 2);
    }
    const last = categoryBands[categoryBands.length - 1];
    return snapRpx(last.topRpx + last.heightRpx + BAND_PAD_RPX);
}
function composeCanvasLayout(swim, lanes) {
    var _a, _b, _c, _d;
    const categoryBands = [];
    const canvasLanes = [];
    let cursor = BAND_PAD_RPX;
    const sheetWidthRpx = swim.sheetWidthRpx || 1440;
    const visibleLanes = orderSwimLanes(lanes);
    for (const lane of visibleLanes) {
        const contentRows = lane.collapsedRows || [];
        const hasRows = contentRows.some((row) => (row || []).length > 0);
        const rowCount = Math.max(1, hasRows ? contentRows.length : 1);
        const trackHeight = snapRpx(LANE_TRACK_PAD_VERTICAL_RPX + rowCount * CHIP_HEIGHT_RPX + (rowCount - 1) * ROW_GAP_RPX);
        const bandHeight = Math.max(MIN_BAND_HEIGHT_RPX, trackHeight);
        const canvasRows = [];
        if (hasRows) {
            contentRows.forEach((row, rowIndex) => {
                const topRpx = snapRpx(cursor + BAND_PAD_RPX + rowIndex * (CHIP_HEIGHT_RPX + ROW_GAP_RPX));
                canvasRows.push(row.map((bar) => {
                    const enriched = withBucketChipMeta(bar, lane.label);
                    const chipW = chipWidthRpxFromBar(enriched);
                    const left = adjustLeftForChipWidth(enriched, chipW, sheetWidthRpx);
                    return {
                        ...enriched,
                        left,
                        topRpx,
                        heightRpx: chipHeightRpx(enriched),
                        chipWidth: `${chipW}rpx`,
                        width: `${(chipW / sheetWidthRpx * 100).toFixed(2)}%`,
                    };
                }));
            });
        }
        else {
            canvasRows.push([]);
        }
        categoryBands.push({
            key: lane.key,
            label: lane.label,
            // 类目色固定映射（视觉规范 v3）：前端为准，覆盖后端旧色值
            borderColor: (0, chip_badge_tokens_1.categoryRailColor)(lane.key, lane.borderColor),
            topRpx: cursor,
            heightRpx: bandHeight,
            readProgressText: lane.readProgressText || `${(_a = lane.readCount) !== null && _a !== void 0 ? _a : 0}/${(_b = lane.totalCount) !== null && _b !== void 0 ? _b : 0}`,
            totalCount: lane.totalCount,
        });
        canvasLanes.push({
            ...lane,
            bandTopRpx: cursor,
            bandHeightRpx: bandHeight,
            moreTopRpx: snapRpx(cursor + bandHeight / 2),
            trackHeightRpx: bandHeight,
            collapsedRows: canvasRows.length ? canvasRows : [[]],
        });
        cursor += bandHeight + BAND_GAP_RPX;
    }
    const canvasHeightRpx = resolveCanvasHeightRpx(categoryBands);
    const panelSheetHeightRpx = snapRpx(PANEL_AXIS_BLOCK_RPX + canvasHeightRpx);
    return {
        ...swim,
        lanes: canvasLanes,
        categoryBands,
        canvasHeightRpx,
        panelSheetHeightRpx,
        canvasPadLeftRpx: (_c = swim.canvasPadLeftRpx) !== null && _c !== void 0 ? _c : CANVAS_PAD_LEFT_RPX,
        canvasWidthRpx: (swim.sheetWidthRpx || 1440) + ((_d = swim.canvasPadLeftRpx) !== null && _d !== void 0 ? _d : CANVAS_PAD_LEFT_RPX),
    };
}
function stripLegacyBarFields(bar) {
    const { _leftPct, _rightPct, _priorityRank, _globalIdNumber, ...rest } = bar;
    return rest;
}
function enrichApiLaneView(lane, view, swim, sheetWidthRpx) {
    const extra = view.extraBars || [];
    const hasBuckets = (view.collapsedRows || []).some((row) => row.some((bar) => bar.type === 'overflow_bucket'));
    if (!extra.length || hasBuckets) {
        return view;
    }
    const rows = (view.collapsedRows || [[]]).map((row) => row.map((bar) => prepareLegacyBar(bar, sheetWidthRpx)));
    const extraPrepared = extra.map((bar) => prepareLegacyBar(bar, sheetWidthRpx));
    const rowsWithBuckets = placeBucketChips(rows.length ? rows : [[]], extraPrepared, lane.key, lane.label, swim.startYear, swim.endYear, sheetWidthRpx, (year) => percentForYearOnSwim(swim, year));
    const collapsedRows = rowsWithBuckets.map((row) => row.map(stripLegacyBarFields));
    const bucketCount = collapsedRows.reduce((count, row) => count + row.filter((bar) => bar.type === 'overflow_bucket').length, 0);
    const individualCount = collapsedRows.reduce((count, row) => count + row.filter((bar) => bar.type !== 'overflow_bucket').length, 0);
    return {
        ...view,
        collapsedRows,
        hasMore: false,
        rowCount: Math.max(1, collapsedRows.length),
        trackHeightRpx: laneTrackHeight(collapsedRows.length),
        visibleCount: individualCount + bucketCount,
    };
}
function applyPriorityView(swim, priority) {
    const sheetWidthRpx = swim.sheetWidthRpx || 1440;
    const lanes = (swim.lanes || []).map((lane) => {
        var _a;
        const view = (_a = lane.priorityViews) === null || _a === void 0 ? void 0 : _a[priority];
        if (!view) {
            return normalizeLegacyLane(lane, sheetWidthRpx, priority, swim);
        }
        const enriched = enrichApiLaneView(lane, view, swim, sheetWidthRpx);
        return {
            ...lane,
            collapsedRows: enriched.collapsedRows || [[]],
            hasMore: enriched.hasMore,
            moreCount: enriched.moreCount,
            moreBarLeft: enriched.moreBarLeft,
            moreBarWidth: enriched.moreBarWidth,
            extraBars: enriched.extraBars || [],
            rowCount: enriched.rowCount,
            trackHeightRpx: enriched.trackHeightRpx,
            visibleCount: enriched.visibleCount,
        };
    });
    return composeCanvasLayout({ ...swim, sheetWidthRpx }, lanes);
}
function estimateSheetWidth(swim) {
    const base = swim.sheetWidthRpx || 1440;
    const maxBars = Math.max(0, ...(swim.lanes || []).map((lane) => {
        var _a;
        const view = (_a = lane.priorityViews) === null || _a === void 0 ? void 0 : _a.p3;
        if (view)
            return view.visibleCount;
        return (lane.collapsedRows || []).reduce((count, row) => count + row.length, 0) + (lane.extraBars || []).length;
    }));
    const perRow = Math.max(1, Math.ceil(maxBars / MAX_LANE_ROWS));
    const needed = EDGE_GAP_RPX + perRow * CHIP_MAX_RPX + Math.max(0, perRow - 1) * CHIP_GAP_RPX + MORE_GAP_RPX + MORE_WIDTH_RPX + EDGE_GAP_RPX;
    return Math.max(base, Math.min(base * 4, needed));
}
function isOverflowBucketBar(bar) {
    return bar.type === 'overflow_bucket';
}
function normalizeLegacyLane(lane, sheetWidthRpx, priority, swim) {
    var _a;
    const allBars = [...(lane.collapsedRows || []).flat(), ...(lane.extraBars || [])]
        .filter((bar) => !isOverflowBucketBar(bar))
        .map((bar) => prepareLegacyBar(bar, sheetWidthRpx))
        .sort(compareLegacyBars);
    const maxPriority = priorityRank(priority);
    const candidates = allBars.filter((bar) => priorityRank(bar.priority) <= maxPriority);
    const hiddenByPriority = allBars.filter((bar) => priorityRank(bar.priority) > maxPriority);
    const packed = packLegacyBars(candidates, sheetWidthRpx);
    const extraBars = [...hiddenByPriority, ...packed.extra].sort(compareLegacyBars);
    const rowsWithBuckets = placeBucketChips(packed.rows.length ? packed.rows : [[]], extraBars, lane.key, lane.label, swim.startYear, swim.endYear, sheetWidthRpx, (year) => percentForYearOnSwim(swim, year));
    const bucketCount = rowsWithBuckets.reduce((count, row) => count + row.filter((bar) => bar.type === 'overflow_bucket').length, 0);
    const individualCount = rowsWithBuckets.reduce((count, row) => count + row.filter((bar) => bar.type !== 'overflow_bucket').length, 0);
    return {
        ...lane,
        collapsedRows: rowsWithBuckets.map((row) => row.map(stripLegacyBarFields)),
        hasMore: false,
        moreCount: extraBars.length,
        moreBarLeft: `${moreLeftPct(sheetWidthRpx).toFixed(2)}%`,
        moreBarWidth: lane.moreBarWidth || '12%',
        extraBars,
        rowCount: Math.max(1, rowsWithBuckets.length),
        trackHeightRpx: laneTrackHeight(rowsWithBuckets.length),
        visibleCount: individualCount + bucketCount,
        totalCount: (_a = lane.totalCount) !== null && _a !== void 0 ? _a : individualCount + bucketCount,
    };
}
function prepareLegacyBar(bar, sheetWidthRpx) {
    const rawLeft = parseFloat(String(bar.left || bar.unitLeft || '0').replace('%', ''));
    const edgePct = 20 / sheetWidthRpx * 100;
    const chipW = chipWidthRpxFromBar(bar);
    const chipPct = chipW / sheetWidthRpx * 100;
    const maxLeft = 100 - (chipW + EDGE_GAP_RPX) / sheetWidthRpx * 100;
    const left = Math.max(edgePct, Math.min(maxLeft, Number.isFinite(rawLeft) ? rawLeft : 0));
    const normalized = {
        ...bar,
        left: `${left.toFixed(2)}%`,
        width: `${chipPct.toFixed(2)}%`,
        chipWidth: bar.chipWidth || `${chipW}rpx`,
        heightRpx: chipHeightRpx(bar),
        _leftPct: left,
        _rightPct: left + chipPct,
        _priorityRank: priorityRank(bar.priority),
        _globalIdNumber: parseGlobalIdNumber(bar.boxId),
    };
    return normalized;
}
function packLegacyBars(bars, sheetWidthRpx) {
    const rows = [];
    const extra = [];
    const gapPct = CHIP_GAP_RPX / sheetWidthRpx * 100;
    for (const bar of bars) {
        let assigned = -1;
        for (let rowIndex = 0; rowIndex < rows.length; rowIndex++) {
            if (canFitRow(rows[rowIndex], bar, gapPct)) {
                assigned = rowIndex;
                rows[rowIndex] = [...rows[rowIndex], bar].sort((a, b) => a._leftPct - b._leftPct);
                break;
            }
        }
        if (assigned === -1) {
            if (rows.length >= MAX_LANE_ROWS) {
                extra.push(bar);
            }
            else {
                rows.push([bar]);
            }
        }
    }
    return { rows, extra };
}
function canFitRow(row, bar, gapPct) {
    return row.every((existing) => bar._rightPct + gapPct <= existing._leftPct || existing._rightPct + gapPct <= bar._leftPct);
}
function compareLegacyBars(a, b) {
    if (a._priorityRank !== b._priorityRank)
        return a._priorityRank - b._priorityRank;
    if (a._leftPct !== b._leftPct)
        return a._leftPct - b._leftPct;
    return a._globalIdNumber - b._globalIdNumber;
}
function priorityRank(priority) {
    const value = String(priority || 'p3').toLowerCase();
    if (value === 'p0')
        return 0;
    if (value === 'p1')
        return 1;
    if (value === 'p2')
        return 2;
    return 3;
}
function parseGlobalIdNumber(boxId) {
    const match = String(boxId || '').match(/^GLBL_(\d+)$/);
    return match ? Number(match[1]) : Number.MAX_SAFE_INTEGER;
}
function moreLeftPct(sheetWidthRpx) {
    return 100 - ((EDGE_GAP_RPX + MORE_WIDTH_RPX) / sheetWidthRpx * 100);
}
function rpxToPx(rpx, windowWidth) {
    return Math.round(rpx * (windowWidth / 750));
}
function computeChipTooltipSafeTop(axisPinned, scrollViewTopPx, windowWidth) {
    // 吸顶条无顶 padding，高度≈外框 70rpx + 底 padding 12rpx
    const axisHeightPx = axisPinned ? rpxToPx(PANEL_AXIS_BLOCK_RPX, windowWidth) : 0;
    return scrollViewTopPx + axisHeightPx + 8;
}
function computeChipTooltipSafeBottom(windowHeight, windowWidth, safeAreaBottom = 0) {
    return windowHeight - rpxToPx(120, windowWidth) - safeAreaBottom;
}
function computeChipTooltipPlacement(rect, opts) {
    const gap = 8;
    const minTooltipH = 96;
    const centerX = rect.left + rect.width / 2;
    const left = Math.max(140, Math.min(opts.windowWidth - 140, centerX));
    const spaceAbove = rect.top - opts.safeTop;
    const spaceBelow = opts.safeBottom - rect.bottom;
    const showAbove = spaceAbove >= minTooltipH && spaceAbove >= spaceBelow;
    if (showAbove) {
        return {
            left,
            top: rect.top - gap,
            transform: 'translate(-50%, -100%)',
            origin: '50% 100%',
        };
    }
    return {
        left,
        top: rect.bottom + gap,
        transform: 'translate(-50%, 0)',
        origin: '50% 0%',
    };
}
function chipTooltipTransformWithScale(baseTransform, scale) {
    return `${baseTransform} scale(${scale.toFixed(2)})`;
}
function heroCivilizationLine(crumbText) {
    var _a;
    const normalized = String(crumbText || '').trim().replace(/[·・]/g, ' · ');
    const civ = (0, correction_1.parseCivilizationFromCrumb)(normalized);
    if (civ)
        return civ;
    return ((_a = normalized.split(' · ')[0]) === null || _a === void 0 ? void 0 : _a.trim()) || '';
}
function previewIntro(intro) {
    const paragraphs = splitIntroParagraphs(intro);
    if (paragraphs.length <= 1) {
        return { preview: paragraphs[0] || '空', canExpand: false, paragraphs };
    }
    return { preview: paragraphs[0], canExpand: true, paragraphs };
}
Page({
    swimScrollLeft: 0,
    swimSource: null,
    pageUnloaded: false,
    _loadQuery: null,
    continuationItems: [],
    continuationRatio: 1,
    continuationViewportWidthPx: 0,
    continuationWindowHeightPx: 0,
    continuationCanvasTopPx: 0,
    continuationCanvasHeightPx: 0,
    continuationPageScrollTop: 0,
    continuationGeometryReady: false,
    continuationLastUpdateAt: 0,
    continuationUpdateTimer: null,
    chipTooltipExitTimer: null,
    /** 外框顶边对齐吸顶线时的 page scrollTop；<0 表示尚未测得 */
    axisPinOffsetPx: -1,
    axisPinMeasureTimer: null,
    data: {
        unit: null,
        dynastyTitle: '',
        navTitle: '',
        heroSubLine: '',
        heroCivLine: '',
        swim: null,
        concurrentItems: [],
        concurrentTabs: [],
        activeConcurrentIndex: 0,
        relatedUnits: [],
        nextUnit: null,
        introPreview: '',
        introDisplay: '',
        introCanExpand: false,
        introParagraphs: [],
        showIntroModal: false,
        matrixBoxIds: [],
        isFav: false,
        favPartial: false,
        favToggling: false,
        headerPadPx: 88,
        scrollTop: 140,
        panelScrollLeft: 0,
        axisMirrorLeft: 0,
        axisPinned: false,
        overlayVisible: false,
        overlayCountTag: '',
        overlayBars: [],
        overlayLaneKey: '',
        continuationRightCount: 0,
        continuationBottomCount: 0,
        continuationCanvasActive: false,
        loadError: '',
        loadErrorDetail: '',
        loading: true,
        priorityOptions: PRIORITY_OPTIONS,
        activePriority: 'p3',
        activePriorityLabel: priorityLabel('p3'),
        priorityMenuVisible: false,
        priorityMenuTopPx: 0,
        priorityMenuRightPx: 24,
        chipTooltipVisible: false,
        chipTooltipPhase: 'enter',
        chipTooltipHeldId: '',
        chipTooltipTitle: '',
        chipTooltipRange: '',
        chipTooltipTag: '',
        chipTooltipPeakSummary: '',
        chipTooltipPriority: '',
        chipTooltipPrioritySummary: '',
        chipTooltipEntrySource: '',
        chipTooltipDetailSource: '',
        chipTooltipCoordinate: '',
        chipTooltipLaneKey: '',
        chipTooltipStartYear: '',
        chipTooltipEndYear: '',
        chipTooltipReignLabel: '',
        chipTooltipLeftPx: 0,
        chipTooltipTopPx: 0,
        chipTooltipBaseTransform: 'translate(-50%, -100%)',
        chipTooltipOrigin: '50% 100%',
        chipTooltipTransform: 'translate(-50%, -100%) scale(0.88)',
        correctionVisible: false,
        dictionaryVisible: false,
        dictionaryQuery: '',
        correctionSubmitting: false,
        correctionBoxId: '',
        correctionBoxTitle: '',
        correctionCivilizationName: '',
        correctionDynastyName: '',
        selectionBarVisible: false,
        selectionBarLeft: 0,
        selectionBarTop: 0,
        selectionBarPlacement: 'above',
        selectionBarText: '',
        selectionMountKey: 1,
        sharePosterVisible: false,
        sharePosterQuote: '',
        sharePosterSourceLine1: '',
        sharePosterSourceLine2: '',
        sharePosterUserName: '历史读者',
        sharePosterUserAvatar: '',
        sharePosterExcerptDate: '',
        civSwitchEnabled: true,
    },
    onShow() {
        void this.refreshFavState();
    },
    onUnload() {
        this.pageUnloaded = true;
        this.swimSource = null;
        if (this.continuationUpdateTimer)
            clearTimeout(this.continuationUpdateTimer);
        if (this.chipTooltipExitTimer)
            clearTimeout(this.chipTooltipExitTimer);
        if (this.axisPinMeasureTimer)
            clearTimeout(this.axisPinMeasureTimer);
    },
    onShareAppMessage() {
        const u = this.data.unit;
        const t = this.data.dynastyTitle || (u === null || u === void 0 ? void 0 : u.name) || '朝代详情';
        const id = u === null || u === void 0 ? void 0 : u.id;
        const path = id ? `/pages/dynasty-detail/index?unitId=${encodeURIComponent(id)}` : '/pages/dynasty-detail/index';
        return { title: t, path };
    },
    async onLoad(query) {
        this._loadQuery = query;
        await (0, feature_flags_1.loadFeatureFlags)();
        await this.loadDynastyPage(query);
    },
    async retryLoad() {
        if (!this._loadQuery)
            return;
        this.setData({ loading: true, loadError: '', loadErrorDetail: '' });
        await this.loadDynastyPage(this._loadQuery);
    },
    copyLoadError() {
        const text = this.data.loadErrorDetail || this.data.loadError;
        if (!text)
            return;
        wx.setClipboardData({
            data: text,
            success: () => wx.showToast({ title: '已复制错误信息', icon: 'success' }),
        });
    },
    async loadDynastyPage(query) {
        var _a, _b;
        const rawUnitId = query.unitId || query.id || '';
        const dynastyHint = (0, query_value_1.decodeQueryValue)(query.dynasty || query.displayName || '');
        const unitCandidates = (0, matrix_adapter_1.resolveDetailUnitIds)(rawUnitId, dynastyHint);
        const civSwitchEnabled = (0, feature_flags_1.isCivSwitchEnabled)();
        this.setData({ civSwitchEnabled });
        if (!civSwitchEnabled) {
            const idsToCheck = unitCandidates.length
                ? unitCandidates
                : (rawUnitId ? [rawUnitId] : []);
            const blocked = idsToCheck.some((id) => id && !(0, feature_flags_1.isHuaxiaUnitId)(id));
            if (blocked) {
                (0, feature_flags_1.toastCivLocked)();
                this.setData({ loading: false, loadError: '该内容筹备中，敬请期待' });
                setTimeout(() => wx.navigateBack(), 1200);
                return;
            }
        }
        if (!unitCandidates.length && !dynastyHint) {
            this.setData({ loading: false, loadError: '缺少朝代参数，无法加载' });
            return;
        }
        const sys = wx.getSystemInfoSync();
        const navH = Math.round(88 * (sys.windowWidth / 750));
        const headerPadPx = (sys.statusBarHeight || 20) + navH;
        const tabBarH = Math.round(72 * (sys.windowWidth / 750));
        // 有并发 Tab 时吸顶线 = Tab 底；无 Tab 时 = 导航底（不再预留空白）
        const scrollTop = headerPadPx;
        this.continuationRatio = sys.windowWidth / 750;
        this.continuationViewportWidthPx = sys.windowWidth - 48 * this.continuationRatio;
        this.continuationWindowHeightPx = sys.windowHeight;
        const anchorYear = query.anchorYear ? parseInt(query.anchorYear, 10) : NaN;
        const provisionalNavTitle = dynastyHint
            ? (dynastyHint.length <= 4 ? dynastyHint : dynastyHint.slice(0, 4))
            : '';
        this.setData({
            headerPadPx,
            scrollTop,
            navTitle: provisionalNavTitle,
            dynastyTitle: dynastyHint,
            loading: true,
            loadError: '',
            loadErrorDetail: '',
        });
        const finishLoading = (patch) => {
            this.setData({ ...patch, loading: false });
        };
        const applyPageData = (hero, swim) => {
            var _a, _b;
            try {
                const unit = hero.unit;
                const dynastyTitle = (unit.dynastyName && unit.dynastyName.trim()) || unit.name;
                const navTitle = dynastyTitle.length <= 4 ? dynastyTitle : dynastyTitle.slice(0, 4);
                const heroSubLine = `${(0, year_format_1.formatHistoryYear)(unit.startYear)}–${(0, year_format_1.formatHistoryYear)(unit.endYear)}`;
                const heroCivLine = heroCivilizationLine(unit.crumbText);
                const activePriority = this.data.activePriority || 'p3';
                this.swimSource = swim;
                const prioritySwim = applyPriorityView(swim, activePriority);
                const swimForView = slimSwimMatrixForView(prioritySwim);
                const matrixBoxIds = collectMatrixBoxIds(swim);
                const hasVisibleContent = (prioritySwim.lanes || []).some(hasLaneContent);
                const { preview, canExpand, paragraphs } = previewIntro(unit.summary || '');
                const concurrentTabs = resolveConcurrentTabs(prioritySwim, unit.id, heroCivLine, dynastyTitle);
                const selfConcurrentLabel = `${heroCivLine || '华夏'}·${dynastyTitle}`;
                const activeConcurrentIndex = resolveActiveConcurrentIndex(concurrentTabs, unit.id, selfConcurrentLabel);
                const concurrentItems = concurrentTabs.map((tab) => tab.label);
                const contentTopPx = headerPadPx + (concurrentTabs.length > 0 ? tabBarH : 0);
                this.axisPinOffsetPx = -1;
                if (!hasVisibleContent) {
                    finishLoading({
                        unit,
                        dynastyTitle,
                        navTitle,
                        heroSubLine,
                        heroCivLine,
                        swim: null,
                        concurrentItems: [],
                        concurrentTabs: [],
                        activeConcurrentIndex: 0,
                        relatedUnits: hero.relatedUnits || [],
                        nextUnit: (_a = hero.nextUnit) !== null && _a !== void 0 ? _a : null,
                        matrixBoxIds: [],
                        headerPadPx,
                        scrollTop: headerPadPx,
                        introPreview: preview,
                        introDisplay: preview,
                        introCanExpand: canExpand,
                        introParagraphs: paragraphs,
                        loadError: (0, load_error_message_1.formatEmptySwimError)((0, runtime_env_1.isDevelopEnv)()),
                        loadErrorDetail: '',
                    });
                    return;
                }
                this.setData({
                    unit,
                    dynastyTitle,
                    navTitle,
                    heroSubLine,
                    heroCivLine,
                    swim: swimForView,
                    concurrentItems,
                    concurrentTabs,
                    activeConcurrentIndex,
                    relatedUnits: hero.relatedUnits || [],
                    nextUnit: (_b = hero.nextUnit) !== null && _b !== void 0 ? _b : null,
                    matrixBoxIds,
                    headerPadPx,
                    scrollTop: contentTopPx,
                    axisPinned: false,
                    axisMirrorLeft: 0,
                    introPreview: preview,
                    introDisplay: preview,
                    introCanExpand: canExpand,
                    introParagraphs: paragraphs,
                    loadError: '',
                    loadErrorDetail: '',
                    loading: false,
                }, () => {
                    this.rebuildContinuationHints(prioritySwim);
                    this.scheduleMeasureAxisPinOffset();
                });
                void this.refreshFavState();
                if (!Number.isNaN(anchorYear)) {
                    setTimeout(() => this.scrollToAnchorYear(anchorYear, swim), 120);
                }
            }
            catch (processErr) {
                throw processErr instanceof Error ? processErr : new Error(String(processErr));
            }
        };
        const tryApplyLocalMock = (mockHint, resolvedUnitId) => {
            if (!(0, runtime_env_1.isDevtoolsClient)())
                return false;
            const fallback = tryLoadLocalMock(mockHint, resolvedUnitId);
            if (!fallback)
                return false;
            console.warn('[dynasty-detail] using local mock for', mockHint);
            const enhancedSwim = {
                ...fallback.swim,
                ...generateTimelineTicks(fallback.swim.startYear, fallback.swim.endYear, fallback.swim.sheetWidthRpx),
                timeScaleMode: 'linear',
            };
            applyPageData(fallback.hero, enhancedSwim);
            warnIfDegradedMock(enhancedSwim);
            return true;
        };
        let resolvedMockHint = dynastyHint;
        let lastError = null;
        const triedIds = unitCandidates.length ? unitCandidates : [''];
        for (const candidateId of triedIds) {
            if (!candidateId)
                continue;
            try {
                const enc = (0, encode_path_segment_1.encodePathSegment)(candidateId);
                const heroRes = await (0, api_1.request)(`/units/${enc}`);
                resolvedMockHint =
                    dynastyHint ||
                        ((_a = heroRes.data.unit.dynastyName) === null || _a === void 0 ? void 0 : _a.trim()) ||
                        ((_b = heroRes.data.unit.name) === null || _b === void 0 ? void 0 : _b.trim()) ||
                        '';
                try {
                    const swimRes = await (0, api_1.request)(`/units/${enc}/swim-matrix`);
                    applyPageData(heroRes.data, {
                        ...swimRes.data,
                        gridLines: swimRes.data.gridLines || [],
                    });
                    return;
                }
                catch (swimErr) {
                    console.error('[dynasty-detail] swim-matrix failed', candidateId, swimErr);
                    lastError = swimErr;
                    if ((0, runtime_env_1.isDevtoolsClient)() && resolvedMockHint && tryApplyLocalMock(resolvedMockHint, candidateId)) {
                        return;
                    }
                }
            }
            catch (e) {
                console.error('[dynasty-detail] API failed', candidateId, e);
                lastError = e;
            }
        }
        if ((0, runtime_env_1.isDevtoolsClient)() && dynastyHint && tryApplyLocalMock(dynastyHint, rawUnitId || triedIds[0] || '')) {
            return;
        }
        const detail = (0, load_error_message_1.formatApiErrorDetail)(lastError, {
            unitId: rawUnitId,
            candidates: triedIds.join(', '),
            dynasty: dynastyHint,
        });
        finishLoading({
            unit: null,
            swim: null,
            loadError: (0, load_error_message_1.formatDynastyLoadError)(lastError, (0, runtime_env_1.isDevelopEnv)()),
            loadErrorDetail: detail,
        });
        wx.showToast({ title: '加载失败', icon: 'none' });
    },
    rebuildContinuationHints(swim) {
        this.continuationItems = buildContinuationItems(swim);
        this.continuationGeometryReady = false;
        wx.nextTick(() => {
            if (this.pageUnloaded)
                return;
            wx.createSelectorQuery()
                .in(this)
                .select('.dyn-panel-hscroll')
                .boundingClientRect()
                .select('.dyn-canvas')
                .boundingClientRect()
                .exec((rects) => {
                if (this.pageUnloaded)
                    return;
                const panelRect = rects === null || rects === void 0 ? void 0 : rects[0];
                const canvasRect = rects === null || rects === void 0 ? void 0 : rects[1];
                if (!panelRect || !canvasRect) {
                    this.setData({
                        continuationRightCount: 0,
                        continuationBottomCount: 0,
                        continuationCanvasActive: false,
                    });
                    return;
                }
                this.continuationViewportWidthPx =
                    Number(panelRect.width) || this.continuationViewportWidthPx;
                this.continuationCanvasTopPx =
                    this.continuationPageScrollTop + Number(canvasRect.top) - this.data.scrollTop;
                this.continuationCanvasHeightPx = Number(canvasRect.height) || 0;
                this.continuationGeometryReady = true;
                this.updateContinuationHints(true);
            });
        });
    },
    scheduleContinuationHintUpdate() {
        const elapsed = Date.now() - this.continuationLastUpdateAt;
        if (elapsed >= CONTINUATION_CUE_THROTTLE_MS) {
            this.updateContinuationHints(true);
            return;
        }
        if (this.continuationUpdateTimer)
            clearTimeout(this.continuationUpdateTimer);
        this.continuationUpdateTimer = setTimeout(() => {
            this.continuationUpdateTimer = null;
            if (this.pageUnloaded)
                return;
            this.updateContinuationHints(true);
        }, CONTINUATION_CUE_THROTTLE_MS - elapsed);
    },
    updateContinuationHints(force = false) {
        if (this.pageUnloaded)
            return;
        if (!this.continuationGeometryReady || !this.continuationItems.length) {
            if (this.data.continuationRightCount
                || this.data.continuationBottomCount
                || this.data.continuationCanvasActive) {
                this.setData({
                    continuationRightCount: 0,
                    continuationBottomCount: 0,
                    continuationCanvasActive: false,
                });
            }
            return;
        }
        const now = Date.now();
        if (!force && now - this.continuationLastUpdateAt < CONTINUATION_CUE_THROTTLE_MS) {
            this.scheduleContinuationHintUpdate();
            return;
        }
        this.continuationLastUpdateAt = now;
        const ratio = Math.max(0.01, this.continuationRatio);
        const visibleRightRpx = (this.swimScrollLeft + this.continuationViewportWidthPx) / ratio;
        const outerViewportHeightPx = Math.max(0, this.continuationWindowHeightPx
            - this.data.scrollTop
            - CONTINUATION_CUE_BOTTOM_RESERVE_RPX * ratio);
        const visibleBottomContentPx = this.continuationPageScrollTop + outerViewportHeightPx;
        const visibleBottomCanvasRpx = (visibleBottomContentPx - this.continuationCanvasTopPx) / ratio;
        const canvasBottomPx = this.continuationCanvasTopPx + this.continuationCanvasHeightPx;
        const canvasActive = this.continuationCanvasTopPx < visibleBottomContentPx
            && canvasBottomPx > this.continuationPageScrollTop;
        const rightCount = canvasActive
            ? (0, offscreen_hints_1.countOffscreenRight)(this.continuationItems, visibleRightRpx, CONTINUATION_CUE_TOLERANCE_RPX)
            : 0;
        const bottomCount = canvasActive
            ? (0, offscreen_hints_1.countOffscreenBottom)(this.continuationItems, visibleBottomCanvasRpx, CONTINUATION_CUE_TOLERANCE_RPX)
            : 0;
        if (rightCount !== this.data.continuationRightCount
            || bottomCount !== this.data.continuationBottomCount
            || canvasActive !== this.data.continuationCanvasActive) {
            this.setData({
                continuationRightCount: rightCount,
                continuationBottomCount: bottomCount,
                continuationCanvasActive: canvasActive,
            });
        }
    },
    scrollToAnchorYear(anchorYear, swim) {
        const rpxRatio = wx.getSystemInfoSync().windowWidth / 750;
        const padLeftPx = (swim.canvasPadLeftRpx || CANVAS_PAD_LEFT_RPX) * rpxRatio;
        const sheetPx = (swim.sheetWidthRpx || 1440) * rpxRatio;
        const targetPx = padLeftPx + (percentForYearOnSwim(swim, anchorYear) / 100) * sheetPx;
        const bias = wx.getSystemInfoSync().windowWidth * 0.32;
        const left = Math.max(0, Math.round(targetPx - bias));
        this.swimScrollLeft = left;
        this.setData({ panelScrollLeft: left, axisMirrorLeft: left });
        this.scheduleContinuationHintUpdate();
    },
    onPanelHScroll(e) {
        const left = roundScrollLeft(e.scrollLeft);
        this.swimScrollLeft = left;
        this.scheduleContinuationHintUpdate();
    },
    /**
     * 测量时间轴外框（.dyn-axis-pin-anchor）顶边相对 scroll-view 内容顶端的偏移。
     * 吸顶条件：pageScrollTop >= 该偏移（外框碰到 Tab/导航底）。
     */
    measureAxisPinOffset() {
        if (this.pageUnloaded || !this.data.swim)
            return;
        wx.createSelectorQuery()
            .in(this)
            .select('.dynasty-scroll')
            .boundingClientRect()
            .select('.dyn-axis-pin-anchor')
            .boundingClientRect()
            .select('.dynasty-scroll')
            .scrollOffset()
            .exec((rects) => {
            if (this.pageUnloaded)
                return;
            const scrollRect = rects === null || rects === void 0 ? void 0 : rects[0];
            const anchorRect = rects === null || rects === void 0 ? void 0 : rects[1];
            const scrollOffset = rects === null || rects === void 0 ? void 0 : rects[2];
            if (!scrollRect || !anchorRect || !scrollOffset)
                return;
            const offset = Math.max(0, Math.round(Number(scrollOffset.scrollTop || 0) +
                Number(anchorRect.top) -
                Number(scrollRect.top)));
            if (offset === this.axisPinOffsetPx) {
                this.applyAxisPinForScroll(this.continuationPageScrollTop);
                return;
            }
            this.axisPinOffsetPx = offset;
            this.applyAxisPinForScroll(this.continuationPageScrollTop);
        });
    },
    scheduleMeasureAxisPinOffset() {
        if (this.pageUnloaded)
            return;
        wx.nextTick(() => {
            if (this.pageUnloaded)
                return;
            this.measureAxisPinOffset();
        });
        if (this.axisPinMeasureTimer)
            clearTimeout(this.axisPinMeasureTimer);
        // 英雄区/字体二次布局后再测一次，避免阈值偏大导致外框钻进 Tab 后才钉住
        this.axisPinMeasureTimer = setTimeout(() => {
            this.axisPinMeasureTimer = null;
            this.measureAxisPinOffset();
        }, 120);
    },
    applyAxisPinForScroll(top) {
        const offset = this.axisPinOffsetPx;
        if (offset < 0)
            return;
        let pinned = this.data.axisPinned;
        if (!pinned && top >= offset)
            pinned = true;
        else if (pinned && top < offset - AXIS_PIN_HYSTERESIS_PX)
            pinned = false;
        if (pinned !== this.data.axisPinned) {
            this.setData({
                axisPinned: pinned,
                axisMirrorLeft: this.swimScrollLeft,
            });
        }
    },
    onDynastyScroll(e) {
        const top = e.detail.scrollTop;
        this.continuationPageScrollTop = top;
        this.scheduleContinuationHintUpdate();
        this.applyAxisPinForScroll(top);
        if (this.data.chipTooltipVisible) {
            this.hideChipTooltip();
        }
    },
    onBarTap(e) {
        if (this.data.chipTooltipVisible) {
            this.hideChipTooltip();
            return;
        }
        const ds = e.currentTarget.dataset || {};
        const boxId = ds.box;
        if (!boxId)
            return;
        if (ds.type === 'overflow_bucket') {
            this.showBucketOverlay(ds);
            return;
        }
        const title = (0, query_value_1.decodeQueryValue)(ds.title);
        void (0, api_1.request)(`/boxes/${(0, encode_path_segment_1.encodePathSegment)(boxId)}`).catch(() => { });
        (0, router_1.navigateTo)(router_1.ROUTES.boxDetail, { boxId, title });
    },
    showBucketOverlay(ds) {
        const laneIdx = Number(ds.lane);
        const bucketStart = Number(ds.startYear);
        const bucketEnd = Number(ds.endYear);
        const label = String(ds.label || '');
        const swim = this.data.swim;
        if (!swim || Number.isNaN(laneIdx))
            return;
        const lane = swim.lanes[laneIdx];
        if (!lane)
            return;
        let bars = lane.extraBars || [];
        if (Number.isFinite(bucketStart) && Number.isFinite(bucketEnd)) {
            bars = bars.filter((bar) => {
                const y = anchorYearOfBar(bar, lane.key);
                return y >= bucketStart && y < bucketEnd;
            });
        }
        this.openOverlaySheet(lane, bars, label);
    },
    openOverlaySheet(lane, bars, label = '') {
        this.setData({
            overlayVisible: true,
            overlayCountTag: buildOverlayCountTag(label || lane.label, bars.length),
            overlayBars: bars,
            overlayLaneKey: lane.key,
        });
    },
    onBarLongPress(e) {
        var _a;
        const ds = e.currentTarget.dataset || {};
        const boxId = ds.box;
        if (!boxId)
            return;
        const bar = findSwimBar(this.data.swim, boxId);
        const peakYearNum = bar === null || bar === void 0 ? void 0 : bar.peakYear;
        const peakReason = String((bar === null || bar === void 0 ? void 0 : bar.peakReason) || '').trim();
        const priorityReason = String((bar === null || bar === void 0 ? void 0 : bar.priorityReason) || '').trim();
        const chipTag = String((bar === null || bar === void 0 ? void 0 : bar.chipTag) || '').trim();
        const laneKey = String(ds.laneKey || '').trim();
        const { start: startYearLabel, end: endYearLabel } = splitTimeRangeLabels(bar, (bar === null || bar === void 0 ? void 0 : bar.timeRange) || ds.range || '');
        const sys = wx.getSystemInfoSync();
        const safeTop = computeChipTooltipSafeTop(this.data.axisPinned, this.data.scrollTop, sys.windowWidth);
        const safeBottom = computeChipTooltipSafeBottom(sys.windowHeight, sys.windowWidth, ((_a = sys.safeAreaInsets) === null || _a === void 0 ? void 0 : _a.bottom) || 0);
        const showTooltip = (rect) => {
            var _a, _b, _c;
            let placement;
            if (rect && rect.width > 0 && rect.height > 0) {
                placement = computeChipTooltipPlacement(rect, {
                    safeTop,
                    safeBottom,
                    windowWidth: sys.windowWidth,
                });
            }
            else {
                const touch = ((_a = e.touches) === null || _a === void 0 ? void 0 : _a[0]) || ((_b = e.changedTouches) === null || _b === void 0 ? void 0 : _b[0]);
                const anchorY = (_c = touch === null || touch === void 0 ? void 0 : touch.clientY) !== null && _c !== void 0 ? _c : Math.round(sys.windowHeight * 0.45);
                const left = (touch === null || touch === void 0 ? void 0 : touch.clientX) == null
                    ? Math.round(sys.windowWidth / 2)
                    : Math.max(140, Math.min(sys.windowWidth - 140, touch.clientX));
                const showAbove = anchorY - safeTop >= 120;
                placement = showAbove
                    ? { left, top: anchorY - 8, transform: 'translate(-50%, -100%)', origin: '50% 100%' }
                    : { left, top: anchorY + 8, transform: 'translate(-50%, 0)', origin: '50% 0%' };
            }
            if (this.chipTooltipExitTimer) {
                clearTimeout(this.chipTooltipExitTimer);
                this.chipTooltipExitTimer = null;
            }
            this.setData({
                chipTooltipHeldId: boxId,
                chipTooltipVisible: true,
                chipTooltipPhase: 'enter',
                chipTooltipTitle: (bar === null || bar === void 0 ? void 0 : bar.title) || ds.title || '',
                chipTooltipStartYear: startYearLabel,
                chipTooltipEndYear: endYearLabel,
                chipTooltipReignLabel: (laneKey === 'junji' || laneKey === 'zhuhou') ? '在位' : '',
                chipTooltipTag: chipTag,
                chipTooltipLaneKey: laneKey,
                chipTooltipPeakSummary: formatPeakSummary(peakYearNum == null ? '' : (0, year_format_1.formatHistoryYear)(peakYearNum), peakReason),
                chipTooltipPriority: formatPriorityLabel((bar === null || bar === void 0 ? void 0 : bar.priority) || ''),
                chipTooltipPrioritySummary: formatPeakSummary(formatPriorityLabel((bar === null || bar === void 0 ? void 0 : bar.priority) || ''), priorityReason),
                chipTooltipEntrySource: (0, entry_source_label_1.formatEntrySourceLabel)((bar === null || bar === void 0 ? void 0 : bar.entrySource) || ''),
                chipTooltipDetailSource: (0, entry_source_label_1.formatDetailSourceLabel)((bar === null || bar === void 0 ? void 0 : bar.detailSource) || ''),
                chipTooltipCoordinate: formatCoordinatePath(bar),
                chipTooltipLeftPx: placement.left,
                chipTooltipTopPx: placement.top,
                chipTooltipBaseTransform: placement.transform,
                chipTooltipOrigin: placement.origin,
                chipTooltipTransform: chipTooltipTransformWithScale(placement.transform, 0.88),
            });
            setTimeout(() => {
                if (!this.data.chipTooltipVisible || this.data.chipTooltipHeldId !== boxId)
                    return;
                this.setData({
                    chipTooltipPhase: 'idle',
                    chipTooltipTransform: chipTooltipTransformWithScale(placement.transform, 1),
                });
            }, 20);
        };
        wx.createSelectorQuery()
            .in(this)
            .select(`#chip-${boxId}`)
            .boundingClientRect((rect) => showTooltip(rect))
            .exec();
    },
    showMoreOverlay(e) {
        const label = e.currentTarget.dataset.label;
        const laneIdx = Number(e.currentTarget.dataset.lane);
        const swim = this.data.swim;
        if (!swim)
            return;
        const lane = swim.lanes[laneIdx];
        if (!lane)
            return;
        const bars = lane.extraBars || [];
        this.openOverlaySheet(lane, bars, label);
    },
    onPriorityTap(e) {
        const ds = e.currentTarget.dataset;
        const priority = String(ds.priority || '').trim();
        if (!priority || !PRIORITY_OPTIONS.some((item) => item.value === priority))
            return;
        if (priority === this.data.activePriority) {
            this.setData({ priorityMenuVisible: false });
            return;
        }
        const swim = this.swimSource;
        if (!swim)
            return;
        const nextSwim = applyPriorityView(swim, priority);
        this.setData({
            activePriority: priority,
            activePriorityLabel: priorityLabel(priority),
            priorityMenuVisible: false,
            swim: slimSwimMatrixForView(nextSwim),
            overlayVisible: false,
        }, () => {
            this.rebuildContinuationHints(nextSwim);
        });
        this.hideChipTooltip();
    },
    togglePriorityMenu() {
        const nextOpen = !this.data.priorityMenuVisible;
        if (!nextOpen) {
            this.setData({ priorityMenuVisible: false });
            return;
        }
        this.hideChipTooltip();
        wx.createSelectorQuery()
            .in(this)
            .select('.unit-hero-priority-wrap')
            .boundingClientRect()
            .exec((res) => {
            const rect = res === null || res === void 0 ? void 0 : res[0];
            const sys = wx.getSystemInfoSync();
            const top = rect ? Math.round(rect.bottom + 4) : this.data.scrollTop + 100;
            const right = rect ? Math.max(8, Math.round(sys.windowWidth - rect.right)) : 24;
            this.setData({
                priorityMenuVisible: true,
                priorityMenuTopPx: top,
                priorityMenuRightPx: right,
            });
        });
    },
    closePriorityMenu() {
        if (this.data.priorityMenuVisible) {
            this.setData({ priorityMenuVisible: false });
        }
    },
    hideOverlay() {
        this.setData({ overlayVisible: false });
    },
    hideChipTooltip() {
        if (!this.data.chipTooltipVisible)
            return;
        if (this.data.chipTooltipPhase === 'exit')
            return;
        const baseTransform = this.data.chipTooltipBaseTransform || 'translate(-50%, -100%)';
        this.setData({
            chipTooltipPhase: 'exit',
            chipTooltipTransform: chipTooltipTransformWithScale(baseTransform, 0.88),
        });
        if (this.chipTooltipExitTimer)
            clearTimeout(this.chipTooltipExitTimer);
        this.chipTooltipExitTimer = setTimeout(() => {
            this.chipTooltipExitTimer = null;
            if (this.data.chipTooltipPhase !== 'exit')
                return;
            this.setData({
                chipTooltipVisible: false,
                chipTooltipHeldId: '',
                chipTooltipPhase: 'enter',
            });
        }, 190);
    },
    onChipTooltipTransitionEnd() {
        if (this.data.chipTooltipPhase !== 'exit')
            return;
        if (this.chipTooltipExitTimer) {
            clearTimeout(this.chipTooltipExitTimer);
            this.chipTooltipExitTimer = null;
        }
        this.setData({
            chipTooltipVisible: false,
            chipTooltipHeldId: '',
            chipTooltipPhase: 'enter',
        });
    },
    goUnit(e) {
        const ds = e.currentTarget.dataset;
        (0, router_1.navigateTo)(router_1.ROUTES.dynastyDetail, {
            unitId: ds.id,
            dynasty: ds.dynasty || '',
        });
    },
    onConcurrentTabTap(e) {
        var _a;
        const index = Number((_a = e.currentTarget.dataset) === null || _a === void 0 ? void 0 : _a.index);
        if (!Number.isFinite(index) || index < 0)
            return;
        if (index === this.data.activeConcurrentIndex)
            return;
        const tab = this.data.concurrentTabs[index];
        if (!tab)
            return;
        const isHuaxia = isHuaxiaCivName(tab.civilizationName) || (0, feature_flags_1.isHuaxiaUnitId)(tab.dynastyId);
        if (!(0, feature_flags_1.isCivSwitchEnabled)() && !isHuaxia) {
            (0, feature_flags_1.toastCivLocked)();
            return;
        }
        const { title } = parseConcurrentLabel(tab.label);
        const targetId = tab.dynastyId || (0, matrix_adapter_1.resolveDetailUnitIds)('', title)[0] || '';
        if (!targetId) {
            wx.showToast({ title: '暂未收录该朝代', icon: 'none' });
            return;
        }
        if (!(0, feature_flags_1.isCivSwitchEnabled)() && !(0, feature_flags_1.isHuaxiaUnitId)(targetId)) {
            (0, feature_flags_1.toastCivLocked)();
            return;
        }
        (0, router_1.navigateTo)(router_1.ROUTES.dynastyDetail, {
            unitId: targetId,
            dynasty: title,
        });
    },
    goNext() {
        const n = this.data.nextUnit;
        if (!(n === null || n === void 0 ? void 0 : n.unitId))
            return;
        (0, router_1.navigateTo)(router_1.ROUTES.dynastyDetail, { unitId: n.unitId, dynasty: n.title });
    },
    openIntro() {
        if (!this.data.introCanExpand)
            return;
        this.setData({ showIntroModal: true });
    },
    closeIntro() {
        this.setData({ showIntroModal: false });
    },
    noop() { },
    async refreshFavState() {
        var _a;
        const unitId = String(((_a = this.data.unit) === null || _a === void 0 ? void 0 : _a.id) || '').trim();
        if (!unitId || !(0, api_1.hasToken)()) {
            this.setData({ isFav: false, favPartial: false });
            return;
        }
        const favorited = await (0, favorite_unit_1.fetchFavoritedUnitIdSet)();
        this.setData({ isFav: favorited.has(unitId), favPartial: false });
    },
    async onFavoriteTap() {
        var _a;
        if (this.data.favToggling || !(0, api_1.hasToken)()) {
            if (!(0, api_1.hasToken)())
                (0, favorite_unit_1.promptLoginForUnitFavorite)();
            return;
        }
        const unitId = String(((_a = this.data.unit) === null || _a === void 0 ? void 0 : _a.id) || '').trim();
        if (!unitId) {
            wx.showToast({ title: '当前朝代无法收藏', icon: 'none' });
            return;
        }
        const nextFav = !this.data.isFav;
        this.setData({ favToggling: true });
        try {
            if (nextFav) {
                await (0, favorite_unit_1.favoriteUnit)(unitId);
            }
            else {
                await (0, favorite_unit_1.unfavoriteUnit)(unitId);
            }
            await this.refreshFavState();
            wx.showToast({ title: nextFav ? '已收藏本朝' : '已取消收藏', icon: 'success' });
        }
        catch (e) {
            wx.showToast({
                title: (0, load_error_message_1.formatApiRequestError)(e) || (0, load_error_message_1.formatUserFacingError)(e, (0, runtime_env_1.isDevelopEnv)(), '收藏失败，请稍后重试'),
                icon: 'none',
            });
        }
        finally {
            this.setData({ favToggling: false });
        }
    },
    hideSelectionBar() {
        this.setData({
            selectionBarVisible: false,
            selectionBarText: '',
        });
        this.clearDetailSelection();
    },
    clearDetailSelection() {
        for (const selector of ['#dynastyIntroSelection', '#dynastyModalSelection']) {
            wx.createSelectorQuery()
                .in(this)
                .select(selector)
                .context((res) => {
                var _a;
                const ctx = res === null || res === void 0 ? void 0 : res.context;
                (_a = ctx === null || ctx === void 0 ? void 0 : ctx.removeSelection) === null || _a === void 0 ? void 0 : _a.call(ctx);
            })
                .exec();
        }
    },
    onDetailSelectionChange(e) {
        const detail = (e.detail || {});
        const selected = String(detail.selectedString || '').trim();
        if (detail.isCollapsed || !selected) {
            this.hideSelectionBar();
            return;
        }
        const anchor = (0, selection_bar_position_1.resolveSelectionBarAnchor)(detail.firstRangeRect, {
            left: this.data.selectionBarLeft,
            top: this.data.selectionBarTop,
            placement: this.data.selectionBarPlacement,
        });
        this.setData({
            selectionBarVisible: true,
            selectionBarText: selected,
            selectionBarLeft: anchor.left,
            selectionBarTop: anchor.top,
            selectionBarPlacement: anchor.placement,
        });
    },
    async onSelectionShare() {
        const text = this.data.selectionBarText;
        this.hideSelectionBar();
        if (!text)
            return;
        wx.showLoading({ title: '生成海报…', mask: true });
        try {
            const dynastyTitle = this.data.dynastyTitle || '朝代';
            const unit = this.data.unit;
            const civ = unit ? (0, correction_1.parseCivilizationFromCrumb)(unit.crumbText) : '';
            const sourceLine1 = `/${[civ, dynastyTitle, '朝代简介'].filter(Boolean).join('・')}`;
            const posterState = await (0, share_poster_open_1.buildSharePosterSheetState)(text, sourceLine1, '');
            this.setData(posterState);
        }
        catch {
            wx.hideLoading();
            wx.showToast({ title: '海报生成失败', icon: 'none' });
        }
    },
    closeSharePoster() {
        wx.hideLoading();
        this.setData({ sharePosterVisible: false });
    },
    onSelectionCopy() {
        const text = this.data.selectionBarText;
        this.hideSelectionBar();
        if (!text)
            return;
        wx.setClipboardData({
            data: text,
            success: () => wx.showToast({ title: '已复制', icon: 'success' }),
        });
    },
    onSelectionQuery() {
        const text = this.data.selectionBarText;
        this.hideSelectionBar();
        if (!text)
            return;
        this.clearDetailSelection();
        this.setData({
            dictionaryVisible: true,
            dictionaryQuery: text,
        });
    },
    closeDictionary() {
        this.setData({ dictionaryVisible: false, dictionaryQuery: '' });
        this.clearDetailSelection();
    },
    onSelectionCorrection() {
        const text = this.data.selectionBarText;
        this.hideSelectionBar();
        if (!text)
            return;
        (0, correction_1.requireLoginForCorrection)(() => {
            const unit = this.data.unit;
            const civilizationName = unit ? (0, correction_1.parseCivilizationFromCrumb)(unit.crumbText) : '';
            this.setData({
                correctionVisible: true,
                correctionSubmitting: false,
                correctionBoxId: this.data.matrixBoxIds[0] || '',
                correctionBoxTitle: `${this.data.dynastyTitle} · 朝代简介`,
                correctionCivilizationName: civilizationName,
                correctionDynastyName: this.data.dynastyTitle,
            });
        });
    },
    onChipTooltipCardTap() { },
    onChipCorrectionTap() {
        const boxId = this.data.chipTooltipHeldId;
        if (!boxId)
            return;
        (0, correction_1.requireLoginForCorrection)(() => {
            const unit = this.data.unit;
            const civilizationName = unit ? (0, correction_1.parseCivilizationFromCrumb)(unit.crumbText) : '';
            this.setData({
                chipTooltipVisible: false,
                chipTooltipHeldId: '',
                correctionVisible: true,
                correctionSubmitting: false,
                correctionBoxId: boxId,
                correctionBoxTitle: this.data.chipTooltipTitle,
                correctionCivilizationName: civilizationName,
                correctionDynastyName: this.data.dynastyTitle,
            });
        });
    },
    closeCorrection() {
        this.setData({ correctionVisible: false, correctionSubmitting: false });
    },
    async onCorrectionSubmit(e) {
        var _a;
        const reason = String(((_a = e.detail) === null || _a === void 0 ? void 0 : _a.reason) || '');
        const boxId = this.data.correctionBoxId;
        if (!boxId || this.data.correctionSubmitting)
            return;
        this.setData({ correctionSubmitting: true });
        try {
            await (0, correction_1.submitCorrection)({
                boxId,
                sourceType: 'dynasty_canvas',
                reason,
            });
            wx.showToast({ title: '提交成功，感谢反馈', icon: 'success' });
            this.setData({ correctionVisible: false, correctionSubmitting: false });
        }
        catch (err) {
            this.setData({ correctionSubmitting: false });
            wx.showToast({
                title: (0, load_error_message_1.formatUserFacingError)(err, (0, runtime_env_1.isDevelopEnv)(), '提交失败，请稍后重试'),
                icon: 'none',
            });
        }
    },
});
