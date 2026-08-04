package com.pandahis.histomap.search.interfaces.service;

import com.pandahis.histomap.contentgraph.domain.BoxCategorySupport;
import com.pandahis.histomap.search.interfaces.dto.SearchResultDTO;
import com.pandahis.histomap.search.interfaces.dto.SearchSuggestDTO;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

@Service
public class SearchService {
  private static final int HOT_TOP_N = 10;
  private static final int MATCH_LIMIT = 100;

  private final JdbcTemplate jdbcTemplate;

  public SearchService(JdbcTemplate jdbcTemplate) {
    this.jdbcTemplate = jdbcTemplate;
  }

  public SearchSuggestDTO suggest(Long userId) {
    List<SearchSuggestDTO.HotKeyword> hot = loadHotKeywordsByVolume(HOT_TOP_N);

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

  /**
   * 热门：优先小程序真实搜索量 TOP N；不足时用运营种子词补齐。
   */
  List<SearchSuggestDTO.HotKeyword> loadHotKeywordsByVolume(int limit) {
    List<SearchSuggestDTO.HotKeyword> volume = jdbcTemplate.query(
        "SELECT keyword, SUM(search_count) AS cnt FROM user_search_history "
            + "GROUP BY keyword ORDER BY cnt DESC, MAX(last_searched_at) DESC LIMIT ?",
        (rs, rowNum) -> new SearchSuggestDTO.HotKeyword(rs.getString("keyword"), true),
        limit
    );
    List<SearchSuggestDTO.HotKeyword> out = dedupeHotKeywords(volume, limit);
    if (out.size() >= limit) {
      return out;
    }

    List<SearchSuggestDTO.HotKeyword> seeds = jdbcTemplate.query(
        "SELECT keyword,is_hot FROM search_hot_keyword WHERE status=1 ORDER BY sort_order ASC, id ASC LIMIT 200",
        (rs, rowNum) -> new SearchSuggestDTO.HotKeyword(rs.getString("keyword"), rs.getInt("is_hot") == 1)
    );
    Set<String> seen = new LinkedHashSet<>();
    for (SearchSuggestDTO.HotKeyword item : out) {
      seen.add(item.keyword());
    }
    for (SearchSuggestDTO.HotKeyword seed : dedupeHotKeywords(seeds, 50)) {
      if (seen.contains(seed.keyword())) continue;
      out.add(seed);
      seen.add(seed.keyword());
      if (out.size() >= limit) break;
    }
    return out;
  }

  /** 保留首次出现（sort_order 更靠前），最多 limit 条 */
  static List<SearchSuggestDTO.HotKeyword> dedupeHotKeywords(
      List<SearchSuggestDTO.HotKeyword> raw, int limit
  ) {
    Map<String, SearchSuggestDTO.HotKeyword> uniq = new LinkedHashMap<>();
    for (SearchSuggestDTO.HotKeyword item : raw) {
      if (item == null || item.keyword() == null) continue;
      String key = item.keyword().trim();
      if (key.isEmpty() || uniq.containsKey(key)) continue;
      uniq.put(key, new SearchSuggestDTO.HotKeyword(key, item.isHot()));
      if (uniq.size() >= limit) break;
    }
    return new ArrayList<>(uniq.values());
  }

  public SearchResultDTO search(Long userId, String q, int page, int pageSize) {
    String keyword = q.trim();
    if (keyword.isEmpty()) {
      return new SearchResultDTO(0, page, pageSize, 0, 0, List.of(), List.of(), List.of());
    }

    if (userId != null) {
      jdbcTemplate.update(
          "INSERT INTO user_search_history(user_id, keyword, last_searched_at, search_count) VALUES (?,?,CURRENT_TIMESTAMP,1) " +
              "ON DUPLICATE KEY UPDATE last_searched_at=CURRENT_TIMESTAMP, search_count=search_count+1",
          userId, keyword
      );
    }

    String like = "%" + escapeLike(keyword) + "%";
    int tierLimit = Math.max(1, Math.min(pageSize, MATCH_LIMIT));

    // 精准：史略名称或简介
    List<Map<String, Object>> preciseRows = jdbcTemplate.queryForList(
        "SELECT b.id, b.title, b.category_key, b.blurb, b.start_year, b.end_year, "
            + "b.civilization_name, b.dynasty_name, b.regime_name, b.person_tag, b.importance_level "
            + "FROM historical_box b "
            + "WHERE b.status=1 AND (b.title LIKE ? ESCAPE '\\\\' OR IFNULL(b.blurb,'') LIKE ? ESCAPE '\\\\') "
            + "ORDER BY b.importance_level DESC, b.start_year ASC LIMIT " + MATCH_LIMIT,
        like, like
    );

    Set<String> preciseIds = new LinkedHashSet<>();
    for (Map<String, Object> r : preciseRows) {
      preciseIds.add(String.valueOf(r.get("id")));
    }

    // 相关：详情正文命中，且未进入精准
    List<Map<String, Object>> relatedRows = jdbcTemplate.queryForList(
        "SELECT b.id, b.title, b.category_key, b.blurb, b.start_year, b.end_year, "
            + "b.civilization_name, b.dynasty_name, b.regime_name, b.person_tag, b.importance_level "
            + "FROM historical_box b "
            + "LEFT JOIN historical_box_detail d ON d.box_id = b.id "
            + "WHERE b.status=1 "
            + "AND (IFNULL(d.translate_detail,'') LIKE ? ESCAPE '\\\\' OR IFNULL(b.detail_md,'') LIKE ? ESCAPE '\\\\') "
            + "AND NOT (b.title LIKE ? ESCAPE '\\\\' OR IFNULL(b.blurb,'') LIKE ? ESCAPE '\\\\') "
            + "ORDER BY b.importance_level DESC, b.start_year ASC LIMIT " + MATCH_LIMIT,
        like, like, like, like
    );

    List<SearchResultDTO.Item> preciseAll = mapBoxRows(preciseRows, keyword, "precise");
    List<SearchResultDTO.Item> relatedAll = new ArrayList<>();
    for (SearchResultDTO.Item item : mapBoxRows(relatedRows, keyword, "related")) {
      if (preciseIds.contains(item.id())) continue;
      relatedAll.add(item);
    }

    // 两档各自按 page/pageSize 切片，避免扁平分页把相关档挤掉
    List<SearchResultDTO.Item> preciseItems = slicePage(preciseAll, page, tierLimit);
    List<SearchResultDTO.Item> relatedItems = slicePage(relatedAll, page, tierLimit);

    List<SearchResultDTO.Item> merged = new ArrayList<>(preciseItems.size() + relatedItems.size());
    merged.addAll(preciseItems);
    merged.addAll(relatedItems);

    return new SearchResultDTO(
        preciseAll.size() + relatedAll.size(),
        page,
        pageSize,
        preciseAll.size(),
        relatedAll.size(),
        List.copyOf(preciseItems),
        List.copyOf(relatedItems),
        List.copyOf(merged)
    );
  }

  static <T> List<T> slicePage(List<T> all, int page, int pageSize) {
    if (all == null || all.isEmpty() || pageSize <= 0) return List.of();
    int safePage = Math.max(1, page);
    int from = Math.min((safePage - 1) * pageSize, all.size());
    int to = Math.min(from + pageSize, all.size());
    if (from >= to) return List.of();
    return all.subList(from, to);
  }

  public void deleteHistory(Long userId, String keyword) {
    jdbcTemplate.update("DELETE FROM user_search_history WHERE user_id=? AND keyword=?", userId, keyword.trim());
  }

  private List<SearchResultDTO.Item> mapBoxRows(List<Map<String, Object>> rows, String keyword, String matchTier) {
    List<SearchResultDTO.Item> items = new ArrayList<>(rows.size());
    for (Map<String, Object> r : rows) {
      items.add(toItem(r, keyword, matchTier));
    }
    return items;
  }

  private static SearchResultDTO.Item toItem(Map<String, Object> r, String keyword, String matchTier) {
    String id = String.valueOf(r.get("id"));
    String title = r.get("title") != null ? String.valueOf(r.get("title")) : "";
    String categoryKey = r.get("category_key") != null ? String.valueOf(r.get("category_key")) : "";
    String categoryName = categoryName(categoryKey);
    String civ = trimText(r.get("civilization_name"));
    String dynasty = trimText(r.get("dynasty_name"));
    String regime = trimText(r.get("regime_name"));
    String coordinateText = joinCoordinate(civ, dynasty, regime);
    String pathText = coordinateText.isEmpty()
        ? categoryName
        : (categoryName.isEmpty() ? coordinateText : coordinateText + " › " + categoryName);
    String blurb = r.get("blurb") != null ? String.valueOf(r.get("blurb")) : "";
    Integer startYear = toInt(r.get("start_year"));
    Integer endYear = toInt(r.get("end_year"));
    String personTag = "";
    if (BoxCategorySupport.isPersonCategory(categoryKey)) {
      personTag = trimText(r.get("person_tag"));
    }
    return new SearchResultDTO.Item(
        "box",
        id,
        pathText,
        highlight(title, keyword),
        highlight(truncate(blurb, 160), keyword),
        matchTier,
        categoryKey,
        categoryName,
        coordinateText,
        startYear,
        endYear,
        personTag.isEmpty() ? null : personTag
    );
  }

  static String joinCoordinate(String civ, String dynasty, String regime) {
    List<String> parts = new ArrayList<>(3);
    if (!civ.isEmpty()) parts.add(civ);
    if (!dynasty.isEmpty()) parts.add(dynasty);
    if (!regime.isEmpty()) parts.add(regime);
    return String.join(".", parts);
  }

  private static String categoryName(String key) {
    return BoxCategorySupport.displayName(key);
  }

  private static String trimText(Object raw) {
    if (raw == null) return "";
    return String.valueOf(raw).trim();
  }

  private static Integer toInt(Object raw) {
    if (raw instanceof Number n) return n.intValue();
    if (raw == null) return null;
    try {
      return Integer.parseInt(String.valueOf(raw).trim());
    } catch (NumberFormatException e) {
      return null;
    }
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
