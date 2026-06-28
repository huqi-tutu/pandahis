package com.pandahis.histomap.user.interfaces.service;

import com.pandahis.histomap.user.interfaces.dto.FootprintListDTO;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.time.OffsetDateTime;
import java.util.List;

@Service
public class FootprintService {
  private final JdbcTemplate jdbcTemplate;

  public FootprintService(JdbcTemplate jdbcTemplate) {
    this.jdbcTemplate = jdbcTemplate;
  }

  public void view(Long userId, String boxId) {
    jdbcTemplate.update(
        "INSERT INTO user_footprint(user_id, box_id, last_viewed_at, view_count) VALUES (?,?,CURRENT_TIMESTAMP,1) " +
            "ON DUPLICATE KEY UPDATE last_viewed_at=CURRENT_TIMESTAMP, view_count=view_count+1",
        userId, boxId
    );
  }

  public FootprintListDTO list(Long userId, int page, int pageSize) {
    long total = jdbcTemplate.queryForObject("SELECT COUNT(1) FROM user_footprint WHERE user_id=?", Long.class, userId);
    int offset = (page - 1) * pageSize;
    List<FootprintListDTO.Item> items = jdbcTemplate.query(
        "SELECT f.box_id, f.last_viewed_at, f.view_count, b.title, b.category_key, b.start_year, b.end_year, "
            + "u.name AS unit_name, u.dynasty_name, c.display_name AS civ_name "
            + "FROM user_footprint f "
            + "JOIN historical_box b ON b.id=f.box_id "
            + "LEFT JOIN historical_emperor u ON u.id=b.emperor_id "
            + "JOIN civilization_l1 c ON c.id=u.civilization_l1_id "
            + "WHERE f.user_id=? "
            + "ORDER BY f.last_viewed_at DESC "
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
          String pathLabel = footprintPathLabel(civName, dynastyName, unitName, categoryKey);
          OffsetDateTime at = rs.getObject("last_viewed_at", OffsetDateTime.class);
          String iso = at == null ? null : at.toString();
          int viewCount = rs.getInt("view_count");
          return new FootprintListDTO.Item(
              boxId, title, subText, categoryKey, iso, viewCount, startYear, endYear, pathLabel);
        },
        userId, pageSize, offset
    );
    return new FootprintListDTO(page, pageSize, total, items);
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
      case "lunzhu" -> "论著";
      default -> key;
    };
  }

  private static String footprintPathLabel(String civName, String dynastyName, String unitName, String categoryKey) {
    String civ = civName == null ? "" : civName.trim();
    String dynasty = dynastyName == null ? "" : dynastyName.trim();
    String unit = unitName == null ? "" : unitName.trim();
    String cat = categoryName(categoryKey);
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
    if (!cat.isEmpty()) {
      if (!sb.isEmpty()) {
        sb.append(" › ");
      }
      sb.append(cat);
    }
    return sb.toString();
  }
}

