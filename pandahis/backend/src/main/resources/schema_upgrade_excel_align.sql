-- 一次性升级脚本：在已有 histomap 库上对齐 Excel/V5 模型（执行前请备份）。
-- MySQL 8+。若列已存在会报错，可忽略对应语句。

ALTER TABLE civilization_l1
  ADD COLUMN code VARCHAR(16) NULL AFTER display_name,
  ADD COLUMN tab_image_url VARCHAR(512) NULL AFTER color_hex;

CREATE UNIQUE INDEX uk_civilization_l1_code ON civilization_l1 (code);

CREATE TABLE IF NOT EXISTS historical_dynasty (
  id VARCHAR(32) PRIMARY KEY,
  civilization_l1_id BIGINT NOT NULL,
  name VARCHAR(128) NOT NULL,
  start_year INT NULL,
  end_year INT NULL,
  start_year_raw VARCHAR(32) NULL,
  end_year_raw VARCHAR(32) NULL,
  sort_order INT NOT NULL DEFAULT 0,
  status TINYINT NOT NULL DEFAULT 1,
  CONSTRAINT fk_dynasty_civ_upg FOREIGN KEY (civilization_l1_id) REFERENCES civilization_l1 (id)
);

ALTER TABLE historical_unit
  ADD COLUMN ruler_name VARCHAR(64) NULL AFTER name,
  ADD COLUMN dynasty_id VARCHAR(32) NULL AFTER dynasty_name,
  ADD COLUMN temple_name VARCHAR(64) NULL AFTER era_name,
  ADD COLUMN era_title VARCHAR(64) NULL AFTER temple_name,
  ADD COLUMN importance_level TINYINT NULL AFTER duration_years,
  ADD COLUMN notes TEXT NULL AFTER summary;

ALTER TABLE historical_unit
  ADD CONSTRAINT fk_unit_dynasty_upg FOREIGN KEY (dynasty_id) REFERENCES historical_dynasty (id);

ALTER TABLE historical_box
  ADD COLUMN business_code VARCHAR(32) NULL AFTER id,
  ADD COLUMN subject_unit_id VARCHAR(64) NULL AFTER unit_id,
  ADD COLUMN dynasty_id VARCHAR(32) NULL AFTER subject_unit_id,
  ADD COLUMN shilue_kind VARCHAR(16) NULL AFTER category_key,
  ADD COLUMN blurb VARCHAR(64) NULL AFTER shilue_kind,
  ADD COLUMN priority_code VARCHAR(8) NULL AFTER importance_level,
  ADD COLUMN priority_reason TEXT NULL AFTER priority_code,
  ADD COLUMN detail_md_flash TEXT NULL AFTER detail_md,
  ADD COLUMN detail_md_pro TEXT NULL AFTER detail_md_flash;

CREATE UNIQUE INDEX uk_historical_box_business_code ON historical_box (business_code);

ALTER TABLE historical_box
  ADD CONSTRAINT fk_box_subject_unit_upg FOREIGN KEY (subject_unit_id) REFERENCES historical_unit (id),
  ADD CONSTRAINT fk_box_dynasty_upg FOREIGN KEY (dynasty_id) REFERENCES historical_dynasty (id);

ALTER TABLE box_critique
  ADD COLUMN title VARCHAR(128) NULL AFTER box_id,
  ADD COLUMN blurb VARCHAR(256) NULL AFTER source;

ALTER TABLE box_relic
  ADD COLUMN summary VARCHAR(256) NULL AFTER image_url,
  ADD COLUMN priority_code VARCHAR(8) NULL AFTER museum,
  ADD COLUMN priority_reason TEXT NULL AFTER priority_code;
