-- 史略翻译详情：仅存储史略ID与翻译正文
-- 执行后运行: python scripts/import_box_translate_json.py

CREATE TABLE IF NOT EXISTS historical_box_detail (
  box_id VARCHAR(64) PRIMARY KEY COMMENT '史略ID',
  translate_detail LONGTEXT NOT NULL COMMENT '翻译详情',
  CONSTRAINT fk_box_detail_box FOREIGN KEY (box_id) REFERENCES historical_box (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='史略翻译详情';
