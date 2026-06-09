package com.pandahis.histomap.contentgraph.interfaces.dto;

import java.util.List;

public record BoxCritiquesDTO(List<Item> items) {
  public record Item(String title, String blurb, String author, String eraText, Integer year, String content, String source) {}
}

