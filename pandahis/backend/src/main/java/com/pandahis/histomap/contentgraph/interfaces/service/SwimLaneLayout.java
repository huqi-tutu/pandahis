package com.pandahis.histomap.contentgraph.interfaces.service;

import com.pandahis.histomap.common.util.HistoryYearFormat;
import com.pandahis.histomap.contentgraph.interfaces.dto.UnitSwimMatrixDTO;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** 朝代详情画布布局：内容自适应胶囊宽，峰值年对齐胶囊中心，8rpx 网格吸附。 */
final class SwimLaneLayout {
  static final int MAX_ROWS = 10;
  static final int GRID_RPX = SwimCanvasLayout.GRID_RPX;
  /** 估算 sheet 宽度时的最大胶囊宽 */
  static final int CHIP_MAX_RPX = 288;
  static final int CHIP_MIN_RPX = 80;
  static final int CHIP_HEIGHT_RPX = 52;
  /** 胶囊左右 padding 合计（与 SCSS 14+14 对齐） */
  static final int CHIP_PAD_H_RPX = 28;
  static final int CHIP_TITLE_RPX_PER_CHAR = 24;
  /** Badge 左右 padding 合计（与 SCSS 8+8 对齐） */
  static final int CHIP_TAG_PAD_H_RPX = 16;
  static final int CHIP_TAG_RPX_PER_CHAR = 20;
  static final int CHIP_INNER_GAP_RPX = 4;
  static final int CHIP_GAP_RPX = 16;
  static final int ROW_GAP_RPX = 16;
  static final int EDGE_GAP_RPX = 24;
  static final int MORE_RPX = 112;
  static final int MORE_GAP_RPX = 20;
  static final int TRACK_PAD_VERTICAL_RPX = 24;
  static final int SHEET_RPX = 1440;
  static final int MIN_BUCKET_YEARS = 10;
  static final int MAX_BUCKET_YEARS = 30;

  private static final Pattern GLOBAL_ID = Pattern.compile("^GLBL_(\\d+)$");
  private static final List<String> PRIORITY_LEVELS = List.of("p0", "p1", "p2", "p3");

  record SwimBarInput(
      String boxId,
      String title,
      int start,
      int end,
      String priority,
      Integer peakYear,
      String peakReason,
      boolean anchorAtStart,
      String personTag,
      String priorityReason,
      String entrySource
  ) {}

  private SwimLaneLayout() {}

  static Map<String, UnitSwimMatrixDTO.LaneView> buildPriorityViews(
      List<SwimBarInput> bars,
      int startYear,
      int span,
      int sheetRpx
  ) {
    return buildPriorityViews(bars, SwimTimeScale.linear(startYear, startYear + span), sheetRpx);
  }

  static Map<String, UnitSwimMatrixDTO.LaneView> buildPriorityViews(
      List<SwimBarInput> bars,
      SwimTimeScale scale,
      int sheetRpx
  ) {
    return buildPriorityViews(bars, scale, sheetRpx, "lane", "");
  }

  static Map<String, UnitSwimMatrixDTO.LaneView> buildPriorityViews(
      List<SwimBarInput> bars,
      SwimTimeScale scale,
      int sheetRpx,
      String laneKey,
      String laneLabel
  ) {
    Map<String, UnitSwimMatrixDTO.LaneView> views = new LinkedHashMap<>();
    for (String threshold : PRIORITY_LEVELS) {
      views.put(threshold, buildPriorityView(bars, threshold, scale, sheetRpx, laneKey, laneLabel));
    }
    return views;
  }

