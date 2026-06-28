package com.pandahis.histomap.contentgraph.interfaces.service;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

/**
 * 首页/帝王页卡片图：优先 historical_emperor.card_image_url，
 * 为空时回退到该单元下 box_relic 的代表图（君纪盒子优先）。
 */
@Service
public class UnitCardImageResolver {
  private final JdbcTemplate jdbcTemplate;

  public UnitCardImageResolver(JdbcTemplate jdbcTemplate) {
    this.jdbcTemplate = jdbcTemplate;
  }

  /** 单单元详情页：仅查该单元的文物回退图 */
  public String resolveForUnit(String unitId, String unitCardImageUrl) {
    String direct = trimOrNull(unitCardImageUrl);
    if (isUsableImageUrl(direct)) {
      return direct;
    }
    if (unitId == null || unitId.isBlank()) {
      return "";
    }
    List<String> urls = jdbcTemplate.query(
        "SELECT br.image_url FROM box_relic br "
            + "INNER JOIN historical_box b ON b.id = br.box_id AND b.status = 1 "
            + "WHERE b.emperor_id = ? AND br.image_url IS NOT NULL AND TRIM(br.image_url) <> '' "
            + "AND br.image_url NOT LIKE '%待查%' "
            + "ORDER BY CASE WHEN b.category_key = 'junji' THEN 0 ELSE 1 END ASC, "
            + "COALESCE(b.importance_level, 0) DESC, br.sort_order ASC LIMIT 1",
        (rs, i) -> rs.getString(1),
        unitId
    );
    if (urls.isEmpty()) {
      return "";
    }
    String url = trimOrNull(urls.get(0));
    return url == null ? "" : url;
  }

  public String resolve(String unitId, String unitCardImageUrl, Map<String, String> relicFallbackByUnit) {
    String direct = trimOrNull(unitCardImageUrl);
    if (isUsableImageUrl(direct)) {
      return direct;
    }
    if (unitId == null || relicFallbackByUnit == null) {
      return "";
    }
    return trimOrNull(relicFallbackByUnit.get(unitId));
  }

  /** 每个 emperor_id 取一张代表性文物图（已按君纪/重要性排序，每帝王仅保留第一条） */
  public Map<String, String> loadRelicFallbackByUnit() {
    List<Map<String, Object>> rows = jdbcTemplate.queryForList(
        "SELECT b.emperor_id AS emperor_id, br.image_url AS image_url "
            + "FROM box_relic br "
            + "INNER JOIN historical_box b ON b.id = br.box_id AND b.status = 1 "
            + "WHERE b.emperor_id IS NOT NULL AND TRIM(b.emperor_id) <> '' "
            + "AND br.image_url IS NOT NULL AND TRIM(br.image_url) <> '' "
            + "AND br.image_url NOT LIKE '%待查%' "
            + "ORDER BY b.emperor_id ASC, "
            + "CASE WHEN b.category_key = 'junji' THEN 0 ELSE 1 END ASC, "
            + "COALESCE(b.importance_level, 0) DESC, br.sort_order ASC"
    );
    Map<String, String> out = new HashMap<>();
    for (Map<String, Object> r : rows) {
      String unitId = (String) r.get("emperor_id");
      if (unitId == null || out.containsKey(unitId)) {
        continue;
      }
      String url = trimOrNull((String) r.get("image_url"));
      if (isUsableImageUrl(url)) {
        out.put(unitId, url);
      }
    }
    return out;
  }

  static boolean isUsableImageUrl(String url) {
    if (url == null) {
      return false;
    }
    String t = url.trim();
    if (t.isEmpty()) {
      return false;
    }
    if (t.contains("待查")) {
      return false;
    }
    return t.startsWith("http://") || t.startsWith("https://");
  }

  static String trimOrNull(String s) {
    if (s == null) {
      return null;
    }
    String t = s.trim();
    return t.isEmpty() ? null : t;
  }
}
