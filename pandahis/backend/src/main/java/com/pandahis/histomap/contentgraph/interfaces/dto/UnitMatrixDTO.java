package com.pandahis.histomap.contentgraph.interfaces.dto;

import java.util.List;

public record UnitMatrixDTO(List<YearItem> years, List<Category> categories, List<Item> items) {
  public record YearItem(int year, String label) {}

  public record Category(String key, String name) {}

  public record Item(String boxId, int year, String categoryKey, String title, String blurb, boolean highlight) {}
}

