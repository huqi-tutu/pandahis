package com.pandahis.histomap.contentgraph.interfaces.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.pandahis.histomap.contentgraph.interfaces.dto.HomeGridDTO;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.dao.DataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.TreeSet;

@Service
public class HomeGridService {
  private static final ObjectMapper OM = new ObjectMapper();

  private final JdbcTemplate jdbcTemplate;
  private final UnitCardImageResolver unitCardImageResolver;
  /** 非空时拼到 civilization tab 图 URL 后，避免微信小程序按 URL 强缓存旧图（换 COS 图后 bump 一次即可） */
  private final String civTabImageCacheBust;

  public HomeGridService(
      JdbcTemplate jdbcTemplate,
      UnitCardImageResolver unitCardImageResolver,
      @Value("${histomap.civ-tab.image-cache-bust:}") String civTabImageCacheBust) {
    this.jdbcTemplate = jdbcTemplate;
    this.unitCardImageResolver = unitCardImageResolver;
    this.civTabImageCacheBust = civTabImageCacheBust == null ? "" : civTabImageCacheBust.trim();
  }

  public HomeGridDTO load() {
    List<HomeGridDTO.Civilization> civilizations = jdbcTemplate.query(
        "SELECT id, display_name, code, color_hex, tab_image_url, sort_order FROM civilization_l1 WHERE status=1 ORDER BY sort_order ASC",
        (rs, rowNum) -> new HomeGridDTO.Civilization(
            rs.getLong("id"),
            rs.getString("display_name"),
            rs.getString("code"),
            rs.getString("color_hex"),
            bustCivTabImageUrl(Optional.ofNullable(rs.getString("tab_image_url")).orElse("")),
            rs.getInt("sort_order")
        )
    );

    List<Map<String, Object>> units = jdbcTemplate.queryForList(
        "SELECT id, name, dynasty_name, era_name, civilization_l1_id, start_year, end_year, duration_years, "
            + "core_topics_json, card_image_url FROM historical_unit WHERE status=1"
    );
    Map<String, String> relicFallbackByUnit = unitCardImageResolver.loadRelicFallbackByUnit();

    List<HomeGridDTO.Cell> cells = new ArrayList<>();
    TreeSet<Integer> yearSet = new TreeSet<>();
    int rowIdx = 0;
    /** 同年同地域同名只保留一条，避免多次导入产生重复「伏羲/黄帝」卡片 */
    LinkedHashMap<String, HomeGridDTO.Cell> cellByYearCivTitle = new LinkedHashMap<>();
    for (Map<String, Object> u : units) {
      String unitId = (String) u.get("id");
      String title = (String) u.get("name");
      int startYear = ((Number) u.get("start_year")).intValue();
      int endYear = ((Number) u.get("end_year")).intValue();
      int duration = ((Number) u.get("duration_years")).intValue();
      Long civId = ((Number) u.get("civilization_l1_id")).longValue();

      String dynasty = trimOrNull((String) u.get("dynasty_name"));
      String era = trimOrNull((String) u.get("era_name"));
      String note = dynasty != null ? dynasty : "";
      String meta = buildMeta(era, duration);
      List<String> highlights = parseHighlights((String) u.get("core_topics_json"));
      String cardImageUrl = unitCardImageResolver.resolve(
          unitId,
          (String) u.get("card_image_url"),
          relicFallbackByUnit
      );
      if (cardImageUrl == null) {
        cardImageUrl = "";
      }
      String variant = (civId + rowIdx) % 2 == 0 ? "light" : "dark";
      String accent = DynastyPalette.resolveAccentHex(dynasty, era);

      String titleKey = title == null ? "" : title.trim();
      String dedupeKey = startYear + "\t" + civId + "\t" + titleKey;
      if (cellByYearCivTitle.containsKey(dedupeKey)) {
        continue;
      }
      rowIdx++;

      HomeGridDTO.UnitCard card = new HomeGridDTO.UnitCard(
          unitId,
          title,
          note,
          meta,
          startYear,
          endYear,
          duration,
          variant,
          highlights,
          cardImageUrl,
          accent
      );
      HomeGridDTO.Cell cell = new HomeGridDTO.Cell(startYear, civId, card);
      cellByYearCivTitle.put(dedupeKey, cell);
    }
    cells.addAll(cellByYearCivTitle.values());
    for (HomeGridDTO.Cell c : cells) {
      yearSet.add(c.timeYear());
    }

    Map<Integer, Integer> rowHeightByYear = new HashMap<>();
    Map<Integer, List<HomeGridDTO.Cell>> byYear = new HashMap<>();
    for (HomeGridDTO.Cell c : cells) {
      byYear.computeIfAbsent(c.timeYear(), k -> new ArrayList<>()).add(c);
    }
    for (Map.Entry<Integer, List<HomeGridDTO.Cell>> e : byYear.entrySet()) {
      int max = 72;
      for (HomeGridDTO.Cell c : e.getValue()) {
        max = Math.max(max, cardMinHeightRpx(c.unitCard()));
      }
      rowHeightByYear.put(e.getKey(), Math.min(max, 280));
    }

    List<HomeGridDTO.TimeAxisItem> timeAxis = yearSet.isEmpty()
        ? List.of(new HomeGridDTO.TimeAxisItem(-221, "前221", 72))
        : yearSet.stream()
            .map(y -> new HomeGridDTO.TimeAxisItem(y, yearLabel(y), rowHeightByYear.getOrDefault(y, 72)))
            .toList();

    HomeGridDTO.Overview overview = loadOverview();

    return new HomeGridDTO(timeAxis, civilizations, cells, overview);
  }

