"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const dev_config_1 = require("../../native-utils/dev-config");
const api_1 = require("../../native-utils/api");
const encode_path_segment_1 = require("../../native-utils/encode-path-segment");
const favorite_box_1 = require("../../native-utils/favorite-box");
const router_1 = require("../../native-utils/router");
const query_value_1 = require("../../native-utils/query-value");
const year_format_1 = require("../../native-utils/year-format");
const entry_source_label_1 = require("../../native-utils/entry-source-label");
const share_invite_1 = require("../../native-utils/share-invite");
const { buildSwimMatrixFromMock, buildHeroFromMock, normalizeDynastyKey, isDegradedMockFallback, } = require('./swim-local-fallback');
const PRIORITY_OPTIONS = [
    { value: 'p0', label: 'P0' },
    { value: 'p1', label: 'P1' },
    { value: 'p2', label: 'P2' },
    { value: 'p3', label: 'P3' },
];
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
const AXIS_PIN_AT = 150;
const AXIS_UNPIN_AT = 110;
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
function parseBucketMemberCount(title) {
    const match = String(title || '').match(/\+(\d+)$/);
    return match ? Number(match[1]) : 0;
}
function bucketTitle(laneLabel, count) {
    return BUCKET_CHIP_TITLE;
}
function anchorYearOfBar(bar) {
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
    let cursor = startYear;
    let bucketIndex = 0;
    while (cursor < endYear) {
        const bucketEnd = Math.min(endYear, cursor + bucketYears);
        const members = overflow.filter((bar) => {
            const y = anchorYearOfBar(bar);
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
            for (let rowIndex = 0; rowIndex < nextRows.length; rowIndex++) {
                if (rowEnds[rowIndex] + gapPct <= bucketBar._leftPct) {
                    assigned = rowIndex;
                    rowEnds[rowIndex] = bucketBar._rightPct;
                    nextRows[rowIndex] = [...nextRows[rowIndex], bucketBar].sort((a, b) => a._leftPct - b._leftPct);
                    break;
                }
            }
            if (assigned === -1) {
                nextRows.push([bucketBar]);
                rowEnds.push(bucketBar._rightPct);
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
function isDevelopEnv() {
    var _a, _b;
    try {
        return ((_b = (_a = wx.getAccountInfoSync()) === null || _a === void 0 ? void 0 : _a.miniProgram) === null || _b === void 0 ? void 0 : _b.envVersion) === 'develop';
    }
    catch {
        return true;
    }
}
function warnIfDegradedMock(swim) {
    if (!isDegradedMockFallback(swim))
        return;
    wx.showToast({
        title: `后端未连通(${dev_config_1.DEV_LAN_HOST}:${dev_config_1.DEV_API_PORT})，仅显示君王`,
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
    // 泳道网格线：从第2个刻度开始，与时间轴刻度对齐
    const gridLines = ticks.filter(t => t.left !== '0%').map(t => ({ left: t.left }));
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
function splitTimeRangeLabels(bar, fallbackRange) {
    if ((bar === null || bar === void 0 ? void 0 : bar.startYear) != null && (bar === null || bar === void 0 ? void 0 : bar.endYear) != null) {
        return {
            start: (0, year_format_1.formatHistoryYear)(bar.startYear),
            end: (0, year_format_1.formatHistoryYear)(bar.endYear),
        };
    }
    const parts = String(fallbackRange || '').split(/\s*[—–-]\s*/);
    if (parts.length >= 2) {
        return { start: parts[0].trim(), end: parts[parts.length - 1].trim() };
    }
    const single = String(fallbackRange || '').trim();
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
    var _a;
    return ((_a = lane.totalCount) !== null && _a !== void 0 ? _a : 0) > 0;
}
function composeCanvasLayout(swim, lanes) {
    var _a, _b, _c, _d, _e;
    const categoryBands = [];
    const canvasLanes = [];
    let cursor = BAND_PAD_RPX;
    const sheetWidthRpx = swim.sheetWidthRpx || 1440;
    const visibleLanes = lanes.filter(hasLaneContent);
    for (const lane of visibleLanes) {
        const rowCount = Math.max(1, lane.rowCount || ((_a = lane.collapsedRows) === null || _a === void 0 ? void 0 : _a.length) || 1);
        const trackHeight = snapRpx(LANE_TRACK_PAD_VERTICAL_RPX + rowCount * CHIP_HEIGHT_RPX + (rowCount - 1) * ROW_GAP_RPX);
        const bandHeight = Math.max(MIN_BAND_HEIGHT_RPX, trackHeight);
        const canvasRows = [];
        (lane.collapsedRows || []).forEach((row, rowIndex) => {
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
        categoryBands.push({
            key: lane.key,
            label: lane.label,
            borderColor: lane.borderColor,
            topRpx: cursor,
            heightRpx: bandHeight,
            readProgressText: lane.readProgressText || `${(_b = lane.readCount) !== null && _b !== void 0 ? _b : 0}/${(_c = lane.totalCount) !== null && _c !== void 0 ? _c : 0}`,
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
    return {
        ...swim,
        lanes: canvasLanes,
        categoryBands,
        canvasHeightRpx: snapRpx(Math.max(MIN_BAND_HEIGHT_RPX + BAND_PAD_RPX * 2, cursor + BAND_PAD_RPX)),
        canvasPadLeftRpx: (_d = swim.canvasPadLeftRpx) !== null && _d !== void 0 ? _d : CANVAS_PAD_LEFT_RPX,
        canvasWidthRpx: (swim.sheetWidthRpx || 1440) + ((_e = swim.canvasPadLeftRpx) !== null && _e !== void 0 ? _e : CANVAS_PAD_LEFT_RPX),
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
function normalizeLegacyLane(lane, sheetWidthRpx, priority, swim) {
    const allBars = [...(lane.collapsedRows || []).flat(), ...(lane.extraBars || [])]
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
    const axisHeightPx = axisPinned ? rpxToPx(86, windowWidth) + 8 : 0;
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
function previewIntro(intro) {
    const paragraphs = splitIntroParagraphs(intro);
    if (paragraphs.length <= 1) {
        return { preview: paragraphs[0] || '空', canExpand: false, paragraphs };
    }
    return { preview: paragraphs[0], canExpand: true, paragraphs };
}
Page({
    swimScrollLeft: 0,
    chipTooltipExitTimer: null,
    data: {
        unit: null,
        dynastyTitle: '',
        navTitle: '',
        heroSubLine: '',
        swim: null,
        concurrentItems: [],
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
        loadError: '',
        priorityOptions: PRIORITY_OPTIONS,
        activePriority: 'p3',
        chipTooltipVisible: false,
        chipTooltipPhase: 'enter',
        chipTooltipHeldId: '',
        chipTooltipTitle: '',
        chipTooltipRange: '',
        chipTooltipTag: '',
        chipTooltipPeakYear: '',
        chipTooltipPeakReason: '',
        chipTooltipPriority: '',
        chipTooltipPriorityReason: '',
        chipTooltipEntrySource: '',
        chipTooltipLaneKey: '',
        chipTooltipStartYear: '',
        chipTooltipEndYear: '',
        chipTooltipLeftPx: 0,
        chipTooltipTopPx: 0,
        chipTooltipBaseTransform: 'translate(-50%, -100%)',
        chipTooltipOrigin: '50% 100%',
        chipTooltipTransform: 'translate(-50%, -100%) scale(0.88)',
    },
    onShow() {
        void this.refreshFavState();
    },
    onShareAppMessage() {
        const u = this.data.unit;
        const t = this.data.dynastyTitle || (u === null || u === void 0 ? void 0 : u.name) || '朝代详情';
        const id = u === null || u === void 0 ? void 0 : u.id;
        const path = id ? `/pages/dynasty-detail/index?unitId=${encodeURIComponent(id)}` : '/pages/dynasty-detail/index';
        return { title: t, path };
    },
    async onLoad(query) {
        const unitId = query.unitId || query.id;
        const dynastyHint = (0, query_value_1.decodeQueryValue)(query.dynasty || query.displayName || '');
        if (!unitId && !dynastyHint)
            return;
        const sys = wx.getSystemInfoSync();
        const navH = Math.round(88 * (sys.windowWidth / 750));
        const headerPadPx = (sys.statusBarHeight || 20) + navH;
        const tabBarH = Math.round(72 * (sys.windowWidth / 750));
        const scrollTop = headerPadPx + tabBarH;
        const anchorYear = query.anchorYear ? parseInt(query.anchorYear, 10) : NaN;
        const provisionalNavTitle = dynastyHint
            ? (dynastyHint.length <= 4 ? dynastyHint : dynastyHint.slice(0, 4))
            : '';
        this.setData({
            headerPadPx,
            scrollTop,
            navTitle: provisionalNavTitle,
            dynastyTitle: dynastyHint,
        });
        const applyPageData = (hero, swim) => {
            var _a;
            const unit = hero.unit;
            const dynastyTitle = (unit.dynastyName && unit.dynastyName.trim()) || unit.name;
            const navTitle = dynastyTitle.length <= 4 ? dynastyTitle : dynastyTitle.slice(0, 4);
            const heroSubLine = `${(0, year_format_1.formatHistoryYear)(unit.startYear)}–${(0, year_format_1.formatHistoryYear)(unit.endYear)}`;
            const activePriority = this.data.activePriority || 'p3';
            const prioritySwim = applyPriorityView(swim, activePriority);
            const matrixBoxIds = collectMatrixBoxIds(prioritySwim);
            const { preview, canExpand, paragraphs } = previewIntro(unit.summary || '');
            this.setData({
                unit,
                dynastyTitle,
                navTitle,
                heroSubLine,
                swim: prioritySwim,
                concurrentItems: prioritySwim.concurrentItems || [],
                relatedUnits: hero.relatedUnits || [],
                nextUnit: (_a = hero.nextUnit) !== null && _a !== void 0 ? _a : null,
                matrixBoxIds,
                headerPadPx,
                scrollTop,
                introPreview: preview,
                introDisplay: preview,
                introCanExpand: canExpand,
                introParagraphs: paragraphs,
                loadError: '',
            });
            void this.refreshFavState();
            if (!Number.isNaN(anchorYear)) {
                setTimeout(() => this.scrollToAnchorYear(anchorYear, swim), 120);
            }
        };
        if (unitId) {
            try {
                const enc = (0, encode_path_segment_1.encodePathSegment)(unitId);
                const [heroRes, swimRes] = await Promise.all([
                    (0, api_1.request)(`/units/${enc}`),
                    (0, api_1.request)(`/units/${enc}/swim-matrix`),
                ]);
                applyPageData(heroRes.data, {
                    ...swimRes.data,
                    gridLines: swimRes.data.gridLines || [],
                });
                return;
            }
            catch (e) {
                console.error('[dynasty-detail] API failed', e);
                if (isDevelopEnv() && dynastyHint) {
                    const fallback = tryLoadLocalMock(dynastyHint, unitId);
                    if (fallback) {
                        console.warn('[dynasty-detail] using local mock for', dynastyHint);
                        const enhancedSwim = {
                            ...fallback.swim,
                            ...generateTimelineTicks(fallback.swim.startYear, fallback.swim.endYear, fallback.swim.sheetWidthRpx),
                            timeScaleMode: 'linear',
                        };
                        applyPageData(fallback.hero, enhancedSwim);
                        warnIfDegradedMock(enhancedSwim);
                        return;
                    }
                }
                const msg = (e === null || e === void 0 ? void 0 : e.message) || '加载失败';
                this.setData({
                    unit: null,
                    swim: null,
                    loadError: `无法加载朝代数据（${msg}）。请确认后端已启动且已导入 historical_dynasty / historical_box 数据。`,
                });
                wx.showToast({ title: '加载失败', icon: 'none' });
                return;
            }
        }
        if (isDevelopEnv() && dynastyHint) {
            const fallback = tryLoadLocalMock(dynastyHint, '');
            if (fallback) {
                console.warn('[dynasty-detail] using local mock for', dynastyHint);
                const enhancedSwim = {
                    ...fallback.swim,
                    ...generateTimelineTicks(fallback.swim.startYear, fallback.swim.endYear, fallback.swim.sheetWidthRpx),
                    timeScaleMode: 'linear',
                };
                applyPageData(fallback.hero, enhancedSwim);
                warnIfDegradedMock(enhancedSwim);
                return;
            }
        }
        this.setData({ loadError: '缺少朝代 ID，无法加载' });
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
    },
    onPanelHScroll(e) {
        const left = roundScrollLeft(e.scrollLeft);
        this.swimScrollLeft = left;
    },
    onDynastyScroll(e) {
        const top = e.detail.scrollTop;
        let pinned = this.data.axisPinned;
        if (!pinned && top > AXIS_PIN_AT)
            pinned = true;
        else if (pinned && top < AXIS_UNPIN_AT)
            pinned = false;
        if (pinned !== this.data.axisPinned) {
            this.setData({
                axisPinned: pinned,
                axisMirrorLeft: this.swimScrollLeft,
            });
        }
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
                var _a, _b;
                const y = (_b = (_a = bar.peakYear) !== null && _a !== void 0 ? _a : bar.startYear) !== null && _b !== void 0 ? _b : 0;
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
                chipTooltipTag: chipTag,
                chipTooltipLaneKey: laneKey,
                chipTooltipPeakYear: peakYearNum == null ? '' : (0, year_format_1.formatHistoryYear)(peakYearNum),
                chipTooltipPeakReason: peakReason,
                chipTooltipPriority: formatPriorityLabel((bar === null || bar === void 0 ? void 0 : bar.priority) || ''),
                chipTooltipPriorityReason: priorityReason,
                chipTooltipEntrySource: (0, entry_source_label_1.formatEntrySourceLabel)((bar === null || bar === void 0 ? void 0 : bar.entrySource) || ''),
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
        const priority = e.currentTarget.dataset.priority;
        if (!priority || priority === this.data.activePriority)
            return;
        const swim = this.data.swim;
        if (!swim)
            return;
        this.setData({
            activePriority: priority,
            swim: applyPriorityView(swim, priority),
            overlayVisible: false,
        });
        this.hideChipTooltip();
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
        const id = e.currentTarget.dataset.id;
        (0, router_1.navigateTo)(router_1.ROUTES.dynastyDetail, { unitId: id });
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
        this.setData({ showIntroModal: true, introModalTitle: (this.data.dynastyTitle || '') + '·朝代简介' });
    },
    closeIntro() {
        this.setData({ showIntroModal: false });
    },
    noop() { },
    async refreshFavState() {
        const boxIds = this.data.matrixBoxIds;
        if (!boxIds.length || !(0, api_1.hasToken)()) {
            this.setData({ isFav: false, favPartial: false });
            return;
        }
        const favorited = await (0, favorite_box_1.fetchFavoritedBoxIdSet)();
        const st = (0, favorite_box_1.computeUnitFavoriteState)(boxIds, favorited);
        this.setData({ isFav: st.allFavorited, favPartial: st.anyFavorited && !st.allFavorited });
    },
    async onFavoriteTap() {
        if (this.data.favToggling || !(0, api_1.hasToken)()) {
            if (!(0, api_1.hasToken)())
                (0, favorite_box_1.promptLoginForFavorite)();
            return;
        }
        const boxIds = this.data.matrixBoxIds;
        if (!boxIds.length) {
            wx.showToast({ title: '当前朝代暂无史略可收藏', icon: 'none' });
            return;
        }
        const favorited = await (0, favorite_box_1.fetchFavoritedBoxIdSet)();
        const st = (0, favorite_box_1.computeUnitFavoriteState)(boxIds, favorited);
        const nextFav = !st.allFavorited;
        this.setData({ favToggling: true });
        try {
            await (0, favorite_box_1.setBoxesFavorited)(boxIds, nextFav);
            await this.refreshFavState();
            wx.showToast({ title: nextFav ? '已收藏本朝史略' : '已取消收藏', icon: 'success' });
        }
        catch (e) {
            wx.showToast({ title: e instanceof Error ? e.message : '操作失败', icon: 'none' });
        }
        finally {
            this.setData({ favToggling: false });
        }
    },
    onShareTap() {
        (0, share_invite_1.promptContentShareUnavailable)();
    },
});
