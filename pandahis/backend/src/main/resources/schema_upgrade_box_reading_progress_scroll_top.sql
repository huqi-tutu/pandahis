-- 已有库升级：阅读进度增加 scroll_top_px（执行一次）

ALTER TABLE user_box_reading_progress
  ADD COLUMN scroll_top_px INT NULL COMMENT '详情 scroll-view 滚动偏移（有栏坐标系）' AFTER progress_pct;
