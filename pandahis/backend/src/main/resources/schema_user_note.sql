-- 用户划线笔记：新库可与 schema_user.sql 一并执行；已有库单独执行本文件
CREATE TABLE IF NOT EXISTS user_box_note (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id BIGINT NOT NULL,
  box_id VARCHAR(128) NOT NULL,
  box_title VARCHAR(256) NOT NULL DEFAULT '',
  box_category_key VARCHAR(16) NOT NULL DEFAULT '' COMMENT '史略类型 category_key',
  unit_id VARCHAR(128) NULL COMMENT '朝代 ID（dynasty_id，三国等乱世归朝代而非政权）',
  civilization_name VARCHAR(128) NOT NULL DEFAULT '',
  dynasty_name VARCHAR(128) NOT NULL DEFAULT '',
  regime_name VARCHAR(128) NOT NULL DEFAULT '',
  emperor_name VARCHAR(128) NOT NULL DEFAULT '',
  coordinate_text VARCHAR(512) NOT NULL DEFAULT '' COMMENT '四级坐标：文明 · 朝代 · 政权 · 君王',
  source_type VARCHAR(32) NOT NULL COMMENT 'box_detail_selection | critique_detail_selection | relic_detail_selection | relation_graph_selection',
  source_ref_id BIGINT NULL COMMENT '评述/见证主键 ID（随 source_type 解释）',
  selected_text VARCHAR(2000) NOT NULL COMMENT '划线选中的原文',
  note_text VARCHAR(2000) NULL COMMENT '用户填写的笔记，可空（仅划线）',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_user_box_note_user_created (user_id, created_at DESC),
  KEY idx_user_box_note_user_dynasty (user_id, unit_id),
  KEY idx_user_box_note_user_box_source (user_id, box_id, source_type),
  CONSTRAINT fk_user_box_note_user FOREIGN KEY (user_id) REFERENCES app_user (id)
);
