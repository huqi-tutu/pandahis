package com.pandahis.histomap.contentgraph.interfaces.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

class BoxEntryDeduperTest {

  @Test
  void hidesThinExtractWhenSupplementExistsWithSameTitle() {
    List<Map<String, Object>> boxes = List.of(
        box("GLBL_00031", "周昭王", "junji", "周昭王", "extract"),
        box("GLBL_00816", "周昭王", "junji", "周昭王在位期间南征荆楚…", "supplement"),
        box("GLBL_00035", "周武王", "junji", "周武王伐纣建周…", "extract")
    );

    List<Map<String, Object>> out = BoxEntryDeduper.hideThinExtractWhenSupplementExists(boxes);

    assertEquals(2, out.size());
    assertTrue(out.stream().noneMatch(b -> "GLBL_00031".equals(b.get("id"))));
    assertTrue(out.stream().anyMatch(b -> "GLBL_00816".equals(b.get("id"))));
    assertTrue(out.stream().anyMatch(b -> "GLBL_00035".equals(b.get("id"))));
  }

  @Test
  void keepsExtractWhenBlurbIsNotThin() {
    List<Map<String, Object>> boxes = List.of(
        box("GLBL_00035", "周武王", "junji", "周武王伐纣建周，牧野之战…", "extract"),
        box("GLBL_00816", "周昭王", "junji", "周昭王在位…", "supplement")
    );

    List<Map<String, Object>> out = BoxEntryDeduper.hideThinExtractWhenSupplementExists(boxes);

    assertEquals(2, out.size());
  }

  private static Map<String, Object> box(
      String id, String title, String categoryKey, String blurb, String entrySource
  ) {
    Map<String, Object> row = new LinkedHashMap<>();
    row.put("id", id);
    row.put("title", title);
    row.put("category_key", categoryKey);
    row.put("blurb", blurb);
    row.put("entry_source", entrySource);
    return row;
  }
}