  private static UnitSwimMatrixDTO.LaneView buildPriorityView(
      List<SwimBarInput> bars,
      String threshold,
      SwimTimeScale scale,
      int sheetRpx,
      String laneKey,
      String laneLabel
  ) {
    List<PreparedBar> prepared = bars.stream()
        .map(SwimLaneLayout::prepare)
        .sorted(PreparedBar.ORDER)
        .toList();

    int maxPriority = priorityRank(threshold);
    List<PreparedBar> candidates = prepared.stream()
        .filter(bar -> bar.priorityRank <= maxPriority)
        .toList();
    List<PreparedBar> hiddenByPriority = prepared.stream()
        .filter(bar -> bar.priorityRank > maxPriority)
        .toList();

    Placement placement = place(candidates, scale, sheetRpx);
    List<List<UnitSwimMatrixDTO.Bar>> rows = new ArrayList<>();
    for (List<UnitSwimMatrixDTO.Bar> row : placement.rows) {
      rows.add(new ArrayList<>(row));
    }
    List<Double> rowEnds = new ArrayList<>(placement.rowEnds);

    List<PreparedBar> extra = new ArrayList<>(hiddenByPriority);
    extra.addAll(placement.overflow);
    extra.sort(PreparedBar.ORDER);

    List<OverflowBucket> buckets = bucketOverflow(
        extra,
        scale.startYear(),
        scale.endYear(),
        laneKey,
        laneLabel
    );
    double gapPct = CHIP_GAP_RPX / (double) sheetRpx * 100.0;
    int bucketRowIndex = -1;
    for (OverflowBucket bucket : buckets) {
      bucketRowIndex = placeBucketChip(rows, rowEnds, bucket, scale, sheetRpx, gapPct, bucketRowIndex);
    }

    int rowCount = Math.max(1, rows.size());
    int height = trackHeight(rowCount);
    int visibleCount = placement.visibleCount + buckets.size();

    return new UnitSwimMatrixDTO.LaneView(
        rows,
        false,
        extra.size(),
        fmtPct(moreLeftPct(sheetRpx)),
        "12%",
        extra.stream().map(bar -> toOverlayBar(bar, scale, sheetRpx)).toList(),
        rowCount,
        height,
        visibleCount
    );
  }

  private static Placement place(
      List<PreparedBar> candidates,
      SwimTimeScale scale,
      int sheetRpx
  ) {
    List<List<UnitSwimMatrixDTO.Bar>> rows = new ArrayList<>();
    List<Double> rowEnds = new ArrayList<>();
    List<PreparedBar> overflow = new ArrayList<>();

    double gapPct = CHIP_GAP_RPX / (double) sheetRpx * 100.0;

    for (PreparedBar bar : candidates) {
      int chipRpx = bar.chipWidthRpx;
      double chipPct = chipRpx / (double) sheetRpx * 100.0;
      double left = leftPctFromAnchor(scale.percentForYear(bar.anchorYear), sheetRpx, chipRpx);
      double right = left + chipPct;

      int assigned = -1;
      for (int row = 0; row < rowEnds.size(); row++) {
        if (rowEnds.get(row) + gapPct <= left) {
          assigned = row;
          rowEnds.set(row, right);
          break;
        }
      }

      if (assigned == -1) {
        assigned = rowEnds.size();
        if (assigned >= MAX_ROWS) {
          overflow.add(bar);
          continue;
        }
        rowEnds.add(right);
        rows.add(new ArrayList<>());
      }

      rows.get(assigned).add(toVisibleBar(bar, left, chipPct, rows.get(assigned).size()));
    }

    if (rows.isEmpty()) {
      rows.add(new ArrayList<>());
      rowEnds.add(0.0);
    }
    return new Placement(rows, rowEnds, overflow, candidates.size() - overflow.size());
  }

  private static List<OverflowBucket> bucketOverflow(
      List<PreparedBar> overflow,
      int startYear,
      int endYear,
      String laneKey,
      String laneLabel
  ) {
    if (overflow.isEmpty()) {
      return List.of();
    }
    int span = Math.max(1, endYear - startYear);
    int bucketYears = resolveBucketYears(span, overflow.size());
    List<OverflowBucket> buckets = new ArrayList<>();
    int cursor = startYear;
    int index = 0;
    while (cursor < endYear) {
      int bucketEnd = Math.min(endYear, cursor + bucketYears);
      final int bucketStart = cursor;
      final int bucketEndFinal = bucketEnd;
      List<PreparedBar> members = overflow.stream()
          .filter(bar -> bar.anchorYear >= bucketStart && bar.anchorYear < bucketEndFinal)
          .toList();
      if (!members.isEmpty()) {
        buckets.add(new OverflowBucket(bucketStart, bucketEndFinal, members, laneKey, laneLabel, index++));
      }
      cursor = bucketEnd;
    }
    return buckets;
  }

