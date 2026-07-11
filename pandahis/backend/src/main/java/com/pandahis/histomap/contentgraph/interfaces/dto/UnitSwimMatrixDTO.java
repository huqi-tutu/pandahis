package com.pandahis.histomap.contentgraph.interfaces.dto;

import java.util.List;
import java.util.Map;

/** 朝代详情 · 横向泳道矩阵 */
public record UnitSwimMatrixDTO(
    int startYear,
    int endYear,
    String endLabel,
    List<AxisTick> ticks,
    List<GridLine> gridLines,
    List<TimeSegment> timeSegments,
    String timeScaleMode,
    List<Lane> lanes,
    List<String> concurrentItems,
    int sheetWidthRpx
) {
  public record AxisTick(
      String label,
      String left,
      boolean edgeStart,
      boolean hideLabel,
      boolean segmentBoundary
  ) {}

  public record GridLine(String left, boolean segmentBoundary) {}

  public record TimeSegment(
      int startYear,
      int endYear,
      String startLabel,
      String endLabel,
      String left,
      String width,
      int boxCount,
      boolean dense
  ) {}

  public record Lane(
      String key,
      String label,
      String icon,
      String borderColor,
      String layout,
      int totalCount,
      Integer readCount,
      String readProgressText,
      List<List<Bar>> collapsedRows,
      boolean hasMore,
      int moreCount,
      String moreBarLeft,
      String moreBarWidth,
      List<Bar> extraBars,
      Map<String, LaneView> priorityViews,
      int rowCount,
      int trackHeightRpx,
      int visibleCount
  ) {}

  public record LaneView(
      List<List<Bar>> collapsedRows,
      boolean hasMore,
      int moreCount,
      String moreBarLeft,
      String moreBarWidth,
      List<Bar> extraBars,
      int rowCount,
      int trackHeightRpx,
      int visibleCount
  ) {}

  public record Bar(
      String title,
      String boxId,
      String boxKey,
      String boxTitle,
      String left,
      String width,
      String unitLeft,
      String unitWidth,
      String chipLeft,
      String chipWidth,
      String lineLeftW,
      String lineRightL,
      String lineRightW,
      String priority,
      String type,
      int zIndex,
      String timeRange,
      int startYear,
      int endYear,
      Integer peakYear,
      String peakReason,
      int globalIdNumber
  ) {}
}
