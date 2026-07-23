-- 史略「标记读完」：用户 × 篇目唯一，记录完成时间与列表排序

CREATE TABLE IF NOT EXISTS user_box_read_completion (
  user_id BIGINT NOT NULL,
  box_id VARCHAR(128) NOT NULL,
  completed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, box_id),
  KEY idx_user_completed (user_id, completed_at DESC)
);
