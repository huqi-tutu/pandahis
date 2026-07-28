package com.pandahis.histomap.user.interfaces.service;

import com.pandahis.histomap.common.api.ApiException;
import com.pandahis.histomap.common.util.HistoryYearFormat;
import com.pandahis.histomap.contentgraph.domain.BoxCategorySupport;
import com.pandahis.histomap.contentgraph.interfaces.service.UnitDynastyResolver;
import com.pandahis.histomap.user.interfaces.dto.FavoriteListDTO;
import com.pandahis.histomap.user.interfaces.dto.UnitFavoriteListDTO;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.time.OffsetDateTime;
import java.util.List;

@Service
public class FavoriteService {
  private final JdbcTemplate jdbcTemplate;
  private final UnitDynastyResolver dynastyResolver;

  public FavoriteService(JdbcTemplate jdbcTemplate, UnitDynastyResolver dynastyResolver) {
    this.jdbcTemplate = jdbcTemplate;
    this.dynastyResolver = dynastyResolver;
  }

  public void favoriteBox(Long userId, String boxId) {
    ensureBoxExists(boxId);
    jdbcTemplate.update(
        "INSERT INTO user_favorite_box(user_id, box_id) VALUES (?, ?) ON DUPLICATE KEY UPDATE box_id=box_id",
        userId, boxId
    );
  }

  public void unfavoriteBox(Long userId, String boxId) {
    jdbcTemplate.update("DELETE FROM user_favorite_box WHERE user_id=? AND box_id=?", userId, boxId);
  }

  public void favoriteUnit(Long userId, String unitId) {
    String dynastyId = resolveDynastyId(unitId);
    jdbcTemplate.update(
        "INSERT INTO user_favorite_unit(user_id, unit_id) VALUES (?, ?) ON DUPLICATE KEY UPDATE unit_id=unit_id",
        userId, dynastyId
    );
  }

  public void unfavoriteUnit(Long userId, String unitId) {
    String dynastyId = resolveDynastyId(unitId);
    jdbcTemplate.update("DELETE FROM user_favorite_unit WHERE user_id=? AND unit_id=?", userId, dynastyId);
  }

  public long countAllFavorites(Long userId) {
    long boxCount = countBoxFavorites(userId);
    long unitCount = countUnitFavorites(userId);
    return boxCount + unitCount;
  }

  public long countBoxFavorites(Long userId) {
    Long n = jdbcTemplate.queryForObject(
        "SELECT COUNT(1) FROM user_favorite_box WHERE user_id=?",
        Long.class,
        userId
    );
    return n == null ? 0 : n;
  }

  public long countUnitFavorites(Long userId) {
    Long n = jdbcTemplate.queryForObject(
        "SELECT COUNT(1) FROM user_favorite_unit WHERE user_id=?",
        Long.class,
        userId
    );
    return n == null ? 0 : n;
  }

  public FavoriteListDTO listBoxes(Long userId, int page, int pageSize) {
    long total = countBoxFavorites(userId);
    int offset = (page - 1) * pageSize;
    List<FavoriteListDTO.Item> items = jdbcTemplate.query(
        "SELECT f.box_id, f.created_at, b.title, b.category_key, b.start_year, b.end_year, "
            + "u.name AS unit_name, u.dynasty_name, c.display_name AS civ_name "
            + "FROM user_favorite_box f "
            + "JOIN historical_box b ON b.id=f.box_id "
            + "LEFT JOIN historical_emperor u ON u.id=b.emperor_id "
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
          String subText = HistoryYearFormat.label(startYear) + " · " + (civName == null ? "" : civName) + " · " + categoryName(categoryKey);
          String pathLabel = boxPathLabel(categoryKey, civName, dynastyName, unitName);
          OffsetDateTime at = rs.getObject("created_at", OffsetDateTime.class);
          String iso = at == null ? null : at.toString();
          return new FavoriteListDTO.Item(
              boxId, title, subText, categoryKey, iso, startYear, endYear, pathLabel);
        },
        userId, pageSize, offset
    );
    return new FavoriteListDTO(page, pageSize, total, items);
  }

  public UnitFavoriteListDTO listUnits(Long userId, int page, int pageSize) {
    long total = countUnitFavorites(userId);
    int offset = (page - 1) * pageSize;
    List<UnitFavoriteListDTO.Item> items = jdbcTemplate.query(
        "SELECT f.unit_id, f.created_at, d.name, d.start_year, d.end_year, c.display_name AS civ_name "
            + "FROM user_favorite_unit f "
            + "JOIN historical_dynasty d ON d.id=f.unit_id AND d.status=1 "
            + "JOIN civilization_l1 c ON c.id=d.civilization_l1_id "
            + "WHERE f.user_id=? "
            + "ORDER BY f.created_at DESC "
            + "LIMIT ? OFFSET ?",
        (rs, rowNum) -> {
          String unitId = rs.getString("unit_id");
          String title = rs.getString("name");
          int startYear = rs.getInt("start_year");
          int endYear = rs.getInt("end_year");
          String civName = rs.getString("civ_name");
          String subText = HistoryYearFormat.label(startYear) + " – " + HistoryYearFormat.label(endYear);
          String pathLabel = unitPathLabel(civName);
          OffsetDateTime at = rs.getObject("created_at", OffsetDateTime.class);
          String iso = at == null ? null : at.toString();
          return new UnitFavoriteListDTO.Item(
              unitId, title, subText, iso, startYear, endYear, pathLabel);
        },
        userId, pageSize, offset
    );
    return new UnitFavoriteListDTO(page, pageSize, total, items);
  }

  private String resolveDynastyId(String unitId) {
    return dynastyResolver.resolveDynastyId(unitId)
        .orElseThrow(() -> ApiException.notFound("unit not found"));
  }

  private void ensureBoxExists(String boxId) {
    Integer exists = jdbcTemplate.queryForObject(
        "SELECT COUNT(1) FROM historical_box WHERE id=? AND status=1",
        Integer.class,
        boxId
    );
    if (exists == null || exists == 0) {
      throw ApiException.notFound("box not found");
    }
  }


  private static String categoryName(String key) {
    return BoxCategorySupport.displayName(key);
  }

  private static String unitPathLabel(String civName) {
    String civ = civName == null ? "" : civName.trim();
    return civ.isEmpty() ? "" : civ;
  }

  private static String boxPathLabel(String categoryKey, String civName, String dynastyName, String unitName) {
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
