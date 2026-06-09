package com.pandahis.histomap.membership.interfaces.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.pandahis.histomap.common.api.ApiException;
import com.pandahis.histomap.common.jdbc.JdbcDates;
import com.pandahis.histomap.membership.interfaces.MembershipController.WechatNotifyRequest;
import com.pandahis.histomap.membership.interfaces.dto.CreateOrderDTO;
import com.pandahis.histomap.membership.interfaces.dto.MembershipDTO;
import com.pandahis.histomap.membership.interfaces.dto.MembershipPlansDTO;
import com.pandahis.histomap.membership.interfaces.dto.OrderDTO;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;

@Service
public class MembershipService {
  private final JdbcTemplate jdbcTemplate;
  private final ObjectMapper objectMapper;

  public MembershipService(JdbcTemplate jdbcTemplate, ObjectMapper objectMapper) {
    this.jdbcTemplate = jdbcTemplate;
    this.objectMapper = objectMapper;
  }

  public MembershipPlansDTO listPlans() {
    List<MembershipPlansDTO.Plan> plans = jdbcTemplate.query(
        "SELECT id,name,price_cent,duration_days,is_default,tag_text,benefits_json FROM membership_plan WHERE status=1 "
            + "ORDER BY CASE id WHEN 'month' THEN 1 WHEN 'quarter' THEN 2 WHEN 'year' THEN 3 ELSE 9 END, price_cent ASC",
        (rs, rowNum) -> new MembershipPlansDTO.Plan(
            rs.getString("id"),
            rs.getString("name"),
            rs.getInt("price_cent"),
            rs.getInt("duration_days"),
            rs.getInt("is_default") == 1,
            rs.getString("tag_text"),
            parseBenefits(rs.getString("benefits_json"))
        )
    );
    return new MembershipPlansDTO(plans);
  }

  public MembershipDTO getMembership(Long userId) {
    List<Map<String, Object>> rows = jdbcTemplate.queryForList(
        "SELECT end_at,status FROM membership WHERE user_id=?",
        userId
    );
    if (rows.isEmpty()) return new MembershipDTO("NONE", null);
    OffsetDateTime endAt = JdbcDates.toOffsetDateTime(rows.get(0).get("end_at"));
    if (endAt != null && endAt.isBefore(OffsetDateTime.now())) {
      return new MembershipDTO("EXPIRED", endAt.toString());
    }
    return new MembershipDTO("ACTIVE", endAt == null ? null : endAt.toString());
  }

  /** 会员有效期内：深度 Tab 免扣阅读点 */
  public boolean isActiveMember(long userId) {
    List<Map<String, Object>> rows = jdbcTemplate.queryForList(
        "SELECT end_at, status FROM membership WHERE user_id=?",
        userId
    );
    if (rows.isEmpty()) return false;
    String status = String.valueOf(rows.get(0).get("status"));
    if (!"active".equalsIgnoreCase(status)) return false;
    OffsetDateTime endAt = JdbcDates.toOffsetDateTime(rows.get(0).get("end_at"));
    return endAt == null || endAt.isAfter(OffsetDateTime.now());
  }

  /** 开通或续期会员（已有有效会员则在原到期日上叠加天数） */
  @Transactional
  public void grantOrExtendMembership(long userId, int durationDays) {
    OffsetDateTime now = OffsetDateTime.now();
    List<Map<String, Object>> rows = jdbcTemplate.queryForList(
        "SELECT start_at, end_at, status FROM membership WHERE user_id=?",
        userId
    );
    if (rows.isEmpty()) {
      jdbcTemplate.update(
          "INSERT INTO membership(user_id, start_at, end_at, status) VALUES (?,?,?,?)",
          userId,
          now,
          now.plusDays(durationDays),
          "active"
      );
      return;
    }
    Map<String, Object> row = rows.get(0);
    OffsetDateTime endAt = JdbcDates.toOffsetDateTime(row.get("end_at"));
    String status = String.valueOf(row.get("status"));
    boolean active =
        "active".equalsIgnoreCase(status) && endAt != null && endAt.isAfter(now);
    if (active) {
      jdbcTemplate.update(
          "UPDATE membership SET end_at=?, status='active' WHERE user_id=?",
          endAt.plusDays(durationDays),
          userId
      );
      return;
    }
    jdbcTemplate.update(
        "UPDATE membership SET start_at=?, end_at=?, status='active' WHERE user_id=?",
        now,
        now.plusDays(durationDays),
        userId
    );
  }

