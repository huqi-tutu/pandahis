-- 史略分类展示名：君纪 → 君王（category_key 编码 junji 不变）
-- MySQL 8+。执行前请备份。

UPDATE historical_box
SET shilue_kind = '君王'
WHERE shilue_kind = '君纪';
