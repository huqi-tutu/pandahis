package com.pandahis.histomap.search.interfaces.service;

import com.pandahis.histomap.search.interfaces.dto.SearchSuggestDTO;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

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

  @Test
  void joinCoordinateUsesMiddleDotAndFourLevels() {
    assertEquals(
        "华夏 · 宋 · 北宋 · 宋神宗",
        SearchService.joinCoordinate("华夏", "宋", "北宋", "宋神宗")
    );
    assertEquals(
        "华夏 · 北宋 · 宋神宗",
        SearchService.joinCoordinate("华夏", "北宋", "北宋", "宋神宗")
    );
    assertEquals("华夏 · 夏", SearchService.joinCoordinate("华夏", "夏", "", ""));
    assertEquals("", SearchService.joinCoordinate("", "", "", ""));
  }

  @Test
  void slicePageRespectsOffsetAndLimit() {
    List<String> all = List.of("a", "b", "c", "d", "e");
    assertEquals(List.of("a", "b"), SearchService.slicePage(all, 1, 2));
    assertEquals(List.of("c", "d"), SearchService.slicePage(all, 2, 2));
    assertEquals(List.of("e"), SearchService.slicePage(all, 3, 2));
    assertEquals(List.of(), SearchService.slicePage(all, 4, 2));
  }

  @Test
  void sortPreciseRowsPutsExactTitleFirstThenHigherPriority() {
    List<Map<String, Object>> rows = new ArrayList<>(List.of(
        row("乐羊", 2, -408),
        row("李悝", 0, -455),
        row("魏文侯", 0, -445)
    ));

    SearchService.sortPreciseRows(rows, "魏文侯");

    assertEquals("魏文侯", rows.get(0).get("title"));
    assertEquals("李悝", rows.get(1).get("title"));
    assertEquals("乐羊", rows.get(2).get("title"));
  }

  @Test
  void sortRelatedRowsOrdersByImportanceAscThenStartYear() {
    List<Map<String, Object>> rows = new ArrayList<>(List.of(
        row("乙", 2, -400),
        row("甲", 0, -390),
        row("丙", 0, -410)
    ));

    SearchService.sortRelatedRows(rows);

    assertEquals("丙", rows.get(0).get("title"));
    assertEquals("甲", rows.get(1).get("title"));
    assertEquals("乙", rows.get(2).get("title"));
  }

  private static Map<String, Object> row(String title, int importance, int startYear) {
    Map<String, Object> m = new LinkedHashMap<>();
    m.put("title", title);
    m.put("importance_level", importance);
    m.put("start_year", startYear);
    return m;
  }
}