  @Transactional
  public CreateOrderDTO createOrder(Long userId, String planId) {
    Map<String, Object> plan = jdbcTemplate.queryForMap(
        "SELECT id,price_cent FROM membership_plan WHERE id=? AND status=1",
        planId
    );
    int amount = ((Number) plan.get("price_cent")).intValue();
    jdbcTemplate.update(
        "INSERT INTO biz_order(user_id, plan_id, amount_cent, status) VALUES (?,?,?,?)",
        userId, planId, amount, "created"
    );
    Long orderId = jdbcTemplate.queryForObject("SELECT MAX(id) FROM biz_order WHERE user_id=?", Long.class, userId);
    if (orderId == null) throw ApiException.internalError("order create failed");

    // v1 skeleton: return placeholder pay params (real WeChat unified order in future).
    Map<String, Object> payParams = Map.of(
        "timeStamp", String.valueOf(System.currentTimeMillis() / 1000),
        "nonceStr", "nonce",
        "package", "prepay_id=mock",
        "signType", "RSA",
        "paySign", "mock-sign"
    );
    return new CreateOrderDTO(orderId, "created", payParams);
  }

  public OrderDTO getOrder(Long userId, long orderId) {
    List<Map<String, Object>> rows = jdbcTemplate.queryForList(
        "SELECT id,user_id,plan_id,amount_cent,status,paid_at FROM biz_order WHERE id=?",
        orderId
    );
    if (rows.isEmpty()) throw ApiException.notFound("order not found");
    Map<String, Object> r = rows.get(0);
    long owner = ((Number) r.get("user_id")).longValue();
    if (owner != userId) throw ApiException.forbidden("forbidden");
    OffsetDateTime paidAt = JdbcDates.toOffsetDateTime(r.get("paid_at"));
    return new OrderDTO(
        ((Number) r.get("id")).longValue(),
        (String) r.get("status"),
        ((Number) r.get("amount_cent")).intValue(),
        paidAt == null ? null : paidAt.toString(),
        (String) r.get("plan_id")
    );
  }

  @Transactional
  public void handleNotify(WechatNotifyRequest req) {
    // idempotency by transaction id
    jdbcTemplate.update(
        "INSERT INTO payment_callback_log(order_id, wx_transaction_id, payload_json) VALUES (?,?,?) ON DUPLICATE KEY UPDATE wx_transaction_id=wx_transaction_id",
        req.orderId(),
        req.wxTransactionId(),
        "{\"paidAt\":\"" + req.paidAt() + "\"}"
    );

    List<Map<String, Object>> orders = jdbcTemplate.queryForList(
        "SELECT id,user_id,plan_id,status FROM biz_order WHERE id=?",
        req.orderId()
    );
    if (orders.isEmpty()) return; // return OK to avoid retry storms
    Map<String, Object> o = orders.get(0);
    String status = (String) o.get("status");
    if (!"created".equals(status)) return;

    long userId = ((Number) o.get("user_id")).longValue();
    String planId = (String) o.get("plan_id");
    int durationDays = jdbcTemplate.queryForObject(
        "SELECT duration_days FROM membership_plan WHERE id=?",
        Integer.class,
        planId
    );

    jdbcTemplate.update(
        "UPDATE biz_order SET status='paid', wx_transaction_id=?, paid_at=CURRENT_TIMESTAMP WHERE id=? AND status='created'",
        req.wxTransactionId(),
        req.orderId()
    );

    grantOrExtendMembership(userId, durationDays);
  }

  private List<String> parseBenefits(String json) {
    if (json == null || json.isBlank()) return List.of();
    try {
      return objectMapper.readValue(json, new TypeReference<>() {});
    } catch (Exception ignored) {
      return List.of();
    }
  }
}

