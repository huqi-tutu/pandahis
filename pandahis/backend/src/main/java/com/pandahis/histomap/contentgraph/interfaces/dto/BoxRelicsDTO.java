package com.pandahis.histomap.contentgraph.interfaces.dto;

import java.util.List;

public record BoxRelicsDTO(List<Item> items) {
  public record Item(String name, String imageUrl, String summary, String description, String museum, String priorityCode) {}
}

