-- 阅读足迹 · 按天明细（热力图数据源）
-- 口径：用户 × 日期 × 篇目 唯一，同一天重复阅读同一篇只记 1 行；
-- 某天的「阅读篇数」= 该用户当天的行数。

CREATE TABLE IF NOT EXISTS user_reading_daily (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id BIGINT NOT NULL,
  read_date DATE NOT NULL,
  box_id VARCHAR(128) NOT NULL,
  UNIQUE KEY uk_user_date_box (user_id, read_date, box_id),
  KEY idx_user_date (user_id, read_date)
);

-- 一次性历史回填：用现有足迹表的「最后阅读时间」补一个点。
-- 注意：user_footprint 是按 (user_id, box_id) 覆盖式记录，
-- 历史上的真实每日密度无法还原，此回填仅保证上线时热力图不至于全空。
INSERT IGNORE INTO user_reading_daily (user_id, read_date, box_id)
SELECT user_id, DATE(last_viewed_at), box_id
FROM user_footprint;