  static int resolveBucketYears(int span, int overflowCount) {
    if (overflowCount <= 0) {
      return span;
    }
    if (span <= MAX_BUCKET_YEARS) {
      return span;
    }
    int minBuckets = Math.max(1, (overflowCount + 11) / 12);
    int maxBuckets = Math.max(minBuckets, (overflowCount + 4) / 5);
    int targetBuckets = Math.min(span / MIN_BUCKET_YEARS, (minBuckets + maxBuckets) / 2);
    targetBuckets = Math.max(1, targetBuckets);
    int bucketYears = (int) Math.ceil((double) span / targetBuckets);
    return Math.max(MIN_BUCKET_YEARS, Math.min(MAX_BUCKET_YEARS, bucketYears));
  }

  private static int placeBucketChip(
      List<List<UnitSwimMatrixDTO.Bar>> rows,
      List<Double> rowEnds,
      OverflowBucket bucket,
      SwimTimeScale scale,
      int sheetRpx,
      double gapPct,
      int bucketRowIndex
  ) {
    String laneLabel = bucket.laneLabel() == null ? "" : bucket.laneLabel().trim();
    String countTag = bucketCountTag(laneLabel, bucket.members().size());
    String title = "查看更多";
    int chipRpx = chipWidthRpx(title, countTag);
    double chipPct = chipRpx / (double) sheetRpx * 100.0;
    int anchorYear = (bucket.startYear() + bucket.endYear()) / 2;
    double left = leftPctFromAnchorForBucket(scale.percentForYear(anchorYear), sheetRpx, chipRpx);
    double right = left + chipPct;

    int assigned = -1;
    if (bucketRowIndex == -1) {
      for (int row = 0; row < rowEnds.size(); row++) {
        if (rowEnds.get(row) + gapPct <= left) {
          assigned = row;
          rowEnds.set(row, right);
          break;
        }
      }
    } else if (bucketRowIndex < rowEnds.size() && rowEnds.get(bucketRowIndex) + gapPct <= left) {
      assigned = bucketRowIndex;
      rowEnds.set(bucketRowIndex, right);
    }

    if (assigned == -1) {
      if (bucketRowIndex == -1) {
        bucketRowIndex = rowEnds.size();
        rowEnds.add(right);
        rows.add(new ArrayList<>());
        assigned = bucketRowIndex;
      } else {
        assigned = bucketRowIndex;
        rowEnds.set(bucketRowIndex, Math.max(rowEnds.get(bucketRowIndex), right));
      }
    }

    rows.get(assigned).add(toBucketBar(bucket, title, countTag, chipRpx, left, chipPct, rows.get(assigned).size()));
    return bucketRowIndex;
  }

  private static String bucketCountTag(String laneLabel, int count) {
    String category = laneLabel.isEmpty() ? "史略" : laneLabel;
    return count + "位" + category;
  }

  private static double leftPctFromAnchor(double centerPct, int sheetRpx, int chipRpx) {
    double chipPct = chipRpx / (double) sheetRpx * 100.0;
    double reservedRightPct = EDGE_GAP_RPX / (double) sheetRpx * 100.0;
    double minLeftPct = EDGE_GAP_RPX / (double) sheetRpx * 100.0;
    double maxLeftPct = 100.0 - chipPct - reservedRightPct;

    double centerRpx = centerPct / 100.0 * sheetRpx;
    double leftRpx = SwimCanvasLayout.snapRpx(centerRpx - chipRpx / 2.0);
    leftRpx = Math.max(EDGE_GAP_RPX, Math.min(sheetRpx - chipRpx - EDGE_GAP_RPX, leftRpx));
    double leftPct = leftRpx / sheetRpx * 100.0;
    return Math.max(minLeftPct, Math.min(maxLeftPct, leftPct));
  }

