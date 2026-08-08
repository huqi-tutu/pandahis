package com.pandahis.histomap.wikipedia;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.pandahis.histomap.common.config.HistomapProperties;
import com.pandahis.histomap.wikipedia.interfaces.dto.WikipediaLookupDTO;
import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class WikipediaLookupServiceTest {

  @Mock
  private WikipediaClient wikipediaClient;

  private WikipediaLookupService service;

  @BeforeEach
  void setUp() {
    HistomapProperties props = new HistomapProperties();
    props.getWikipedia().setCacheTtlSeconds(3600);
    props.getWikipedia().setDefaultLimit(3);
    props.getWikipedia().setMaxLimit(8);
    service = new WikipediaLookupService(wikipediaClient, props);
  }

  @Test
  void lookup_notFound_returnsEmptyFoundFalse() {
    when(wikipediaClient.fetchArticle("不存在词条")).thenReturn(Optional.empty());

    WikipediaLookupDTO dto = service.lookup("不存在词条", 0, 3);

    assertEquals("不存在词条", dto.query());
    assertFalse(dto.found());
    assertNull(dto.resolvedTitle());
    assertTrue(dto.paragraphs().isEmpty());
    assertFalse(dto.hasMore());
    assertNull(dto.nextOffset());
    assertEquals(0, dto.totalParagraphs());
  }

  @Test
  void lookup_pagesByCompleteParagraphs() {
    when(wikipediaClient.fetchArticle("禅让制"))
        .thenReturn(
            Optional.of(
                new WikipediaArticle(
                    "禅让制",
                    List.of("第一段。", "第二段。", "第三段。", "第四段。"))));

    WikipediaLookupDTO first = service.lookup("禅让制", 0, 3);
    assertTrue(first.found());
    assertEquals("禅让制", first.resolvedTitle());
    assertEquals(List.of("第一段。", "第二段。", "第三段。"), first.paragraphs());
    assertTrue(first.hasMore());
    assertEquals(3, first.nextOffset());
    assertEquals(4, first.totalParagraphs());

    WikipediaLookupDTO second = service.lookup("禅让制", 3, 3);
    assertEquals(List.of("第四段。"), second.paragraphs());
    assertFalse(second.hasMore());
    assertNull(second.nextOffset());

    // 同一 query 应命中缓存，只拉一次上游
    verify(wikipediaClient, times(1)).fetchArticle("禅让制");
  }

  @Test
  void lookup_titleDiffersFromQuery() {
    when(wikipediaClient.fetchArticle("涿鹿之战"))
        .thenReturn(Optional.of(new WikipediaArticle("涿鹿之戰", List.of("正文。"))));

    WikipediaLookupDTO dto = service.lookup("涿鹿之战", 0, 3);
    assertEquals("涿鹿之战", dto.query());
    assertEquals("涿鹿之戰", dto.resolvedTitle());
  }

  @Test
  void lookup_upstreamError_degradesToNotFound() {
    when(wikipediaClient.fetchArticle(anyString()))
        .thenThrow(new RuntimeException("timeout"));

    WikipediaLookupDTO dto = service.lookup("黄帝", 0, 3);
    assertFalse(dto.found());
    assertTrue(dto.paragraphs().isEmpty());

    // 失败负缓存：再次查询不应打上游
    WikipediaLookupDTO again = service.lookup("黄帝", 0, 3);
    assertFalse(again.found());
    verify(wikipediaClient, times(1)).fetchArticle("黄帝");
  }
}
