package com.pandahis.histomap.user.interfaces.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.pandahis.histomap.common.api.ApiException;
import com.pandahis.histomap.common.jdbc.JdbcDates;
import com.pandahis.histomap.user.interfaces.dto.HomeMatrixStateDTO;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class HomeMatrixStateService {
  private static final ObjectMapper OM = new ObjectMapper();
  private static final String DEFAULT_CIVILIZATION_CODE = "HX";
  private static final int MAX_DYNASTY_KEYS = 128;
  private static final int MAX_SCROLL_TOP_PX = 2_000_000;

  private final JdbcTemplate jdbcTemplate;

  public HomeMatrixStateService(JdbcTemplate jdbcTemplate) {
    this.jdbcTemplate = jdbcTemplate;
  }

  public HomeMatrixStateDTO load(long userId) {
    List<Map<String, Object>> rows = jdbcTemplate.queryForList(
        "SELECT civilization_code, last_dynasty_key, collapsed_dynasty_keys_json, "
            + "last_scroll_top_px, updated_at FROM user_home_matrix_state WHERE user_id=?",
        userId
    );
    if (rows.isEmpty()) {
      return defaultState();
    }
    Map<String, Object> row = rows.get(0);
    OffsetDateTime updatedAt = JdbcDates.toOffsetDateTime(row.get("updated_at"));
    return new HomeMatrixStateDTO(
        trimOrDefault((String) row.get("civilization_code"), DEFAULT_CIVILIZATION_CODE),
        trimToNull((String) row.get("last_dynasty_key")),
        parseCollapsedKeys((String) row.get("collapsed_dynasty_keys_json")),
        toInteger(row.get("last_scroll_top_px")),
        updatedAt == null ? null : updatedAt.toString()
    );
  }

  @Transactional
  public HomeMatrixStateDTO save(long userId, SaveHomeMatrixStateCommand command) {
    String civilizationCode = normalizeCode(command.civilizationCode());
    String lastDynastyKey = trimToNull(command.lastDynastyKey());
    List<String> collapsedKeys = normalizeCollapsedKeys(command.collapsedDynastyKeys());
    Integer scrollTop = normalizeScrollTop(command.lastScrollTopPx());
    String collapsedJson = writeCollapsedKeys(collapsedKeys);

    jdbcTemplate.update(
        "INSERT INTO user_home_matrix_state("
            + "user_id, civilization_code, last_dynasty_key, collapsed_dynasty_keys_json, last_scroll_top_px"
            + ") VALUES (?,?,?,?,?) "
            + "ON DUPLICATE KEY UPDATE "
            + "civilization_code=VALUES(civilization_code), "
            + "last_dynasty_key=VALUES(last_dynasty_key), "
            + "collapsed_dynasty_keys_json=VALUES(collapsed_dynasty_keys_json), "
            + "last_scroll_top_px=VALUES(last_scroll_top_px), "
            + "updated_at=CURRENT_TIMESTAMP",
        userId,
        civilizationCode,
        lastDynastyKey,
        collapsedJson,
        scrollTop
    );
    return load(userId);
  }

  private static HomeMatrixStateDTO defaultState() {
    return new HomeMatrixStateDTO(DEFAULT_CIVILIZATION_CODE, null, List.of(), null, null);
  }

  private static List<String> parseCollapsedKeys(String raw) {
    if (raw == null || raw.isBlank()) {
      return List.of();
    }
    try {
      return normalizeCollapsedKeys(OM.readValue(raw, new TypeReference<List<String>>() {}));
    } catch (JsonProcessingException ex) {
      return List.of();
    }
  }

  private static String writeCollapsedKeys(List<String> keys) {
    try {
      return OM.writeValueAsString(keys == null ? List.of() : keys);
    } catch (JsonProcessingException ex) {
      throw ApiException.invalidArgument("朝代折叠状态格式错误");
    }
  }

  private static List<String> normalizeCollapsedKeys(List<String> keys) {
    if (keys == null || keys.isEmpty()) {
      return List.of();
    }
    LinkedHashSet<String> out = new LinkedHashSet<>();
    for (String key : keys) {
      String value = trimToNull(key);
      if (value == null) {
        continue;
      }
      if (value.length() > 64) {
        throw ApiException.invalidArgument("朝代标识长度不能超过 64 个字符");
      }
      out.add(value);
      if (out.size() > MAX_DYNASTY_KEYS) {
        throw ApiException.invalidArgument("朝代折叠状态数量过多");
      }
    }
    return new ArrayList<>(out);
  }

  private static String normalizeCode(String raw) {
    String code = trimOrDefault(raw, DEFAULT_CIVILIZATION_CODE).toUpperCase();
    if (code.length() > 16) {
      throw ApiException.invalidArgument("文明编码长度不能超过 16 个字符");
    }
    return code;
  }

  private static Integer normalizeScrollTop(Integer raw) {
    if (raw == null) {
      return null;
    }
    if (raw < 0 || raw > MAX_SCROLL_TOP_PX) {
      throw ApiException.invalidArgument("首页滚动位置超出范围");
    }
    return raw;
  }

  private static String trimToNull(String raw) {
    if (raw == null) {
      return null;
    }
    String value = raw.trim();
    return value.isEmpty() ? null : value;
  }

  private static String trimOrDefault(String raw, String fallback) {
    String value = trimToNull(raw);
    return value == null ? fallback : value;
  }

  private static Integer toInteger(Object value) {
    if (value == null) {
      return null;
    }
    if (value instanceof Number number) {
      return number.intValue();
    }
    return Integer.parseInt(String.valueOf(value));
  }

  public record SaveHomeMatrixStateCommand(
      String civilizationCode,
      String lastDynastyKey,
      List<String> collapsedDynastyKeys,
      Integer lastScrollTopPx
  ) {}
}
