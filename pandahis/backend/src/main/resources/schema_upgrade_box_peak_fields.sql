ALTER TABLE historical_box
  ADD COLUMN IF NOT EXISTS peak_year INT NULL COMMENT '峰值年' AFTER importance_level,
  ADD COLUMN IF NOT EXISTS peak_reason TEXT NULL COMMENT '峰值原因' AFTER peak_year,
  ADD COLUMN IF NOT EXISTS peak_type VARCHAR(64) NULL COMMENT '峰值类型' AFTER peak_reason;
