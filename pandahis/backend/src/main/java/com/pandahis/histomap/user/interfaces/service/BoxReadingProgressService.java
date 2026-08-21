package com.pandahis.histomap.user.interfaces.service;

import com.pandahis.histomap.common.api.ApiException;
import com.pandahis.histomap.common.jdbc.JdbcDates;
import com.pandahis.histomap.user.interfaces.dto.BoxReadingProgressDTO;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class BoxReadingProgressService {
  /** 过浅或过深不落库，下次从头读更合理 */
  public static final int MIN_RESTORABLE_PCT = 5;
  public static final int MAX_RESTORABLE_PCT = 95;
  private static final int MAX_SCROLL_TOP_PX = 2_000_000;

  private final JdbcTemplate jdbcTemplate;

  public BoxReadingProgressService(JdbcTemplate jdbcTemplate) {
    this.jdbcTemplate = jdbcTemplate;
  }

  public BoxReadingProgressDTO load(long userId, String boxId) {
    String id = normalizeBoxId(boxId);
    List<Map<String, Object>> rows = jdbcTemplate.queryForList(
        "SELECT box_id, progress_pct, scroll_top_px, updated_at FROM user_box_reading_progress "
            + "WHERE user_id=? AND box_id=?",
        userId,
        id
    );
    if (rows.isEmpty()) {
      return empty(id);
    }
    Map<String, Object> row = rows.get(0);
    Integer pct = toInteger(row.get("progress_pct"));
    if (!isRestorable(pct)) {
      return empty(id);
    }
    OffsetDateTime updatedAt = JdbcDates.toOffsetDateTime(row.get("updated_at"));
    return new BoxReadingProgressDTO(
        id,
        pct,
        normalizeScrollTop(toInteger(row.get("scroll_top_px"))),
        updatedAt == null ? null : updatedAt.toString()
    );
  }

  @Transactional
  public BoxReadingProgressDTO save(long userId, String boxId, Integer progressPct, Integer scrollTopPx) {
    String id = normalizeBoxId(boxId);
    Integer pct = normalizeProgressPct(progressPct);
    Integer scrollTop = normalizeScrollTop(scrollTopPx);
    if (!isRestorable(pct)) {
      jdbcTemplate.update(
          "DELETE FROM user_box_reading_progress WHERE user_id=? AND box_id=?",
          userId,
          id
      );
      return empty(id);
    }
    jdbcTemplate.update(
        "INSERT INTO user_box_reading_progress(user_id, box_id, progress_pct, scroll_top_px) "
            + "VALUES (?,?,?,?) "
            + "ON DUPLICATE KEY UPDATE progress_pct=VALUES(progress_pct), "
            + "scroll_top_px=VALUES(scroll_top_px), "
            + "updated_at=CURRENT_TIMESTAMP",
        userId,
        id,
        pct,
        scrollTop
    );
    return load(userId, id);
  }

  private static BoxReadingProgressDTO empty(String boxId) {
    return new BoxReadingProgressDTO(boxId, null, null, null);
  }

  static boolean isRestorable(Integer pct) {
    return pct != null && pct >= MIN_RESTORABLE_PCT && pct <= MAX_RESTORABLE_PCT;
  }

  private static Integer normalizeProgressPct(Integer raw) {
    if (raw == null) {
      return null;
    }
    if (raw < 0 || raw > 100) {
      throw ApiException.invalidArgument("阅读进度百分比须在 0–100 之间");
    }
    return raw;
  }

  private static Integer normalizeScrollTop(Integer raw) {
    if (raw == null) {
      return null;
    }
    if (raw < 0 || raw > MAX_SCROLL_TOP_PX) {
      throw ApiException.invalidArgument("阅读滚动位置超出范围");
    }
    return raw;
  }

  private static String normalizeBoxId(String raw) {
    if (raw == null) {
      throw ApiException.invalidArgument("史略 ID 不能为空");
    }
    String id = raw.trim();
    if (id.isEmpty()) {
      throw ApiException.invalidArgument("史略 ID 不能为空");
    }
    if (id.length() > 128) {
      throw ApiException.invalidArgument("史略 ID 长度不能超过 128 个字符");
    }
    return id;
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
}
