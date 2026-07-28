package com.pandahis.histomap.user.interfaces.dto;

import java.util.List;

public record UnitFavoriteListDTO(int page, int pageSize, long total, List<Item> items) {
  public record Item(
      String unitId,
      String title,
      String subText,
      String favoritedAt,
      int startYear,
      int endYear,
      String pathLabel
  ) {}
}
