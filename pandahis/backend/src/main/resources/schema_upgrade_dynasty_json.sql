-- 朝代.json 全量同步：扩展 ID 长度 + 增加 JSON 冗余字段
-- 执行后运行: python scripts/import_dynasty_json.py

ALTER TABLE historical_dynasty
  MODIFY COLUMN id VARCHAR(64) NOT NULL;

ALTER TABLE historical_dynasty
  ADD COLUMN civilization_name VARCHAR(64) NULL COMMENT '文明名称（JSON 原文）' AFTER civilization_l1_id,
  ADD COLUMN civilization_code VARCHAR(16) NULL COMMENT '文明编码（JSON 文明ID）' AFTER civilization_name;
