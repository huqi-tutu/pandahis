-- 纠错记录补充评述/见证来源 ID，用于「去查看」精确跳转
ALTER TABLE user_box_correction
  ADD COLUMN source_ref_id BIGINT NULL COMMENT '评述/见证主键 ID（随 source_type 解释）' AFTER source_type;
