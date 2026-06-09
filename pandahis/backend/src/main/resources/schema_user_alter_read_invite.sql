-- 已有库升级：邀请与阅读数（执行一次）

ALTER TABLE app_user ADD COLUMN read_balance INT NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS user_invite_code (
  user_id BIGINT PRIMARY KEY,
  code VARCHAR(16) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_user_invite_code_code (code)
);

CREATE TABLE IF NOT EXISTS user_invite_event (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  inviter_user_id BIGINT NOT NULL,
  invitee_user_id BIGINT NOT NULL,
  invite_code VARCHAR(32) NULL,
  reward_granted TINYINT NOT NULL DEFAULT 1,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_user_invite_event_invitee (invitee_user_id),
  KEY idx_user_invite_event_inviter (inviter_user_id)
);

CREATE TABLE IF NOT EXISTS user_box_tab_read_ledger (
  user_id BIGINT NOT NULL,
  box_id VARCHAR(128) NOT NULL,
  tab_key VARCHAR(16) NOT NULL,
  consumed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, box_id, tab_key),
  KEY idx_read_ledger_user (user_id)
);
