package com.pandahis.histomap.contentgraph.interfaces.dto;

import java.util.List;

/** 朝代详情 · 横向泳道矩阵 */
public record UnitSwimMatrixDTO(
    int startYear,
    int endYear,
    String endLabel,
    List<AxisTick> ticks,
    List<Lane> lanes,
    List<String> concurrentItems,
    int sheetWidthRpx
) {
  public record AxisTick(String label, String left) {}

  public record Lane(
      String label,
      String borderColor,
      String layout,
      List<List<Bar>> collapsedRows,
      boolean hasMore,
      int moreCount,
      String moreBarLeft,
      String moreBarWidth
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
      String timeRange
  ) {}
}
