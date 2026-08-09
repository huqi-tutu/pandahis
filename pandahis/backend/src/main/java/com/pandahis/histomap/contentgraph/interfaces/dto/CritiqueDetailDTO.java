package com.pandahis.histomap.contentgraph.interfaces.dto;

public record CritiqueDetailDTO(
    long id,
    String boxId,
    String boxTitle,
    String civilizationName,
    String dynastyName,
    String title,
    String blurb,
    String author,
    String eraText,
    Integer year,
    String content,
    String source
) {}
