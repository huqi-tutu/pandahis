package com.pandahis.histomap.user.interfaces.dto;

import java.util.List;

public record CorrectionListDTO(
    int page,
    int pageSize,
    long total,
    List<Item> items
) {
  public record Item(
      long id,
      String boxId,
      String boxTitle,
      String status,
      String createdAt
  ) {}
}
