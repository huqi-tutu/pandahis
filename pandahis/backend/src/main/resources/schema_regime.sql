-- 政权表：由 data/政权.json 导入
-- 执行后运行: python scripts/import_regime_json.py

CREATE TABLE IF NOT EXISTS historical_regime (
  id VARCHAR(128) PRIMARY KEY COMMENT '政权ID（JSON 政权ID）',
  name VARCHAR(128) NOT NULL COMMENT '政权名称',
  dynasty_id VARCHAR(64) NOT NULL COMMENT '所属朝代ID',
  dynasty_name VARCHAR(128) NOT NULL COMMENT '朝代名称（JSON 原文）',
  dynasty_zy VARCHAR(128) NULL COMMENT '主朝代归属（JSON dynasty_zy）',
  civilization_l1_id BIGINT NOT NULL COMMENT '所属文明ID',
  civilization_name VARCHAR(64) NULL COMMENT '文明名称（JSON 原文）',
  civilization_code VARCHAR(16) NULL COMMENT '文明编码（JSON 文明ID）',
  start_year INT NULL COMMENT '开始年份',
  end_year INT NULL COMMENT '结束年份',
  start_year_raw VARCHAR(32) NULL COMMENT '开始时间原文',
  end_year_raw VARCHAR(32) NULL COMMENT '结束时间原文',
  sort_order INT NOT NULL DEFAULT 0,
  status TINYINT NOT NULL DEFAULT 1,
  INDEX idx_regime_dynasty (dynasty_id),
  INDEX idx_regime_civ (civilization_l1_id),
  CONSTRAINT fk_regime_dynasty FOREIGN KEY (dynasty_id) REFERENCES historical_dynasty (id),
  CONSTRAINT fk_regime_civ FOREIGN KEY (civilization_l1_id) REFERENCES civilization_l1 (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='政权';
