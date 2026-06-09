package com.pandahis.histomap.contentgraph.interfaces.dto;

import java.util.List;

public record BoxGraphDTO(String centerNodeKey, List<Node> nodes, List<Edge> edges) {
  public record Node(String key, String type, String name, String badgeText, Integer weight, String targetBoxId, String extraJson) {}

  public record Edge(String fromKey, String toKey, String label) {}
}

