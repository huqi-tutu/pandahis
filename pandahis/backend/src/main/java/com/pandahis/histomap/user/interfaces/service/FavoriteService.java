package com.pandahis.histomap.user.interfaces.service;

import com.pandahis.histomap.user.interfaces.dto.FavoriteListDTO;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.time.OffsetDateTime;
import java.util.List;

@Service
public class FavoriteService {
  private final JdbcTemplate jdbcTemplate;

  public FavoriteService(JdbcTemplate jdbcTemplate) {
    this.jdbcTemplate = jdbcTemplate;
  }

  public void favorite(Long userId, String boxId) {
    jdbcTemplate.update(
        "INSERT INTO user_favorite_box(user_id, box_id) VALUES (?, ?) ON DUPLICATE KEY UPDATE box_id=box_id",
        userId, boxId
    );
  }

  public void unfavorite(Long userId, String boxId) {
    jdbcTemplate.update("DELETE FROM user_favorite_box WHERE user_id=? AND box_id=?", userId, boxId);
  }

  public FavoriteListDTO list(Long userId, int page, int pageSize) {
    long total = jdbcTemplate.queryForObject("SELECT COUNT(1) FROM user_favorite_box WHERE user_id=?", Long.class, userId);
    int offset = (page - 1) * pageSize;
    List<FavoriteListDTO.Item> items = jdbcTemplate.query(
        "SELECT f.box_id, f.created_at, b.title, b.category_key, b.start_year, b.end_year, "
            + "u.name AS unit_name, u.dynasty_name, c.display_name AS civ_name "
            + "FROM user_favorite_box f "
            + "JOIN historical_box b ON b.id=f.box_id "
            + "JOIN historical_unit u ON u.id=b.unit_id "
            + "JOIN civilization_l1 c ON c.id=u.civilization_l1_id "
            + "WHERE f.user_id=? "
            + "ORDER BY f.created_at DESC "
            + "LIMIT ? OFFSET ?",
        (rs, rowNum) -> {
          String boxId = rs.getString("box_id");
          String title = rs.getString("title");
          String categoryKey = rs.getString("category_key");
          int startYear = rs.getInt("start_year");
          int endYear = rs.getInt("end_year");
          String civName = rs.getString("civ_name");
          String unitName = rs.getString("unit_name");
          String dynastyName = rs.getString("dynasty_name");
          String subText = yearLabel(startYear) + " · " + (civName == null ? "" : civName) + " · " + categoryName(categoryKey);
          String pathLabel = pathLabel(categoryKey, civName, dynastyName, unitName);
          OffsetDateTime at = rs.getObject("created_at", OffsetDateTime.class);
          String iso = at == null ? null : at.toString();
          return new FavoriteListDTO.Item(
              boxId, title, subText, categoryKey, iso, startYear, endYear, pathLabel);
        },
        userId, pageSize, offset
    );
    return new FavoriteListDTO(page, pageSize, total, items);
  }

  private static String yearLabel(int year) {
    return year < 0 ? ("前" + Math.abs(year)) : String.valueOf(year);
  }

  private static String categoryName(String key) {
    return switch (key) {
      case "junji" -> "君纪";
      case "shichen" -> "士臣";
      case "minlu" -> "民录";
      case "dianzhi" -> "典制";
      case "shilue" -> "事略";
      default -> key;
    };
  }

  private static String pathLabel(String categoryKey, String civName, String dynastyName, String unitName) {
    String civ = civName == null ? "" : civName.trim();
    if ("junji".equals(categoryKey)) {
      return civ.isEmpty() ? "" : "一级文明归属：" + civ;
    }
    String dynasty = dynastyName == null ? "" : dynastyName.trim();
    String unit = unitName == null ? "" : unitName.trim();
    StringBuilder sb = new StringBuilder();
    if (!civ.isEmpty()) {
      sb.append(civ);
    }
    if (!dynasty.isEmpty() && !dynasty.equals(unit)) {
      if (!sb.isEmpty()) {
        sb.append(" › ");
      }
      sb.append(dynasty);
    }
    if (!unit.isEmpty()) {
      if (!sb.isEmpty()) {
        sb.append(" › ");
      }
      sb.append(unit);
    }
    return sb.toString();
  }
}

