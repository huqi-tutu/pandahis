-- 邀友助力领季度会员：每用户仅可领取一次
CREATE TABLE IF NOT EXISTS user_membership_assist_claim (
  user_id BIGINT PRIMARY KEY,
  claimed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
