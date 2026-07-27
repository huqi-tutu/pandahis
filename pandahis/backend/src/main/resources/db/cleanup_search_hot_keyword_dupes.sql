-- 清理 search_hot_keyword 重复词（保留 id 最小的一条），再补唯一索引
-- 在已有库上手工执行一次即可

DELETE t1 FROM search_hot_keyword t1
INNER JOIN search_hot_keyword t2
  ON t1.keyword = t2.keyword AND t1.id > t2.id;

-- 若索引已存在会报错，可忽略
ALTER TABLE search_hot_keyword
  ADD UNIQUE KEY uk_search_hot_keyword (keyword);
