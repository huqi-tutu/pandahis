package com.pandahis.histomap.search.interfaces.dto;

import java.util.List;

public record SearchResultDTO(long total, int page, int pageSize, List<Item> items) {
  public record Item(String type, String id, String pathText, String titleHighlight, String descHighlight) {}
}

