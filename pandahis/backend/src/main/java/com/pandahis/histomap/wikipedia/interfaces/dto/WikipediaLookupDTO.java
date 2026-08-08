package com.pandahis.histomap.wikipedia.interfaces.dto;

import java.util.List;

public record WikipediaLookupDTO(
    String query,
    boolean found,
    String resolvedTitle,
    List<String> paragraphs,
    int offset,
    Integer nextOffset,
    boolean hasMore,
    int totalParagraphs
) {}
