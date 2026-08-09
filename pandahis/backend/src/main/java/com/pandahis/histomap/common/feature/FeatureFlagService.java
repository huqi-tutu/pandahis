package com.pandahis.histomap.common.feature;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.dao.DataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

/**
 * 线上功能开关。
 *
 * <p>文明切换（高 → 低）：
 * <ol>
 *   <li>MySQL {@code app_kv.feature_civ_switch_enabled}</li>
 *   <li>{@code histomap.features.civ-switch-enabled}（各 profile 默认 false）</li>
 * </ol>
 */
@Service
public class FeatureFlagService {
  static final String KV_CIV_SWITCH = "feature_civ_switch_enabled";
  /** 开关关闭时，搜索与内容门禁使用的默认文明 CODE */
  public static final String DEFAULT_CIVILIZATION_CODE = "HX";

  private final JdbcTemplate jdbcTemplate;
  private final boolean civSwitchEnabledDefault;

  public FeatureFlagService(
      JdbcTemplate jdbcTemplate,
      @Value("${histomap.features.civ-switch-enabled:false}") boolean civSwitchEnabledDefault) {
    this.jdbcTemplate = jdbcTemplate;
    this.civSwitchEnabledDefault = civSwitchEnabledDefault;
  }

  /** 是否允许用户切换一级文明（首页 Tab / 浮层 / 详情并发 Tab） */
  public boolean isCivSwitchEnabled() {
    Boolean kv = readBooleanKv(KV_CIV_SWITCH);
    if (kv != null) {
      return kv;
    }
    return civSwitchEnabledDefault;
  }

  private Boolean readBooleanKv(String key) {
    try {
      var rows = jdbcTemplate.query(
          "SELECT v FROM app_kv WHERE k=?",
          (rs, i) -> rs.getString(1),
          key
      );
      if (rows.isEmpty()) {
        return null;
      }
      String raw = rows.get(0);
      if (raw == null || raw.isBlank()) {
        return null;
      }
      String v = raw.trim();
      if ("1".equals(v) || "true".equalsIgnoreCase(v) || "yes".equalsIgnoreCase(v)) {
        return true;
      }
      if ("0".equals(v) || "false".equalsIgnoreCase(v) || "no".equalsIgnoreCase(v)) {
        return false;
      }
      return null;
    } catch (DataAccessException e) {
      return null;
    }
  }
}
