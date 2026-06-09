package com.pandahis.histomap.membership.interfaces.service;

import com.pandahis.histomap.common.api.ApiException;
import com.pandahis.histomap.invite.service.InviteService;
import com.pandahis.histomap.membership.interfaces.dto.AssistParticipantDTO;
import com.pandahis.histomap.membership.interfaces.dto.MembershipAssistDTO;
import com.pandahis.histomap.membership.interfaces.dto.MembershipDTO;
import java.time.OffsetDateTime;
import java.util.List;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class MembershipAssistService {
  public static final int ASSIST_TARGET_COUNT = 4;
  public static final int ASSIST_DEADLINE_DAYS = 30;
  public static final String REWARD_PLAN_ID = "quarter";

  private final JdbcTemplate jdbcTemplate;
  private final InviteService inviteService;
  private final MembershipService membershipService;

  public MembershipAssistService(
      JdbcTemplate jdbcTemplate,
      InviteService inviteService,
      MembershipService membershipService
  ) {
    this.jdbcTemplate = jdbcTemplate;
    this.inviteService = inviteService;
    this.membershipService = membershipService;
  }

  public MembershipAssistDTO getAssist(long userId) {
    int current = inviteService.countSuccessfulInvites(userId);
    boolean claimed = hasClaimed(userId);
    MembershipDTO membership = membershipService.getMembership(userId);
    String planName = planDisplayName(REWARD_PLAN_ID);
    int durationDays = planDurationDays(REWARD_PLAN_ID);
    boolean completed = current >= ASSIST_TARGET_COUNT;
    List<AssistParticipantDTO> participants =
        inviteService.listInviteParticipants(userId, ASSIST_TARGET_COUNT);
    String deadlineAt = resolveAssistDeadline(userId, claimed);
    return new MembershipAssistDTO(
        ASSIST_TARGET_COUNT,
        Math.min(current, ASSIST_TARGET_COUNT),
        completed,
        claimed,
        planName,
        durationDays,
        membership.endAt(),
        deadlineAt,
        participants
    );
  }

  @Transactional
  public MembershipAssistDTO claimReward(long userId) {
    if (isAssistExpired(userId) && !hasClaimed(userId)) {
      throw ApiException.invalidArgument("invite assist campaign expired");
    }
    int current = inviteService.countSuccessfulInvites(userId);
    if (current < ASSIST_TARGET_COUNT) {
      throw ApiException.invalidArgument("invite assist not completed yet");
    }
    if (hasClaimed(userId)) {
      return getAssist(userId);
    }
    int durationDays = planDurationDays(REWARD_PLAN_ID);
    membershipService.grantOrExtendMembership(userId, durationDays);
    try {
      jdbcTemplate.update(
          "INSERT INTO user_membership_assist_claim (user_id) VALUES (?)",
          userId
      );
    } catch (DuplicateKeyException e) {
      // concurrent claim
    }
    return getAssist(userId);
  }

  private String resolveAssistDeadline(long userId, boolean claimed) {
    if (claimed) {
      return null;
    }
    OffsetDateTime anchor = firstInviteAt(userId);
    if (anchor == null) {
      anchor = OffsetDateTime.now();
    }
    return anchor.plusDays(ASSIST_DEADLINE_DAYS).toString();
  }

  private boolean isAssistExpired(long userId) {
    if (hasClaimed(userId)) {
      return false;
    }
    String deadline = resolveAssistDeadline(userId, false);
    if (deadline == null || deadline.isBlank()) {
      return false;
    }
    try {
      OffsetDateTime end = OffsetDateTime.parse(deadline);
      return end.isBefore(OffsetDateTime.now());
    } catch (Exception e) {
      return false;
    }
  }

  private OffsetDateTime firstInviteAt(long userId) {
    try {
      return jdbcTemplate.queryForObject(
          "SELECT MIN(created_at) FROM user_invite_event WHERE inviter_user_id=?",
          OffsetDateTime.class,
          userId
      );
    } catch (Exception e) {
      return null;
    }
  }

  private boolean hasClaimed(long userId) {
    try {
      Integer n = jdbcTemplate.queryForObject(
          "SELECT COUNT(1) FROM user_membership_assist_claim WHERE user_id=?",
          Integer.class,
          userId
      );
      return n != null && n > 0;
    } catch (Exception e) {
      return false;
    }
  }

  private String planDisplayName(String planId) {
    try {
      return jdbcTemplate.queryForObject(
          "SELECT name FROM membership_plan WHERE id=?",
          String.class,
          planId
      );
    } catch (Exception e) {
      return "季度会员卡";
    }
  }

  private int planDurationDays(String planId) {
    try {
      Integer days = jdbcTemplate.queryForObject(
          "SELECT duration_days FROM membership_plan WHERE id=?",
          Integer.class,
          planId
      );
      return days == null ? 90 : days;
    } catch (Exception e) {
      return 90;
    }
  }
}
