package com.pandahis.histomap.user.interfaces.dto;

import java.util.List;

public record NoteDynastyListDTO(List<Item> items) {
  public record Item(
      String dynastyId,
      String dynastyName,
      String civilizationName,
      int noteCount,
      Integer startYear
  ) {}
}
