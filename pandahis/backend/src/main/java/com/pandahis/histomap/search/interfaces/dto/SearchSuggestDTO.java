package com.pandahis.histomap.search.interfaces.dto;

import java.util.List;

public record SearchSuggestDTO(List<HotKeyword> hotKeywords, List<HistoryKeyword> historyKeywords) {
  public record HotKeyword(String keyword, boolean isHot) {}

  public record HistoryKeyword(String keyword, String lastSearchedAt) {}
}

