package com.pandahis.histomap.contentgraph.interfaces.dto;

import java.util.List;

/** PRD V1.1 王朝层：朝代名称、简介；附带「其他地域」「下一朝代」导航数据 */
public record UnitHeroDTO(
    Unit unit,
    List<CategoryTip> categoryTips,
    List<RelatedUnit> relatedUnits,
    NextUnit nextUnit
) {
  public record Unit(
      String id,
      String name,
      String rulerName,
      String dynastyName,
      String crumbText,
      String eraText,
      String templeName,
      String eraTitle,
      int startYear,
      int endYear,
      int durationYears,
      String summary,
      String cardImageUrl
  ) {}

  public record CategoryTip(String key, String name, String desc) {}

  public record RelatedUnit(String unitId, String title, int startYear) {}

  /** 同地域时间线上的下一单元；无则 null */
  public record NextUnit(String unitId, String title, int startYear) {}
}
