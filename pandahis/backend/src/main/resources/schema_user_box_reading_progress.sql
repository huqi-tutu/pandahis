-- 已有库升级：史略详情阅读进度（登录用户；执行一次）

CREATE TABLE IF NOT EXISTS user_box_reading_progress (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id BIGINT NOT NULL,
  box_id VARCHAR(128) NOT NULL,
  progress_pct TINYINT NOT NULL,
  scroll_top_px INT NULL,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_user_box_reading_progress (user_id, box_id),
  KEY idx_user_box_reading_progress_user (user_id),
  CONSTRAINT fk_user_box_reading_progress_user FOREIGN KEY (user_id) REFERENCES app_user (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户史略详情阅读进度（百分比）';
