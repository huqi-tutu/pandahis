-- 朝代简介（可选）；无数据时 API 返回「空」
ALTER TABLE historical_dynasty
  ADD COLUMN summary TEXT NULL COMMENT '朝代简介' AFTER end_year_raw;
