-- 从 user_reading_daily 回填 user_footprint（索引重建后 footprint 被清空、daily 仍保留历史时使用）
-- 口径：每用户×篇目一行，last_viewed_at = 最近阅读日，view_count = 阅读天数

INSERT INTO user_footprint (user_id, box_id, last_viewed_at, view_count)
SELECT
  d.user_id,
  d.box_id,
  CAST(MAX(d.read_date) AS DATETIME) AS last_viewed_at,
  COUNT(DISTINCT d.read_date) AS view_count
FROM user_reading_daily d
JOIN historical_box b ON b.id = d.box_id
GROUP BY d.user_id, d.box_id
ON DUPLICATE KEY UPDATE
  last_viewed_at = GREATEST(user_footprint.last_viewed_at, VALUES(last_viewed_at)),
  view_count = GREATEST(user_footprint.view_count, VALUES(view_count));
