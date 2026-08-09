package com.pandahis.histomap.contentgraph.interfaces.dto;

import java.util.List;

public record HomeGridDTO(
    List<TimeAxisItem> timeAxis,
    List<Civilization> civilizations,
    List<Cell> cells,
    Overview overview,
    FeatureFlags flags
) {
  /** 与 GET /config/features 一致，供首页无需二次请求 */
  public record FeatureFlags(boolean civSwitchEnabled) {}

  public HomeGridDTO {
    if (flags == null) {
      flags = new FeatureFlags(true);
    }
  }
  /** rowHeightPx：与小程序矩阵行 min-height 一致，使用 rpx 数值（如 56–180） */
  public record TimeAxisItem(int year, String label, int rowHeightPx) {}

  public record Civilization(long id, String displayName, String code, String colorHex, String tabImageUrl, int sortOrder) {}

  public record Cell(int timeYear, long civId, UnitCard unitCard) {}

  public record UnitCard(
      String unitId,
      String title,
      String note,
      String meta,
      int startYear,
      int endYear,
      int durationYears,
      String variant,
      List<String> highlights,
      String cardImageUrl,
      /** 一级地域 brand 色，用于卡片左边线等 UI */
      String accentHex
  ) {}

  /** 全景总览：地图 URL + 归一化热区（0~1） */
  public record Overview(String mapImageUrl, List<Hotspot> hotspots) {
    public Overview {
      if (mapImageUrl == null) {
        mapImageUrl = "";
      }
      if (hotspots == null) {
        hotspots = List.of();
      }
    }
  }

  public record Hotspot(String unitId, double left, double top, double width, double height) {}
}
