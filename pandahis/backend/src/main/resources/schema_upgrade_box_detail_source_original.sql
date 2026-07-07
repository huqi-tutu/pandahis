-- 史略翻译详情表增加「史料原文」JSON 字段（供 /boxes/{id}/original-ref 接口）
-- 执行后运行: python scripts/import_box_translate_json.py

ALTER TABLE historical_box_detail
  ADD COLUMN source_original_json LONGTEXT NULL COMMENT '史料原文 JSON（含 text/blocks）' AFTER translate_detail;
