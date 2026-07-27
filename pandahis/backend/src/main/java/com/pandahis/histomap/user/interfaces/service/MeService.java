package com.pandahis.histomap.user.interfaces.service;

import com.pandahis.histomap.common.api.ApiException;
import com.pandahis.histomap.common.jdbc.JdbcDates;
import com.pandahis.histomap.user.interfaces.dto.MeDTO;
import com.pandahis.histomap.user.interfaces.service.ReadCompleteService;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class MeService {
  private static final Logger log = LoggerFactory.getLogger(MeService.class);

  private final JdbcTemplate jdbcTemplate;
  private final ReadCompleteService readCompleteService;

  public MeService(JdbcTemplate jdbcTemplate, ReadCompleteService readCompleteService) {
    this.jdbcTemplate = jdbcTemplate;
    this.readCompleteService = readCompleteService;
  }

  public MeDTO load(Long userId) {
    Map<String, Object> u;
    try {
      u = jdbcTemplate.queryForMap("SELECT nickname,avatar_url,phone_e164 FROM app_user WHERE id=?", userId);
    } catch (EmptyResultDataAccessException e) {
      throw ApiException.unauthorized("login required");
    }
    long fav = safeCount("SELECT COUNT(1) FROM user_favorite_box WHERE user_id=?", userId);
    // 与热力图 daily 表合并口径：索引重建会清空 user_footprint，但 user_reading_daily 仍保留历史。
    long fp = safeCount(
        "SELECT COUNT(DISTINCT box_id) FROM ("
            + "SELECT box_id FROM user_footprint WHERE user_id=? "
            + "UNION "
            + "SELECT box_id FROM user_reading_daily WHERE user_id=?"
            + ") t",
        userId,
        userId
    );
    // 与阅读热力图同源：user_reading_daily 保留每日阅读记录；
    // UNION footprint 末次日期，兼容尚未写入 daily 表的历史数据。
    long learnDaysCount = safeCount(
        "SELECT COUNT(DISTINCT d) FROM ("
            + "SELECT read_date AS d FROM user_reading_daily WHERE user_id=? "
            + "UNION "
            + "SELECT DATE(last_viewed_at) AS d FROM user_footprint WHERE user_id=?"
            + ") t",
        userId,
        userId
    );
    long readCompleteCount;
    try {
      readCompleteCount = readCompleteService.countByUser(userId);
    } catch (Exception ignored) {
      readCompleteCount = 0;
    }

    String phone = (String) u.get("phone_e164");
    String masked = maskPhone(phone);

    var membership = loadMembershipSummary(userId);

    return new MeDTO(
        (String) u.get("nickname"),
        (String) u.get("avatar_url"),
        masked,
        fav,
        fp,
        learnDaysCount,
        readCompleteCount,
        membership.status(),
        membership.endAt()
    );
  }

  @Transactional
  public MeDTO updateNickname(long userId, String nicknameRaw) {
    String nickname = nicknameRaw == null ? "" : nicknameRaw.trim();
    if (nickname.length() < 1 || nickname.length() > 32) {
      throw ApiException.invalidArgument("昵称长度为 1–32 个字符");
    }
    jdbcTemplate.update("UPDATE app_user SET nickname=? WHERE id=?", nickname, userId);
    return load(userId);
  }

  @Transactional
  public MeDTO updateAvatarUrl(long userId, String avatarUrlRaw) {
    String avatarUrl = avatarUrlRaw == null ? "" : avatarUrlRaw.trim();
    if (avatarUrl.isBlank() || avatarUrl.length() > 512) {
      throw ApiException.invalidArgument("头像地址无效");
    }
    if (!(avatarUrl.startsWith("https://") || avatarUrl.startsWith("http://"))) {
      throw ApiException.invalidArgument("头像地址无效");
    }
    jdbcTemplate.update("UPDATE app_user SET avatar_url=? WHERE id=?", avatarUrl, userId);
    return load(userId);
  }

  public String currentAvatarUrl(long userId) {
    try {
      return jdbcTemplate.queryForObject(
          "SELECT avatar_url FROM app_user WHERE id=?",
          String.class,
          userId
      );
    } catch (Exception e) {
      return null;
    }
  }

  private record MembershipSummary(String status, String endAt) {}

  private MembershipSummary loadMembershipSummary(long userId) {
    List<Map<String, Object>> rows =
        jdbcTemplate.queryForList("SELECT end_at, status FROM membership WHERE user_id=?", userId);
    if (rows.isEmpty()) {
      return new MembershipSummary("NONE", null);
    }
    OffsetDateTime endAt = JdbcDates.toOffsetDateTime(rows.get(0).get("end_at"));
    if (endAt != null && endAt.isBefore(OffsetDateTime.now())) {
      return new MembershipSummary("EXPIRED", endAt.toString());
    }
    return new MembershipSummary("ACTIVE", endAt == null ? null : endAt.toString());
  }

  private long safeCount(String sql, Object... args) {
    try {
      Long n = jdbcTemplate.queryForObject(sql, Long.class, args);
      return n == null ? 0 : n;
    } catch (Exception e) {
      log.warn("MeService count failed: {}", sql, e);
      return 0;
    }
  }

  private String maskPhone(String phoneE164) {
    if (phoneE164 == null || phoneE164.isBlank()) return "";
    String p = phoneE164;
    if (p.startsWith("+86")) p = p.substring(3);
    if (p.length() == 11) {
      return p.substring(0, 3) + " **** " + p.substring(7);
    }
    return phoneE164;
  }
}

