-- historical_box：唯一 ID 为 史略ID（id），母本史略ID 改为 parent_entry_id（非唯一）
-- 执行: python scripts/import_box_index_json.py

ALTER TABLE historical_box DROP INDEX uk_historical_box_business_code;
ALTER TABLE historical_box CHANGE COLUMN business_code parent_entry_id VARCHAR(64) NULL COMMENT '母本史略ID';
ALTER TABLE historical_box ADD INDEX idx_box_parent_entry (parent_entry_id);