  private static double leftPctFromAnchorForBucket(double centerPct, int sheetRpx, int chipRpx) {
    return leftPctFromAnchor(centerPct, sheetRpx, chipRpx);
  }

  private static PreparedBar prepare(SwimBarInput input) {
    int start = input.start();
    int end = input.end() <= start ? start + 1 : input.end();
    int anchorYear = input.anchorAtStart() || input.peakYear() == null ? start : input.peakYear();
    String priority = normalizePriority(input.priority());
    String tag = chipTag(input.personTag());
    return new PreparedBar(
        input.boxId(),
        input.title(),
        start,
        end,
        priority,
        priorityRank(priority),
        anchorYear,
        input.peakYear(),
        input.peakReason(),
        parseGlobalId(input.boxId()),
        tag,
        chipWidthRpx(input.title(), tag),
        trimOrNull(input.priorityReason()),
        normalizeEntrySource(input.entrySource())
    );
  }

  private static String normalizeEntrySource(String raw) {
    if (raw == null) {
      return "extract";
    }
    String value = raw.trim().toLowerCase();
    return "supplement".equals(value) ? "supplement" : "extract";
  }

  static int chipWidthRpx(String title, String chipTag) {
    int titleLen = visibleLength(title);
    int titleW = titleLen * CHIP_TITLE_RPX_PER_CHAR;
    int tagW = 0;
    if (chipTag != null) {
      int tagLen = visibleLength(chipTag);
      tagW = CHIP_TAG_PAD_H_RPX + tagLen * CHIP_TAG_RPX_PER_CHAR + CHIP_INNER_GAP_RPX;
    }
    int raw = CHIP_PAD_H_RPX + titleW + tagW;
    return SwimCanvasLayout.snap(Math.max(CHIP_MIN_RPX, Math.min(CHIP_MAX_RPX, raw)));
  }

  private static int visibleLength(String value) {
    if (value == null) {
      return 0;
    }
    String trimmed = value.trim();
    return trimmed.codePointCount(0, trimmed.length());
  }

  private static UnitSwimMatrixDTO.Bar toVisibleBar(
      PreparedBar bar,
      double leftPct,
      double widthPct,
      int zOffset
  ) {
    String left = fmtPct(leftPct);
    String width = fmtPct(widthPct);
    String chipWidth = bar.chipWidthRpx + "rpx";
    return new UnitSwimMatrixDTO.Bar(
        bar.title,
        bar.boxId,
        bar.boxId,
        bar.title,
        left,
        width,
        left,
        width,
        "0rpx",
        chipWidth,
        "0rpx",
        "0rpx",
        "0rpx",
        bar.priority,
        "default",
        10 + zOffset,
        HistoryYearFormat.label(bar.start) + " — " + HistoryYearFormat.label(bar.end),
        bar.start,
        bar.end,
        bar.peakYear,
        bar.peakReason,
        bar.globalIdNumber,
        0,
        CHIP_HEIGHT_RPX,
        bar.chipTag,
        bar.priorityReason,
        bar.entrySource
    );
  }

  private static UnitSwimMatrixDTO.Bar toBucketBar(
      OverflowBucket bucket,
      String title,
      String countTag,
      int chipRpx,
      double leftPct,
      double widthPct,
      int zOffset
  ) {
    String boxId = "BUCKET_" + bucket.laneKey() + "_" + bucket.index();
    int anchorYear = (bucket.startYear() + bucket.endYear()) / 2;
    return new UnitSwimMatrixDTO.Bar(
        title,
        boxId,
        boxId,
        title,
        fmtPct(leftPct),
        fmtPct(widthPct),
        fmtPct(leftPct),
        fmtPct(widthPct),
        "0rpx",
        chipRpx + "rpx",
        "0rpx",
        "0rpx",
        "0rpx",
        "p3",
        "overflow_bucket",
        5 + zOffset,
        HistoryYearFormat.label(bucket.startYear()) + " — " + HistoryYearFormat.label(bucket.endYear()),
        bucket.startYear(),
        bucket.endYear(),
        anchorYear,
        null,
        0,
        0,
        CHIP_HEIGHT_RPX,
        countTag,
        null,
        null
    );
  }

