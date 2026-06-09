package com.pandahis.histomap.contentgraph.interfaces.dto;

import java.util.List;

/** 沉浸首页 · 政权矩阵布局（对齐产品 home-matrix） */
public record HomeMatrixDTO(
    List<Row> rows,
    List<Block> blocks,
    List<Overlay> overlays,
    int totalHRpx
) {
  public record Row(
      String key,
      int y,
      int h,
      String year,
      String hxLabel,
      boolean showYear,
      boolean expandable,
      boolean expanded,
      String dynastyKey
  ) {}

  public record Block(
      String id,
      int top,
      int h,
      double leftPct,
      double widthPct,
      String cardBg,
      String person,
      String dynasty,
      String civ,
      int anchorYear,
      String unitId,
      String kind,
      String displayName,
      String timeRange,
      String radiusStyle,
      String edgeClass,
      /** 产品矩阵 entryId（如 zhong_hua_wu_di_huang_di 纹理块） */
      String entryId,
      boolean fillSeamFix,
      boolean seamGapTop,
      boolean seamGapBottom,
      boolean seamGapLeft,
      boolean seamGapRight,
      String fillStyleExtra
  ) {}

  public record Overlay(
      String id,
      int headerTop,
      double headerLeftPct,
      double headerWidthPct,
      int timeWrapTop,
      double timeLeftPct,
      double timeWidthPct,
      int timeWrapH,
      String timeCorner,
      int timeFontRpx,
      String labelLayout,
      String kind,
      String person,
      String displayName,
      String timeRange,
      boolean hideLabels,
      boolean hideTags,
      boolean hideTime,
      List<HighlightTag> highlights
  ) {}

  public record HighlightTag(String text, String tagStyle) {}
}
