package com.pandahis.histomap.contentgraph.interfaces.service;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

/**
 * 朝代泳道去重：同名同类下若已有二期「模型补全」(supplement)，则隐藏一期史料提取(extract)薄条。
 */
public final class BoxEntryDeduper {
  private static final String SOURCE_EXTRACT = "extract";
  private static final String SOURCE_SUPPLEMENT = "supplement";

  private BoxEntryDeduper() {}

  public static List<Map<String, Object>> hideThinExtractWhenSupplementExists(List<Map<String, Object>> boxes) {
    if (boxes == null || boxes.isEmpty()) {
      return boxes == null ? List.of() : boxes;
    }

    Map<String, List<Map<String, Object>>> groups = new HashMap<>();
    for (Map<String, Object> box : boxes) {
      String key = groupKey(box);
      groups.computeIfAbsent(key, ignored -> new ArrayList<>()).add(box);
    }

    Set<String> hideIds = new HashSet<>();
    for (List<Map<String, Object>> group : groups.values()) {
      boolean hasSupplement = group.stream().anyMatch(BoxEntryDeduper::isSupplement);
      if (!hasSupplement) {
        continue;
      }
      for (Map<String, Object> box : group) {
        if (isExtract(box) && isThinBlurb(box)) {
          hideIds.add(id(box));
        }
      }
    }

    if (hideIds.isEmpty()) {
      return boxes;
    }
    return boxes.stream().filter(box -> !hideIds.contains(id(box))).toList();
  }

  private static String groupKey(Map<String, Object> box) {
    return normalize(title(box)) + "\0" + normalize(categoryKey(box));
  }

  private static boolean isSupplement(Map<String, Object> box) {
    return SOURCE_SUPPLEMENT.equalsIgnoreCase(entrySource(box));
  }

  private static boolean isExtract(Map<String, Object> box) {
    return SOURCE_EXTRACT.equalsIgnoreCase(entrySource(box));
  }

  private static boolean isThinBlurb(Map<String, Object> box) {
    String title = title(box);
    String blurb = blurb(box);
    if (blurb.isEmpty()) {
      return true;
    }
    return blurb.equals(title);
  }

  private static String id(Map<String, Object> box) {
    return Objects.toString(box.get("id"), "").trim();
  }

  private static String title(Map<String, Object> box) {
    return normalize(Objects.toString(box.get("title"), ""));
  }

  private static String blurb(Map<String, Object> box) {
    return normalize(Objects.toString(box.get("blurb"), ""));
  }

  private static String categoryKey(Map<String, Object> box) {
    return normalize(Objects.toString(box.get("category_key"), ""));
  }

  private static String entrySource(Map<String, Object> box) {
    return normalize(Objects.toString(box.get("entry_source"), ""));
  }

  private static String normalize(String value) {
    return value == null ? "" : value.trim();
  }
}