  private static UnitSwimMatrixDTO.Bar toOverlayBar(PreparedBar bar, SwimTimeScale scale, int sheetRpx) {
    String left = fmtPct(leftPctFromAnchor(scale.percentForYear(bar.anchorYear), sheetRpx, bar.chipWidthRpx));
    return new UnitSwimMatrixDTO.Bar(
        bar.title,
        bar.boxId,
        bar.boxId,
        bar.title,
        left,
        "0%",
        left,
        "0%",
        "0rpx",
        bar.chipWidthRpx + "rpx",
        "0rpx",
        "0rpx",
        "0rpx",
        bar.priority,
        "default",
        0,
        HistoryYearFormat.label(bar.start) + " — " + HistoryYearFormat.label(bar.end),
        bar.start,
        bar.end,
        bar.peakYear,
        bar.peakReason,
        bar.globalIdNumber,
        0,
        CHIP_HEIGHT_RPX,
        bar.chipTag,
        bar.priorityReason,
        bar.entrySource
    );
  }

  private static String trimOrNull(String value) {
    if (value == null) {
      return null;
    }
    String trimmed = value.trim();
    return trimmed.isEmpty() ? null : trimmed;
  }

  private static String chipTag(String personTag) {
    if (personTag == null) {
      return null;
    }
    String value = personTag.trim();
    return value.isEmpty() ? null : value;
  }

  static int trackHeight(int rowCount) {
    int rows = Math.max(1, rowCount);
    return TRACK_PAD_VERTICAL_RPX + rows * CHIP_HEIGHT_RPX + (rows - 1) * ROW_GAP_RPX;
  }

  static int parseGlobalId(String boxId) {
    Matcher matcher = GLOBAL_ID.matcher(boxId == null ? "" : boxId);
    if (!matcher.matches()) {
      throw new IllegalArgumentException("Invalid global box id format");
    }
    return Integer.parseInt(matcher.group(1));
  }

  static int priorityRank(String priority) {
    return switch (normalizePriority(priority)) {
      case "p0" -> 0;
      case "p1" -> 1;
      case "p2" -> 2;
      default -> 3;
    };
  }

  private static String normalizePriority(String priority) {
    String value = priority == null ? "" : priority.trim().toLowerCase();
    return PRIORITY_LEVELS.contains(value) ? value : "p3";
  }

  private static double moreLeftPct(int sheetRpx) {
    return 100.0 - ((EDGE_GAP_RPX + MORE_RPX) / (double) sheetRpx * 100.0);
  }

  private static String fmtPct(double value) {
    return String.format("%.2f%%", value);
  }

  private record Placement(
      List<List<UnitSwimMatrixDTO.Bar>> rows,
      List<Double> rowEnds,
      List<PreparedBar> overflow,
      int visibleCount
  ) {}

  private record OverflowBucket(
      int startYear,
      int endYear,
      List<PreparedBar> members,
      String laneKey,
      String laneLabel,
      int index
  ) {}

  private record PreparedBar(
      String boxId,
      String title,
      int start,
      int end,
      String priority,
      int priorityRank,
      int anchorYear,
      Integer peakYear,
      String peakReason,
      int globalIdNumber,
      String chipTag,
      int chipWidthRpx,
      String priorityReason,
      String entrySource
  ) {
    static final Comparator<PreparedBar> ORDER = Comparator
        .comparingInt((PreparedBar bar) -> bar.priorityRank)
        .thenComparingInt(bar -> bar.anchorYear)
        .thenComparingInt(bar -> bar.globalIdNumber);
  }
}
