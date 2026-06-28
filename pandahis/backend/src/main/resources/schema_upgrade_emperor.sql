-- historical_unit → historical_emperor，historical_box.unit_id → emperor_id
-- 执行: python scripts/import_emperor_json.py

-- 1) historical_box：解除旧 FK，列改名，清空待后续 box 优化用帝王ID 关联
ALTER TABLE historical_box DROP FOREIGN KEY fk_box_unit;
ALTER TABLE historical_box DROP FOREIGN KEY fk_box_subject_unit;
ALTER TABLE historical_box DROP FOREIGN KEY fk_box_subject_unit_upg;

ALTER TABLE historical_box CHANGE COLUMN unit_id emperor_id VARCHAR(128) NULL;
ALTER TABLE historical_box CHANGE COLUMN subject_unit_id subject_emperor_id VARCHAR(128) NULL;

UPDATE historical_box SET emperor_id = NULL, subject_emperor_id = NULL;

-- 2) 删除旧帝王表
DROP TABLE IF EXISTS historical_unit;

-- 3) 新建 historical_emperor（字段对齐 data/帝王.json）
CREATE TABLE historical_emperor (
  id VARCHAR(128) PRIMARY KEY COMMENT '帝王ID',
  name VARCHAR(128) NOT NULL COMMENT '帝王名称',
  ruler_name VARCHAR(64) NULL COMMENT '帝王原名',
  regime_id VARCHAR(128) NOT NULL COMMENT '政权ID',
  regime_name VARCHAR(128) NOT NULL COMMENT '政权名称',
  dynasty_id VARCHAR(64) NOT NULL COMMENT '朝代ID',
  dynasty_name VARCHAR(128) NOT NULL COMMENT '朝代名称',
  civilization_l1_id BIGINT NOT NULL COMMENT '文明ID',
  civilization_name VARCHAR(64) NULL COMMENT '文明名称',
  civilization_code VARCHAR(16) NULL COMMENT '文明编码',
  temple_name VARCHAR(64) NULL COMMENT '庙号',
  era_name VARCHAR(64) NULL COMMENT '年号',
  enthronement_year INT NULL COMMENT '即位时间（数值）',
  abdication_year INT NULL COMMENT '退位时间（数值）',
  enthronement_year_raw VARCHAR(32) NULL COMMENT '即位时间原文',
  abdication_year_raw VARCHAR(32) NULL COMMENT '退位时间原文',
  reign_duration INT NULL COMMENT '在位时长',
  importance_level TINYINT NULL COMMENT '重要性评级',
  tags TEXT NULL COMMENT '标签',
  card_image_url VARCHAR(512) NULL COMMENT '卡片配图',
  sort_order INT NOT NULL DEFAULT 0,
  status TINYINT NOT NULL DEFAULT 1,
  INDEX idx_emperor_regime (regime_id),
  INDEX idx_emperor_dynasty (dynasty_id),
  INDEX idx_emperor_civ (civilization_l1_id),
  CONSTRAINT fk_emperor_regime FOREIGN KEY (regime_id) REFERENCES historical_regime (id),
  CONSTRAINT fk_emperor_dynasty FOREIGN KEY (dynasty_id) REFERENCES historical_dynasty (id),
  CONSTRAINT fk_emperor_civ FOREIGN KEY (civilization_l1_id) REFERENCES civilization_l1 (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='帝王';
