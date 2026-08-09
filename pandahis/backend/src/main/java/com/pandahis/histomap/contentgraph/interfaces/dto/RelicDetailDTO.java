package com.pandahis.histomap.contentgraph.interfaces.dto;

public record RelicDetailDTO(
    long id,
    String boxId,
    String boxTitle,
    String civilizationName,
    String dynastyName,
    String name,
    String imageUrl,
    String summary,
    String description,
    String museum,
    String priorityCode
) {}
