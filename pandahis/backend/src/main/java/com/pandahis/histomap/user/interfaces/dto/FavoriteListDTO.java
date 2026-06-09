package com.pandahis.histomap.user.interfaces.dto;

import java.util.List;

public record FavoriteListDTO(int page, int pageSize, long total, List<Item> items) {
  public record Item(
      String boxId,
      String title,
      String subText,
      String categoryKey,
      String favoritedAt,
      int startYear,
      int endYear,
      String pathLabel
  ) {}
}

