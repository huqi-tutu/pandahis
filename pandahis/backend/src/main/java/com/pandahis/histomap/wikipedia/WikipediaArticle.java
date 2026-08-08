package com.pandahis.histomap.wikipedia;

import java.util.List;

/** 已清洗、已按完整段落拆好的维基词条。 */
public record WikipediaArticle(String resolvedTitle, List<String> paragraphs) {
  public WikipediaArticle {
    paragraphs = paragraphs == null ? List.of() : List.copyOf(paragraphs);
  }
}
