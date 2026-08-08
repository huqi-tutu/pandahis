-- 用户帮助与反馈
CREATE TABLE IF NOT EXISTS user_feedback (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id BIGINT NOT NULL,
  feedback_type VARCHAR(32) NOT NULL COMMENT 'feature | content | partnership | other',
  content VARCHAR(1000) NOT NULL,
  image_urls_json TEXT NULL COMMENT 'JSON 数组，最多 3 个图片 URL',
  status VARCHAR(16) NOT NULL DEFAULT 'pending' COMMENT 'pending | reviewed | resolved',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_user_feedback_user_created (user_id, created_at DESC),
  KEY idx_user_feedback_created (created_at DESC),
  CONSTRAINT fk_user_feedback_user FOREIGN KEY (user_id) REFERENCES app_user (id)
);
