-- 史略来源：区分「史料提取」与「模型补全」
-- 执行后运行: python scripts/import_box_index_json.py

ALTER TABLE historical_box
  ADD COLUMN entry_source VARCHAR(16) NOT NULL DEFAULT 'extract'
    COMMENT '史略来源: extract=史料提取 supplement=模型补全'
    AFTER category_key;

ALTER TABLE historical_box
  ADD INDEX idx_box_entry_source (entry_source);
