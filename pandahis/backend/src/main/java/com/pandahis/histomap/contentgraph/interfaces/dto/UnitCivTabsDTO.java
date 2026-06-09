package com.pandahis.histomap.contentgraph.interfaces.dto;

import java.util.List;

public record UnitCivTabsDTO(List<Tab> tabs) {
  public record Tab(long civilizationId, String civilizationName, String unitId, boolean isActive) {}
}

