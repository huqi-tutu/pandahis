package com.pandahis.histomap.search.interfaces.service;

import com.pandahis.histomap.search.interfaces.dto.SearchSuggestDTO;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;

class SearchServiceDedupeTest {

  @Test
  void dedupeHotKeywordsKeepsFirstAndLimit() {
    List<SearchSuggestDTO.HotKeyword> raw = List.of(
        new SearchSuggestDTO.HotKeyword("乌台诗案", true),
        new SearchSuggestDTO.HotKeyword("宋神宗", false),
        new SearchSuggestDTO.HotKeyword("乌台诗案", false),
        new SearchSuggestDTO.HotKeyword("宋神宗", true),
        new SearchSuggestDTO.HotKeyword("苏轼", false)
    );

    List<SearchSuggestDTO.HotKeyword> out = SearchService.dedupeHotKeywords(raw, 3);

    assertEquals(3, out.size());
    assertEquals("乌台诗案", out.get(0).keyword());
    assertEquals(true, out.get(0).isHot());
    assertEquals("宋神宗", out.get(1).keyword());
    assertEquals(false, out.get(1).isHot());
    assertEquals("苏轼", out.get(2).keyword());
  }
}
