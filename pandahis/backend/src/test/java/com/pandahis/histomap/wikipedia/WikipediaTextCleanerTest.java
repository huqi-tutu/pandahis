package com.pandahis.histomap.wikipedia;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import org.junit.jupiter.api.Test;

class WikipediaTextCleanerTest {

  @Test
  void clean_removesPinyinAndZhuyinParentheses() {
    String raw =
        "禅让制（“禅”，拼音：shàn，注音：ㄕㄢˋ，音同“擅”），中国统治者更迭的一种方式。";
    String cleaned = WikipediaTextCleaner.clean(raw);
    assertEquals("禅让制，中国统治者更迭的一种方式。", cleaned);
  }

  @Test
  void clean_removesInlineLatinPinyinParentheses() {
    String raw = "涿（zhuō）鹿之战是相传中国远古时代的一次战争。";
    String cleaned = WikipediaTextCleaner.clean(raw);
    assertEquals("涿鹿之战是相传中国远古时代的一次战争。", cleaned);
  }

  @Test
  void clean_preservesPlainText() {
    String raw = "阪泉之战是中国上古时期传说中的一场战争。";
    assertEquals(raw, WikipediaTextCleaner.clean(raw));
  }

  @Test
  void toParagraphs_splitsOnBlankLinesAndDropsEmpty() {
    String raw = "第一段。\n\n\n第二段。\n\n";
    List<String> paragraphs = WikipediaTextCleaner.toParagraphs(raw);
    assertEquals(List.of("第一段。", "第二段。"), paragraphs);
  }

  @Test
  void toParagraphs_singleBlock_returnsOne() {
    List<String> paragraphs = WikipediaTextCleaner.toParagraphs("只有一段文字。");
    assertEquals(1, paragraphs.size());
    assertEquals("只有一段文字。", paragraphs.get(0));
  }

  @Test
  void toParagraphs_blank_returnsEmpty() {
    assertTrue(WikipediaTextCleaner.toParagraphs("   ").isEmpty());
    assertTrue(WikipediaTextCleaner.toParagraphs(null).isEmpty());
  }
}
