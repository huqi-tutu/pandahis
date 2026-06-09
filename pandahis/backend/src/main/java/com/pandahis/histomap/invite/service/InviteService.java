package com.pandahis.histomap.invite.service;

import com.pandahis.histomap.membership.interfaces.dto.AssistParticipantDTO;
import java.security.SecureRandom;
import java.util.List;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class InviteService {
  public static final int INVITE_REWARD_READS = 10;
  private static final String CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  private static final SecureRandom RNG = new SecureRandom();

  private final JdbcTemplate jdbcTemplate;

  public InviteService(JdbcTemplate jdbcTemplate) {
    this.jdbcTemplate = jdbcTemplate;
  }

  /** 新用户首次注册且带有效邀请码时：写邀请关系并给邀请人加阅读数（幂等）。 */
  @Transactional
  public boolean recordNewUserFromInvite(long inviteeUserId, String inviteCodeRaw) {
    return bindInviteCode(inviteeUserId, inviteCodeRaw).bound();
  }

  /**
   * 已登录用户补填邀请码（仅当被邀请人尚未绑定过邀请关系时生效）。
   */
  @Transactional
  public BindResult bindInviteCode(long inviteeUserId, String inviteCodeRaw) {
    if (inviteCodeRaw == null) {
      return BindResult.fail("请输入邀请码");
    }
    String code = inviteCodeRaw.trim().toUpperCase();
    if (code.isEmpty()) {
      return BindResult.fail("请输入邀请码");
    }
    Long inviter =
        jdbcTemplate.query(
                "SELECT user_id FROM user_invite_code WHERE code=?",
                (rs, i) -> rs.getLong(1),
                code)
            .stream()
            .findFirst()
            .orElse(null);
    if (inviter == null) {
      return BindResult.fail("邀请码无效");
    }
    if (inviter.equals(inviteeUserId)) {
      return BindResult.fail("不能使用自己的邀请码");
    }
    Integer already =
        jdbcTemplate.queryForObject(
            "SELECT COUNT(1) FROM user_invite_event WHERE invitee_user_id=?",
            Integer.class,
            inviteeUserId);
    if (already != null && already > 0) {
      return BindResult.fail("你已绑定过邀请关系");
    }
    try {
      jdbcTemplate.update(
          "INSERT INTO user_invite_event (inviter_user_id, invitee_user_id, invite_code, reward_granted) VALUES (?,?,?,1)",
          inviter,
          inviteeUserId,
          code);
    } catch (DuplicateKeyException e) {
      return BindResult.fail("你已绑定过邀请关系");
    }
    jdbcTemplate.update(
        "UPDATE app_user SET read_balance = read_balance + ? WHERE id=?",
        INVITE_REWARD_READS,
        inviter);
    return BindResult.ok("邀请码已生效，你已获得 " + INVITE_REWARD_READS + " 点阅读数");
  }

  public record BindResult(boolean bound, String message) {
    static BindResult ok(String message) {
      return new BindResult(true, message);
    }

    static BindResult fail(String message) {
      return new BindResult(false, message);
    }
  }

  @Transactional
  public String ensureInviteCode(long userId) {
    var existing = jdbcTemplate.query(
        "SELECT code FROM user_invite_code WHERE user_id=?",
        (rs, i) -> rs.getString(1),
        userId
    );
    if (!existing.isEmpty()) {
      return existing.get(0);
    }
    for (int attempt = 0; attempt < 32; attempt++) {
      String code = randomCode(10);
      try {
        jdbcTemplate.update("INSERT INTO user_invite_code (user_id, code) VALUES (?,?)", userId, code);
        return code;
      } catch (DuplicateKeyException e) {
        // code collision, retry
      }
    }
    throw new IllegalStateException("failed to allocate invite code");
  }

  public List<AssistParticipantDTO> listInviteParticipants(long inviterUserId, int limit) {
    return jdbcTemplate.query(
        "SELECT u.nickname, u.avatar_url FROM user_invite_event e "
            + "INNER JOIN app_user u ON u.id = e.invitee_user_id "
            + "WHERE e.inviter_user_id=? ORDER BY e.created_at ASC LIMIT ?",
        (rs, i) ->
            new AssistParticipantDTO(
                rs.getString("nickname"),
                rs.getString("avatar_url")
            ),
        inviterUserId,
        limit
    );
  }

  public int countSuccessfulInvites(long inviterUserId) {
    Integer n = jdbcTemplate.queryForObject(
        "SELECT COUNT(1) FROM user_invite_event WHERE inviter_user_id=?",
        Integer.class,
        inviterUserId
    );
    return n == null ? 0 : n;
  }

  public int readBalance(long userId) {
    Integer b = jdbcTemplate.queryForObject(
        "SELECT read_balance FROM app_user WHERE id=?",
        Integer.class,
        userId
    );
    return b == null ? 0 : b;
  }

  private static String randomCode(int len) {
    StringBuilder sb = new StringBuilder(len);
    for (int i = 0; i < len; i++) {
      sb.append(CODE_ALPHABET.charAt(RNG.nextInt(CODE_ALPHABET.length())));
    }
    return sb.toString();
  }
}
