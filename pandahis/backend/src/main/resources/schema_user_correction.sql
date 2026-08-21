CREATE TABLE IF NOT EXISTS user_box_correction (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id BIGINT NOT NULL,
  box_id VARCHAR(128) NOT NULL,
  box_title VARCHAR(256) NOT NULL DEFAULT '',
  unit_id VARCHAR(128) NULL COMMENT '朝代/单元 ID',
  civilization_name VARCHAR(128) NOT NULL DEFAULT '',
  dynasty_name VARCHAR(128) NOT NULL DEFAULT '',
  source_type VARCHAR(32) NOT NULL COMMENT 'dynasty_canvas | box_detail_selection | box_original_selection | critique_detail_selection | relic_detail_selection | relation_graph_selection',
  source_ref_id BIGINT NULL COMMENT '评述/见证主键 ID（随 source_type 解释）',
  selected_text TEXT NULL COMMENT '划词选中的原文片段',
  reason VARCHAR(500) NULL COMMENT '用户填写的纠错原因',
  status VARCHAR(16) NOT NULL DEFAULT 'pending' COMMENT 'pending | reviewed | resolved',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_user_box_correction_user_created (user_id, created_at DESC),
  KEY idx_user_box_correction_user_box (user_id, box_id),
  CONSTRAINT fk_user_box_correction_user FOREIGN KEY (user_id) REFERENCES app_user (id)
);
