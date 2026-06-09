package com.pandahis.histomap.invite.service;

import com.pandahis.histomap.common.api.ApiException;
import com.pandahis.histomap.contentgraph.interfaces.dto.BoxHeaderDTO;
import com.pandahis.histomap.membership.interfaces.service.MembershipService;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class DeepTabReadService {
  private final JdbcTemplate jdbcTemplate;
  private final MembershipService membershipService;

  public DeepTabReadService(JdbcTemplate jdbcTemplate, MembershipService membershipService) {
    this.jdbcTemplate = jdbcTemplate;
    this.membershipService = membershipService;
  }

  private static BoxHeaderDTO.TabAccess unlocked() {
    return new BoxHeaderDTO.TabAccess(false, null, null);
  }

  private static BoxHeaderDTO.TabAccess lockedLogin() {
    return new BoxHeaderDTO.TabAccess(true, "LOGIN_REQUIRED", new BoxHeaderDTO.UnlockAction("OPEN_LOGIN"));
  }

  private static BoxHeaderDTO.TabAccess lockedNeedMembership() {
    return new BoxHeaderDTO.TabAccess(
        true,
        "NEED_MEMBERSHIP_OR_READS",
        new BoxHeaderDTO.UnlockAction("OPEN_MEMBERSHIP_PAGE")
    );
  }

  public BoxHeaderDTO.TabAccess tabAccess(long userId, String boxId, boolean authed, String tabKey) {
    if (!authed) {
      return lockedLogin();
    }
    if (membershipService.isActiveMember(userId)) {
      return unlocked();
    }
    if (hasLedger(userId, boxId, tabKey)) {
      return unlocked();
    }
    int balance = readBalance(userId);
    if (balance < 1) {
      return lockedNeedMembership();
    }
    return unlocked();
  }

  public int readBalance(long userId) {
    Integer b = jdbcTemplate.queryForObject(
        "SELECT read_balance FROM app_user WHERE id=?",
        Integer.class,
        userId
    );
    return b == null ? 0 : b;
  }

  private boolean hasLedger(long userId, String boxId, String tabKey) {
    Integer c = jdbcTemplate.queryForObject(
        "SELECT COUNT(1) FROM user_box_tab_read_ledger WHERE user_id=? AND box_id=? AND tab_key=?",
        Integer.class,
        userId,
        boxId,
        tabKey
    );
    return c != null && c > 0;
  }

  /**
   * 首次打开某深度 Tab 扣 1 点阅读数；会员有效期内免扣；已扣过则幂等。
   */
  @Transactional
  public void ensurePaidDeepTab(long userId, String boxId, String tabKey) {
    if (membershipService.isActiveMember(userId)) {
      return;
    }
    if (hasLedger(userId, boxId, tabKey)) {
      return;
    }
    Integer bal = jdbcTemplate.queryForObject(
        "SELECT read_balance FROM app_user WHERE id=? FOR UPDATE",
        Integer.class,
        userId
    );
    if (bal == null) {
      throw ApiException.forbidden("NEED_MEMBERSHIP_OR_READS");
    }
    if (bal < 1) {
      throw ApiException.forbidden("NEED_MEMBERSHIP_OR_READS");
    }
    int updated = jdbcTemplate.update(
        "UPDATE app_user SET read_balance = read_balance - 1 WHERE id=? AND read_balance >= 1",
        userId
    );
    if (updated != 1) {
      throw ApiException.forbidden("NEED_MEMBERSHIP_OR_READS");
    }
    jdbcTemplate.update(
        "INSERT INTO user_box_tab_read_ledger (user_id, box_id, tab_key, consumed_at) VALUES (?,?,?,NOW())",
        userId,
        boxId,
        tabKey
    );
  }
}
