package com.pandahis.histomap.user.interfaces.service;

import com.pandahis.histomap.common.api.ApiException;
import com.pandahis.histomap.common.jdbc.JdbcDates;
import com.pandahis.histomap.user.interfaces.dto.MeDTO;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class MeService {
  private final JdbcTemplate jdbcTemplate;

  public MeService(JdbcTemplate jdbcTemplate) {
    this.jdbcTemplate = jdbcTemplate;
  }

  public MeDTO load(Long userId) {
    Map<String, Object> u = jdbcTemplate.queryForMap("SELECT nickname,avatar_url,phone_e164 FROM app_user WHERE id=?", userId);
    long fav = jdbcTemplate.queryForObject("SELECT COUNT(1) FROM user_favorite_box WHERE user_id=?", Long.class, userId);
    long fp = jdbcTemplate.queryForObject("SELECT COUNT(1) FROM user_footprint WHERE user_id=?", Long.class, userId);
    Long learnDays = jdbcTemplate.queryForObject(
        "SELECT COUNT(DISTINCT DATE(last_viewed_at)) FROM user_footprint WHERE user_id=?",
        Long.class,
        userId
    );
    long learnDaysCount = learnDays == null ? 0 : learnDays;

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

