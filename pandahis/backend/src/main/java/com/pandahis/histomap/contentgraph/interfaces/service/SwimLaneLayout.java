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

/** 朝代详情泳道布局：固定胶囊，以 peakYear 定位并按优先级视图折叠。 */
final class SwimLaneLayout {
  static final int MAX_ROWS = 10;
  static final int CHIP_RPX = 132;
  static final int CHIP_HEIGHT_RPX = 44;
  static final int CHIP_GAP_RPX = 16;
  static final int EDGE_GAP_RPX = 20;
  static final int MORE_RPX = 112;
  static final int MORE_GAP_RPX = 20;
  static final int TRACK_PAD_VERTICAL_RPX = 24;
  static final int SHEET_RPX = 1440;

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
      boolean anchorAtStart
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
    Map<String, UnitSwimMatrixDTO.LaneView> views = new LinkedHashMap<>();
    for (String threshold : PRIORITY_LEVELS) {
      views.put(threshold, buildPriorityView(bars, threshold, scale, sheetRpx));
    }
    return views;
  }

  private static UnitSwimMatrixDTO.LaneView buildPriorityView(
      List<SwimBarInput> bars,
      String threshold,
      SwimTimeScale scale,
      int sheetRpx
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
    List<PreparedBar> extra = new ArrayList<>(hiddenByPriority);
    extra.addAll(placement.overflow);
    extra.sort(PreparedBar.ORDER);

    int rowCount = Math.max(1, placement.rows.size());
    int height = trackHeight(rowCount);
    boolean hasMore = !extra.isEmpty();
    String moreLeft = fmtPct(moreLeftPct(sheetRpx));

    return new UnitSwimMatrixDTO.LaneView(
        placement.rows,
        hasMore,
        extra.size(),
        moreLeft,
        "12%",
        extra.stream().map(bar -> toOverlayBar(bar, scale)).toList(),
        rowCount,
        height,
        placement.visibleCount
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

    double chipPct = CHIP_RPX / (double) sheetRpx * 100.0;
    double gapPct = CHIP_GAP_RPX / (double) sheetRpx * 100.0;
    double edgePct = EDGE_GAP_RPX / (double) sheetRpx * 100.0;
    double reservedRightPct = (EDGE_GAP_RPX + MORE_GAP_RPX + MORE_RPX) / (double) sheetRpx * 100.0;

    for (PreparedBar bar : candidates) {
      double anchorLeft = scale.percentForYear(bar.anchorYear);
      double left = Math.max(edgePct, Math.min(100 - chipPct - reservedRightPct, anchorLeft));
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
    }
    return new Placement(rows, overflow, candidates.size() - overflow.size());
  }

  private static PreparedBar prepare(SwimBarInput input) {
    int start = input.start();
    int end = input.end() <= start ? start + 1 : input.end();
    int anchorYear = input.anchorAtStart() || input.peakYear() == null ? start : input.peakYear();
    String priority = normalizePriority(input.priority());
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
        parseGlobalId(input.boxId())
    );
  }

  private static UnitSwimMatrixDTO.Bar toVisibleBar(
      PreparedBar bar,
      double leftPct,
      double widthPct,
      int zOffset
  ) {
    String left = fmtPct(leftPct);
    String width = fmtPct(widthPct);
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
        CHIP_RPX + "rpx",
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
        bar.globalIdNumber
    );
  }

  private static UnitSwimMatrixDTO.Bar toOverlayBar(PreparedBar bar, SwimTimeScale scale) {
    String left = fmtPct(scale.percentForYear(bar.anchorYear));
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
        CHIP_RPX + "rpx",
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
        bar.globalIdNumber
    );
  }

  static int trackHeight(int rowCount) {
    int rows = Math.max(1, Math.min(MAX_ROWS, rowCount));
    return TRACK_PAD_VERTICAL_RPX + rows * CHIP_HEIGHT_RPX + (rows - 1) * CHIP_GAP_RPX;
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

  private static double percentForYear(int year, int startYear, int span) {
    return Math.max(0, Math.min(100, 100.0 * (year - startYear) / Math.max(1, span)));
  }

  private static double moreLeftPct(int sheetRpx) {
    return 100.0 - ((EDGE_GAP_RPX + MORE_RPX) / (double) sheetRpx * 100.0);
  }

  private static String fmtPct(double value) {
    return String.format("%.2f%%", value);
  }

  private record Placement(
      List<List<UnitSwimMatrixDTO.Bar>> rows,
      List<PreparedBar> overflow,
      int visibleCount
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
      int globalIdNumber
  ) {
    static final Comparator<PreparedBar> ORDER = Comparator
        .comparingInt((PreparedBar bar) -> bar.priorityRank)
        .thenComparingInt(bar -> bar.anchorYear)
        .thenComparingInt(bar -> bar.globalIdNumber);
  }
}