  private static int cardMinHeightRpx(HomeGridDTO.UnitCard card) {
    int h = 72;
    if (card.cardImageUrl() != null && !card.cardImageUrl().isBlank()) {
      h += 88;
    }
    int n = Math.min(5, card.highlights() == null ? 0 : card.highlights().size());
    h += n * 28;
    if (card.note() != null && !card.note().isBlank()) {
      h += 22;
    }
    if (card.meta() != null && !card.meta().isBlank()) {
      h += 22;
    }
    h += 36;
    return h;
  }

  private static String buildMeta(String era, int durationYears) {
    String reign = "在位 " + durationYears + " 年";
    if (era != null && !era.isBlank()) {
      return era + " · " + reign;
    }
    return reign;
  }

  private String bustCivTabImageUrl(String url) {
    if (url == null || url.isBlank()) {
      return "";
    }
    if (civTabImageCacheBust.isEmpty()) {
      return url.trim();
    }
    String u = url.trim();
    char sep = u.contains("?") ? '&' : '?';
    return u + sep + "v=" + civTabImageCacheBust;
  }

  private static String trimOrNull(String s) {
    if (s == null) {
      return null;
    }
    String t = s.trim();
    return t.isEmpty() ? null : t;
  }

  private static List<String> parseHighlights(String json) {
    if (json == null || json.isBlank()) {
      return List.of();
    }
    try {
      JsonNode n = OM.readTree(json);
      if (!n.isArray()) {
        return List.of();
      }
      List<String> out = new ArrayList<>();
      LinkedHashSet<String> seen = new LinkedHashSet<>();
      for (JsonNode x : n) {
        if (x.isTextual()) {
          String t = x.asText().trim();
          if (!t.isEmpty() && seen.add(t)) {
            out.add(t);
          }
        }
        if (out.size() >= 5) {
          break;
        }
      }
      return List.copyOf(out);
    } catch (Exception e) {
      return List.of();
    }
  }

  private HomeGridDTO.Overview loadOverview() {
    try {
      String mapUrl = queryKv("overview_map_image_url");
      String hotJson = queryKv("overview_hotspots_json");
      List<HomeGridDTO.Hotspot> spots = parseHotspots(hotJson);
      return new HomeGridDTO.Overview(mapUrl == null ? "" : mapUrl, spots);
    } catch (DataAccessException e) {
      return new HomeGridDTO.Overview("", List.of());
    }
  }

  private String queryKv(String k) {
    List<String> rows = jdbcTemplate.query(
        "SELECT v FROM app_kv WHERE k=?",
        (rs, i) -> rs.getString(1),
        k
    );
    return rows.isEmpty() ? null : rows.get(0);
  }

  private static List<HomeGridDTO.Hotspot> parseHotspots(String json) {
    if (json == null || json.isBlank()) {
      return List.of();
    }
    try {
      JsonNode arr = OM.readTree(json);
      if (!arr.isArray()) {
        return List.of();
      }
      List<HomeGridDTO.Hotspot> out = new ArrayList<>();
      for (JsonNode o : arr) {
        if (!o.isObject()) {
          continue;
        }
        String unitId = text(o, "unitId");
        if (unitId == null || unitId.isBlank()) {
          continue;
        }
        double left = num(o, "left");
        double top = num(o, "top");
        double w = num(o, "width");
        double h = num(o, "height");
        out.add(new HomeGridDTO.Hotspot(unitId, left, top, w, h));
      }
      return List.copyOf(out);
    } catch (Exception e) {
      return List.of();
    }
  }

  private static String text(JsonNode o, String field) {
    JsonNode n = o.get(field);
    return n == null || !n.isTextual() ? null : n.asText();
  }

  private static double num(JsonNode o, String field) {
    JsonNode n = o.get(field);
    if (n == null || !n.isNumber()) {
      return 0;
    }
    return n.asDouble();
  }

  private static String yearLabel(int year) {
    return year < 0 ? ("前" + Math.abs(year)) : String.valueOf(year);
  }
}
