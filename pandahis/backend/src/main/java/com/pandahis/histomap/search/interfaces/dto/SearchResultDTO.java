package com.pandahis.histomap.search.interfaces.dto;

import java.util.List;

public record SearchResultDTO(
    long total,
    int page,
    int pageSize,
    long preciseTotal,
    long relatedTotal,
    List<Item> preciseItems,
    List<Item> relatedItems,
    /** 兼容旧客户端：精准在前、相关在后的扁平列表 */
    List<Item> items
) {
  /**
   * @param matchTier {@code precise} 名称/简介命中；{@code related} 详情正文命中
   */
  public record Item(
      String type,
      String id,
      String pathText,
      String titleHighlight,
      String descHighlight,
      String matchTier,
      String categoryKey,
      String categoryName,
      String coordinateText,
      Integer startYear,
      Integer endYear,
      String personTag
  ) {}
}
