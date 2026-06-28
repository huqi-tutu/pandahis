package com.pandahis.histomap.contentgraph.interfaces.service;

import com.pandahis.histomap.common.api.ApiException;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

/** 将帝王/政权/朝代 ID 统一解析为朝代行（historical_dynasty） */
@Service
public class UnitDynastyResolver {
  private final JdbcTemplate jdbcTemplate;

  public UnitDynastyResolver(JdbcTemplate jdbcTemplate) {
    this.jdbcTemplate = jdbcTemplate;
  }

  public Map<String, Object> requireDynastyRow(String unitId) {
    String dynastyId = resolveDynastyId(unitId)
        .orElseThrow(() -> ApiException.notFound("unit not found"));
    return requireDynastyById(dynastyId);
  }

  public Optional<String> resolveDynastyId(String unitId) {
    if (unitId == null || unitId.isBlank()) return Optional.empty();

    List<Map<String, Object>> dynastyRows = jdbcTemplate.queryForList(
        "SELECT id FROM historical_dynasty WHERE id=? AND status=1",
        unitId
    );
    if (!dynastyRows.isEmpty()) {
      return Optional.of(unitId);
    }

    List<Map<String, Object>> emperorRows = jdbcTemplate.queryForList(
        "SELECT dynasty_id FROM historical_emperor WHERE id=? AND status=1",
        unitId
    );
    if (!emperorRows.isEmpty()) {
      Object dynastyId = emperorRows.get(0).get("dynasty_id");
      return dynastyId == null ? Optional.empty() : Optional.of(String.valueOf(dynastyId));
    }

    List<Map<String, Object>> regimeRows = jdbcTemplate.queryForList(
        "SELECT dynasty_id FROM historical_regime WHERE id=? AND status=1",
        unitId
    );
    if (!regimeRows.isEmpty()) {
      Object dynastyId = regimeRows.get(0).get("dynasty_id");
      return dynastyId == null ? Optional.empty() : Optional.of(String.valueOf(dynastyId));
    }

    return Optional.empty();
  }

  public Map<String, Object> requireDynastyById(String dynastyId) {
    List<Map<String, Object>> rows = jdbcTemplate.queryForList(
        "SELECT id, name, civilization_l1_id, civilization_name, civilization_code, "
            + "start_year, end_year, start_year_raw, end_year_raw "
            + "FROM historical_dynasty WHERE id=? AND status=1",
        dynastyId
    );
    if (rows.isEmpty()) {
      throw ApiException.notFound("dynasty not found");
    }
    return rows.get(0);
  }

  public String civilizationName(Map<String, Object> dynastyRow) {
    String civName = Optional.ofNullable((String) dynastyRow.get("civilization_name")).orElse("").trim();
    if (!civName.isEmpty()) return civName;
    Long civId = dynastyRow.get("civilization_l1_id") == null
        ? null
        : ((Number) dynastyRow.get("civilization_l1_id")).longValue();
    if (civId == null) return "";
    String fromDb = jdbcTemplate.queryForObject(
        "SELECT display_name FROM civilization_l1 WHERE id=?",
        String.class,
        civId
    );
    return fromDb == null ? "" : fromDb;
  }

  public int dynastyStartYear(Map<String, Object> dynastyRow) {
    return dynastyRow.get("start_year") == null ? 0 : ((Number) dynastyRow.get("start_year")).intValue();
  }

  public int dynastyEndYear(Map<String, Object> dynastyRow) {
    int start = dynastyStartYear(dynastyRow);
    if (dynastyRow.get("end_year") == null) {
      return start + 1;
    }
    int end = ((Number) dynastyRow.get("end_year")).intValue();
    return end <= start ? start + 1 : end;
  }
}
