-- 一级地域扩展为 18 条（与 2026-05 文明 tab 配图素材一致）
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- Step B: historical_unit 旧 id -> 临时 id（避免与重建后的 id 冲突）
UPDATE historical_unit SET civilization_l1_id = CASE civilization_l1_id
  WHEN 1 THEN 1001
  WHEN 2 THEN 1002
  WHEN 3 THEN 1003
  WHEN 4 THEN 1004
  WHEN 5 THEN 1007
  WHEN 6 THEN 1008
  WHEN 7 THEN 1008
  WHEN 8 THEN 1013
  WHEN 9 THEN 1010
  WHEN 10 THEN 1009
  WHEN 11 THEN 1011
  WHEN 12 THEN 1014
  WHEN 13 THEN 1016
  WHEN 14 THEN 1018
  ELSE civilization_l1_id
END
WHERE civilization_l1_id BETWEEN 1 AND 14;

UPDATE historical_dynasty SET civilization_l1_id = CASE civilization_l1_id
  WHEN 1 THEN 1001
  WHEN 2 THEN 1002
  WHEN 3 THEN 1003
  WHEN 4 THEN 1004
  WHEN 5 THEN 1007
  WHEN 6 THEN 1008
  WHEN 7 THEN 1008
  WHEN 8 THEN 1013
  WHEN 9 THEN 1010
  WHEN 10 THEN 1009
  WHEN 11 THEN 1011
  WHEN 12 THEN 1014
  WHEN 13 THEN 1016
  WHEN 14 THEN 1018
  ELSE civilization_l1_id
END
WHERE civilization_l1_id BETWEEN 1 AND 14;

-- Step A: 重建 civilization_l1
DELETE FROM civilization_l1;

INSERT INTO civilization_l1 (id, display_name, code, color_hex, tab_image_url, sort_order, status) VALUES
(1,  '华夏',   'HX',  '#84572F', 'https://pandahis-1300045339.cos.ap-chengdu.myqcloud.com/histomap/civ-tab/HX.png',  1,  1),
(2,  '朝鲜',   'CX',  '#9ABCC8', 'https://pandahis-1300045339.cos.ap-chengdu.myqcloud.com/histomap/civ-tab/CX.png',  2,  1),
(3,  '日本',   'RB',  '#EDD5C0', 'https://pandahis-1300045339.cos.ap-chengdu.myqcloud.com/histomap/civ-tab/RB.png',  3,  1),
(4,  '东南亚', 'DNY', '#92ADA4', 'https://pandahis-1300045339.cos.ap-chengdu.myqcloud.com/histomap/civ-tab/DNY.png', 4,  1),
(5,  '中亚',   'ZY',  '#C4A882', 'https://pandahis-1300045339.cos.ap-chengdu.myqcloud.com/histomap/civ-tab/ZY.png',  5,  1),
(6,  '北亚',   'BY',  '#8B9EB5', 'https://pandahis-1300045339.cos.ap-chengdu.myqcloud.com/histomap/civ-tab/BY.png',  6,  1),
(7,  '南亚',   'NY',  '#E0C088', 'https://pandahis-1300045339.cos.ap-chengdu.myqcloud.com/histomap/civ-tab/NY.png',  7,  1),
(8,  '西亚',   'XY',  '#D4B098', 'https://pandahis-1300045339.cos.ap-chengdu.myqcloud.com/histomap/civ-tab/XY.png',  8,  1),
(9,  '南欧',   'NO',  '#92ADA4', 'https://pandahis-1300045339.cos.ap-chengdu.myqcloud.com/histomap/civ-tab/NO.png',  9,  1),
(10, '东欧',   'DO',  '#9ABCC8', 'https://pandahis-1300045339.cos.ap-chengdu.myqcloud.com/histomap/civ-tab/DO.png',  10, 1),
(11, '西欧',   'XO',  '#B3D9E0', 'https://pandahis-1300045339.cos.ap-chengdu.myqcloud.com/histomap/civ-tab/XO.png',  11, 1),
(12, '北欧',   'BO',  '#A8C4D4', 'https://pandahis-1300045339.cos.ap-chengdu.myqcloud.com/histomap/civ-tab/BO.png',  12, 1),
(13, '北非',   'BF',  '#F1A805', 'https://pandahis-1300045339.cos.ap-chengdu.myqcloud.com/histomap/civ-tab/BF.png',  13, 1),
(14, '西非',   'XF',  '#84572F', 'https://pandahis-1300045339.cos.ap-chengdu.myqcloud.com/histomap/civ-tab/XF.png',  14, 1),
(15, '东非',   'DF',  '#B8956A', 'https://pandahis-1300045339.cos.ap-chengdu.myqcloud.com/histomap/civ-tab/DF.png',  15, 1),
(16, '中美',   'ZM',  '#F2D6A1', 'https://pandahis-1300045339.cos.ap-chengdu.myqcloud.com/histomap/civ-tab/ZM.png',  16, 1),
(17, '北美',   'BM',  '#7F96B8', 'https://pandahis-1300045339.cos.ap-chengdu.myqcloud.com/histomap/civ-tab/BM.png',  17, 1),
(18, '南美',   'NM',  '#D4B098', 'https://pandahis-1300045339.cos.ap-chengdu.myqcloud.com/histomap/civ-tab/NM.png',  18, 1);

-- 临时 id -> 正式 id
UPDATE historical_unit SET civilization_l1_id = civilization_l1_id - 1000
WHERE civilization_l1_id BETWEEN 1001 AND 1018;

UPDATE historical_dynasty SET civilization_l1_id = civilization_l1_id - 1000
WHERE civilization_l1_id BETWEEN 1001 AND 1018;

SET FOREIGN_KEY_CHECKS = 1;
