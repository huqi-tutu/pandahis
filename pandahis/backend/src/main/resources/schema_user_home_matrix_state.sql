-- 已有库升级：首页矩阵记住上次朝代与折叠状态（执行一次）

CREATE TABLE IF NOT EXISTS user_home_matrix_state (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id BIGINT NOT NULL,
  civilization_code VARCHAR(16) NOT NULL DEFAULT 'HX',
  last_dynasty_key VARCHAR(64) NULL,
  collapsed_dynasty_keys_json JSON NULL,
  last_scroll_top_px INT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_user_home_matrix_state_user (user_id),
  KEY idx_user_home_matrix_state_dynasty (last_dynasty_key),
  CONSTRAINT fk_user_home_matrix_state_user FOREIGN KEY (user_id) REFERENCES app_user (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户首页矩阵状态';
