-- 史略详情来源：区分「史料顺译」与「大模型撰写」（与 entry_source 正交）
-- 执行后运行: python scripts/sync_detail_source.py

ALTER TABLE historical_box
  ADD COLUMN detail_source VARCHAR(16) NULL
    COMMENT '详情来源: translate=史料顺译 compose=大模型撰写'
    AFTER entry_source;

ALTER TABLE historical_box
  ADD INDEX idx_box_detail_source (detail_source);
