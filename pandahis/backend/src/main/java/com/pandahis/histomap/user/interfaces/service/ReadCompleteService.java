package com.pandahis.histomap.user.interfaces.service;

import com.pandahis.histomap.common.util.HistoryYearFormat;
import com.pandahis.histomap.contentgraph.domain.BoxCategorySupport;
import com.pandahis.histomap.user.interfaces.dto.ReadCompleteListDTO;
import java.time.OffsetDateTime;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

@Service
public class ReadCompleteService {
  private final JdbcTemplate jdbcTemplate;

  public ReadCompleteService(JdbcTemplate jdbcTemplate) {
    this.jdbcTemplate = jdbcTemplate;
  }

  public void markComplete(long userId, String boxId) {
    jdbcTemplate.update(
        "INSERT INTO user_box_read_completion(user_id, box_id, completed_at) VALUES (?,?,CURRENT_TIMESTAMP) "
            + "ON DUPLICATE KEY UPDATE completed_at=CURRENT_TIMESTAMP",
        userId,
        boxId
    );
  }

  public void unmarkComplete(long userId, String boxId) {
    jdbcTemplate.update(
        "DELETE FROM user_box_read_completion WHERE user_id=? AND box_id=?",
        userId,
        boxId
    );
  }

  public boolean isComplete(long userId, String boxId) {
    Integer n = jdbcTemplate.queryForObject(
        "SELECT COUNT(1) FROM user_box_read_completion WHERE user_id=? AND box_id=?",
        Integer.class,
        userId,
        boxId
    );
    return n != null && n > 0;
  }

  public long countByUser(long userId) {
    Long n = jdbcTemplate.queryForObject(
        "SELECT COUNT(1) FROM user_box_read_completion WHERE user_id=?",
        Long.class,
        userId
    );
    return n == null ? 0 : n;
  }

  public Set<String> completedBoxIdsForDynasty(long userId, String dynastyId) {
    List<String> ids = jdbcTemplate.query(
        "SELECT r.box_id FROM user_box_read_completion r "
            + "JOIN historical_box b ON b.id=r.box_id "
            + "WHERE r.user_id=? AND b.dynasty_id=?",
        (rs, rowNum) -> rs.getString("box_id"),
        userId,
        dynastyId
    );
    return new HashSet<>(ids);
  }

  public ReadCompleteListDTO list(long userId, int page, int pageSize) {
    long total = countByUser(userId);
    int offset = (page - 1) * pageSize;
    List<ReadCompleteListDTO.Item> items = jdbcTemplate.query(
        "SELECT r.box_id, r.completed_at, b.title, b.category_key, b.start_year, b.end_year, "
            + "u.name AS unit_name, u.dynasty_name, c.display_name AS civ_name "
            + "FROM user_box_read_completion r "
            + "JOIN historical_box b ON b.id=r.box_id "
            + "LEFT JOIN historical_emperor u ON u.id=b.emperor_id "
            + "JOIN civilization_l1 c ON c.id=u.civilization_l1_id "
            + "WHERE r.user_id=? "
            + "ORDER BY r.completed_at DESC "
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
          String subText = HistoryYearFormat.label(startYear) + " · " + (civName == null ? "" : civName)
              + " · " + categoryName(categoryKey);
          String pathLabel = pathLabel(civName, dynastyName, unitName, categoryKey);
          OffsetDateTime at = rs.getObject("completed_at", OffsetDateTime.class);
          String iso = at == null ? null : at.toString();
          return new ReadCompleteListDTO.Item(
              boxId, title, subText, categoryKey, iso, startYear, endYear, pathLabel);
        },
        userId,
        pageSize,
        offset
    );
    return new ReadCompleteListDTO(page, pageSize, total, items);
  }

  private static String categoryName(String key) {
    return BoxCategorySupport.displayName(key);
  }

  private static String pathLabel(String civName, String dynastyName, String unitName, String categoryKey) {
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
