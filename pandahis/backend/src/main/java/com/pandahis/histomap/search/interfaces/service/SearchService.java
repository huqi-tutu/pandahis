package com.pandahis.histomap.search.interfaces.service;

import com.pandahis.histomap.search.interfaces.dto.SearchResultDTO;
import com.pandahis.histomap.search.interfaces.dto.SearchSuggestDTO;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

@Service
public class SearchService {
  private final JdbcTemplate jdbcTemplate;

  public SearchService(JdbcTemplate jdbcTemplate) {
    this.jdbcTemplate = jdbcTemplate;
  }

  public SearchSuggestDTO suggest(Long userId) {
    List<SearchSuggestDTO.HotKeyword> hot = jdbcTemplate.query(
        "SELECT keyword,is_hot FROM search_hot_keyword WHERE status=1 ORDER BY sort_order ASC LIMIT 50",
        (rs, rowNum) -> new SearchSuggestDTO.HotKeyword(rs.getString("keyword"), rs.getInt("is_hot") == 1)
    );

    List<SearchSuggestDTO.HistoryKeyword> history = new ArrayList<>();
    if (userId != null) {
      history = jdbcTemplate.query(
          "SELECT keyword,last_searched_at FROM user_search_history WHERE user_id=? ORDER BY last_searched_at DESC LIMIT 20",
          (rs, rowNum) -> {
            OffsetDateTime at = rs.getObject("last_searched_at", OffsetDateTime.class);
            return new SearchSuggestDTO.HistoryKeyword(rs.getString("keyword"), at == null ? null : at.toString());
          },
          userId
      );
    }

    return new SearchSuggestDTO(hot, history);
  }

  public SearchResultDTO search(Long userId, String q, int page, int pageSize) {
    String keyword = q.trim();
    if (keyword.isEmpty()) {
      return new SearchResultDTO(0, page, pageSize, List.of());
    }

    if (userId != null) {
      jdbcTemplate.update(
          "INSERT INTO user_search_history(user_id, keyword, last_searched_at, search_count) VALUES (?,?,CURRENT_TIMESTAMP,1) " +
              "ON DUPLICATE KEY UPDATE last_searched_at=CURRENT_TIMESTAMP, search_count=search_count+1",
          userId, keyword
      );
    }

    String like = "%" + escapeLike(keyword) + "%";

    // boxes
    List<Map<String, Object>> boxRows = jdbcTemplate.queryForList(
        "SELECT b.id,b.title,b.category_key,b.start_year,b.parent_entry_id,b.blurb,u.name AS unit_name,u.ruler_name,u.civilization_l1_id "
            + "FROM historical_box b LEFT JOIN historical_emperor u ON u.id=b.emperor_id "
            + "WHERE b.status=1 AND (b.id LIKE ? ESCAPE '\\\\' OR b.title LIKE ? ESCAPE '\\\\' OR b.parent_entry_id LIKE ? ESCAPE '\\\\' OR b.blurb LIKE ? ESCAPE '\\\\') "
            + "ORDER BY b.importance_level DESC, b.start_year ASC LIMIT 100",
        like, like, like
    );

    // units
    List<Map<String, Object>> unitRows = jdbcTemplate.queryForList(
        "SELECT id,name,ruler_name,civilization_l1_id,enthronement_year FROM historical_emperor "
            + "WHERE status=1 AND (name LIKE ? ESCAPE '\\\\' OR ruler_name LIKE ? ESCAPE '\\\\' OR dynasty_name LIKE ? ESCAPE '\\\\' OR era_name LIKE ? ESCAPE '\\\\' OR tags LIKE ? ESCAPE '\\\\') "
            + "ORDER BY enthronement_year ASC LIMIT 100",
        like, like, like, like, like
    );

    List<SearchResultDTO.Item> items = new ArrayList<>();
    for (Map<String, Object> r : boxRows) {
      String id = (String) r.get("id");
      String title = (String) r.get("title");
      String unitName = (String) r.get("unit_name");
      if (unitName == null) unitName = "";
      String cat = (String) r.get("category_key");
      Object civObj = r.get("civilization_l1_id");
      String civName = "";
      if (civObj != null) {
        long civId = ((Number) civObj).longValue();
        civName = jdbcTemplate.queryForObject("SELECT display_name FROM civilization_l1 WHERE id=?", String.class, civId);
      }
      if (civName == null) civName = "";
      String pathText = civName.isEmpty() ? (unitName + " › " + categoryName(cat)) : (civName + " › " + unitName + " › " + categoryName(cat));
      String blurb = r.get("blurb") != null ? String.valueOf(r.get("blurb")) : "";
      items.add(new SearchResultDTO.Item(
          "box",
          id,
          pathText,
          highlight(title, keyword),
          highlight(truncate(blurb, 160), keyword)
      ));
    }

    for (Map<String, Object> r : unitRows) {
      String id = (String) r.get("id");
      String name = (String) r.get("name");
      long civId = ((Number) r.get("civilization_l1_id")).longValue();
      String civName = jdbcTemplate.queryForObject("SELECT display_name FROM civilization_l1 WHERE id=?", String.class, civId);
      String pathText = (civName == null ? "" : civName) + " › " + name;
      String ruler = r.get("ruler_name") != null ? String.valueOf(r.get("ruler_name")) : "";
      items.add(new SearchResultDTO.Item(
          "unit",
          id,
          pathText,
          highlight(name, keyword),
          highlight(truncate(ruler, 160), keyword)
      ));
    }

    long total = items.size();
    int from = Math.min((page - 1) * pageSize, items.size());
    int to = Math.min(from + pageSize, items.size());
    List<SearchResultDTO.Item> paged = items.subList(from, to);
    return new SearchResultDTO(total, page, pageSize, paged);
  }

  public void deleteHistory(Long userId, String keyword) {
    jdbcTemplate.update("DELETE FROM user_search_history WHERE user_id=? AND keyword=?", userId, keyword.trim());
  }

  private static String categoryName(String key) {
    return switch (key) {
      case "junji" -> "君纪";
      case "shichen" -> "士臣";
      case "minlu" -> "民录";
      case "dianzhi" -> "典制";
      case "shilue" -> "事略";
      case "lunzhu" -> "论著";
      default -> key;
    };
  }

  private static String escapeLike(String s) {
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_");
  }

  private static String escapeHtml(String s) {
    return s
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\"", "&quot;")
        .replace("'", "&#39;");
  }

  private static String truncate(String text, int maxLen) {
    if (text == null) return "";
    String s = text.trim();
    if (s.length() <= maxLen) return s;
    return s.substring(0, maxLen) + "…";
  }

  private static String highlight(String text, String keyword) {
    if (text == null) text = "";
    String safe = escapeHtml(text);
    String safeKeyword = escapeHtml(keyword);
    return safe.replace(safeKeyword, "<em>" + safeKeyword + "</em>");
  }
}

