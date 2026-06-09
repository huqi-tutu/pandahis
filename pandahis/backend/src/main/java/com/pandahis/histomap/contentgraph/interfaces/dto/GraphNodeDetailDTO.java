package com.pandahis.histomap.contentgraph.interfaces.dto;

public record GraphNodeDetailDTO(
    String name,
    String category,
    String role,
    String level,
    String lineage,
    String summary,
    String targetBoxId
) {}
