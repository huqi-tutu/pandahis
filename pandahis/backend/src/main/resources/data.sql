-- 一级地域 18 条（与 2026-05 文明 tab 配图素材一致）；code 与 Excel「文明 ID」列对齐便于导入
INSERT INTO civilization_l1 (id, display_name, code, color_hex, tab_image_url, sort_order, status) VALUES
(1, '华夏', 'HX', '#84572F', 'https://pandahis-1300045339.cos.ap-chengdu.myqcloud.com/histomap/civ-tab/HX.png', 1, 1),
(2, '朝鲜', 'CX', '#9ABCC8', 'https://pandahis-1300045339.cos.ap-chengdu.myqcloud.com/histomap/civ-tab/CX.png', 2, 1),
(3, '日本', 'RB', '#EDD5C0', 'https://pandahis-1300045339.cos.ap-chengdu.myqcloud.com/histomap/civ-tab/RB.png', 3, 1),
(4, '东南亚', 'DNY', '#92ADA4', 'https://pandahis-1300045339.cos.ap-chengdu.myqcloud.com/histomap/civ-tab/DNY.png', 4, 1),
(5, '中亚', 'ZY', '#C4A882', 'https://pandahis-1300045339.cos.ap-chengdu.myqcloud.com/histomap/civ-tab/ZY.png', 5, 1),
(6, '北亚', 'BY', '#8B9EB5', 'https://pandahis-1300045339.cos.ap-chengdu.myqcloud.com/histomap/civ-tab/BY.png', 6, 1),
(7, '南亚', 'NY', '#E0C088', 'https://pandahis-1300045339.cos.ap-chengdu.myqcloud.com/histomap/civ-tab/NY.png', 7, 1),
(8, '西亚', 'XY', '#D4B098', 'https://pandahis-1300045339.cos.ap-chengdu.myqcloud.com/histomap/civ-tab/XY.png', 8, 1),
(9, '南欧', 'NO', '#92ADA4', 'https://pandahis-1300045339.cos.ap-chengdu.myqcloud.com/histomap/civ-tab/NO.png', 9, 1),
(10, '东欧', 'DO', '#9ABCC8', 'https://pandahis-1300045339.cos.ap-chengdu.myqcloud.com/histomap/civ-tab/DO.png', 10, 1),
(11, '西欧', 'XO', '#B3D9E0', 'https://pandahis-1300045339.cos.ap-chengdu.myqcloud.com/histomap/civ-tab/XO.png', 11, 1),
(12, '北欧', 'BO', '#A8C4D4', 'https://pandahis-1300045339.cos.ap-chengdu.myqcloud.com/histomap/civ-tab/BO.png', 12, 1),
(13, '北非', 'BF', '#F1A805', 'https://pandahis-1300045339.cos.ap-chengdu.myqcloud.com/histomap/civ-tab/BF.png', 13, 1),
(14, '西非', 'XF', '#84572F', 'https://pandahis-1300045339.cos.ap-chengdu.myqcloud.com/histomap/civ-tab/XF.png', 14, 1),
(15, '东非', 'DF', '#B8956A', 'https://pandahis-1300045339.cos.ap-chengdu.myqcloud.com/histomap/civ-tab/DF.png', 15, 1),
(16, '中美', 'ZM', '#F2D6A1', 'https://pandahis-1300045339.cos.ap-chengdu.myqcloud.com/histomap/civ-tab/ZM.png', 16, 1),
(17, '北美', 'BM', '#7F96B8', 'https://pandahis-1300045339.cos.ap-chengdu.myqcloud.com/histomap/civ-tab/BM.png', 17, 1),
(18, '南美', 'NM', '#D4B098', 'https://pandahis-1300045339.cos.ap-chengdu.myqcloud.com/histomap/civ-tab/NM.png', 18, 1)
ON DUPLICATE KEY UPDATE display_name=VALUES(display_name), code=VALUES(code), color_hex=VALUES(color_hex), tab_image_url=VALUES(tab_image_url), sort_order=VALUES(sort_order), status=VALUES(status);

INSERT INTO historical_dynasty (id, civilization_l1_id, name, start_year, end_year, start_year_raw, end_year_raw, sort_order, status)
VALUES ('dyn_song_hx', 1, '宋', 960, 1279, '960', '1279', 10, 1),
       ('dyn_goryeo', 2, '高丽', 918, 1392, '918', '1392', 1, 1)
ON DUPLICATE KEY UPDATE name=VALUES(name), civilization_l1_id=VALUES(civilization_l1_id), start_year=VALUES(start_year), end_year=VALUES(end_year), sort_order=VALUES(sort_order), status=VALUES(status);

INSERT INTO app_user (id, nickname, avatar_url, phone_e164)
VALUES (1, '测试用户', NULL, '+8613812345678')
ON DUPLICATE KEY UPDATE nickname=VALUES(nickname), avatar_url=VALUES(avatar_url), phone_e164=VALUES(phone_e164);

INSERT INTO historical_unit (id, name, ruler_name, dynasty_name, dynasty_id, era_name, temple_name, era_title, civilization_l1_id, start_year, end_year, duration_years, importance_level, core_topics_json, summary, notes, status)
VALUES ('huaxia_song_shenzong', '宋神宗', '赵顼', '宋', 'dyn_song_hx', '熙宁 · 元丰', NULL, NULL, 1, 1067, 1085, 18, 5, '["王安石变法","乌台诗案"]', '宋神宗赵顼（1048—1085），在位期间推行熙宁变法。', NULL, 1)
ON DUPLICATE KEY UPDATE name=VALUES(name), ruler_name=VALUES(ruler_name), dynasty_name=VALUES(dynasty_name), dynasty_id=VALUES(dynasty_id), era_name=VALUES(era_name), temple_name=VALUES(temple_name), era_title=VALUES(era_title), civilization_l1_id=VALUES(civilization_l1_id),
  start_year=VALUES(start_year), end_year=VALUES(end_year), duration_years=VALUES(duration_years), importance_level=VALUES(importance_level), core_topics_json=VALUES(core_topics_json), summary=VALUES(summary), notes=VALUES(notes), status=VALUES(status);

INSERT INTO historical_unit (id, name, ruler_name, dynasty_name, dynasty_id, era_name, temple_name, era_title, civilization_l1_id, start_year, end_year, duration_years, importance_level, core_topics_json, summary, notes, status)
VALUES ('huaxia_song_zhezong', '宋哲宗', '赵煦', '宋', 'dyn_song_hx', '元符', NULL, NULL, 1, 1085, 1100, 15, 4, '[]', '宋哲宗赵煦，神宗之子。用于演示「下一朝代」同地域时间线。', NULL, 1)
ON DUPLICATE KEY UPDATE name=VALUES(name), ruler_name=VALUES(ruler_name), dynasty_name=VALUES(dynasty_name), dynasty_id=VALUES(dynasty_id), era_name=VALUES(era_name), temple_name=VALUES(temple_name), era_title=VALUES(era_title), civilization_l1_id=VALUES(civilization_l1_id),
  start_year=VALUES(start_year), end_year=VALUES(end_year), duration_years=VALUES(duration_years), importance_level=VALUES(importance_level), core_topics_json=VALUES(core_topics_json), summary=VALUES(summary), notes=VALUES(notes), status=VALUES(status);

INSERT INTO historical_unit (id, name, ruler_name, dynasty_name, dynasty_id, era_name, temple_name, era_title, civilization_l1_id, start_year, end_year, duration_years, importance_level, core_topics_json, summary, notes, status)
VALUES ('chaoxian_demo_king', '高丽宣宗', '王运', '高丽', 'dyn_goryeo', '-', NULL, NULL, 2, 1083, 1094, 11, 3, '[]', '演示跨地域「年份相近」推荐用占位数据。', NULL, 1)
ON DUPLICATE KEY UPDATE name=VALUES(name), ruler_name=VALUES(ruler_name), dynasty_name=VALUES(dynasty_name), dynasty_id=VALUES(dynasty_id), era_name=VALUES(era_name), temple_name=VALUES(temple_name), era_title=VALUES(era_title), civilization_l1_id=VALUES(civilization_l1_id),
  start_year=VALUES(start_year), end_year=VALUES(end_year), duration_years=VALUES(duration_years), importance_level=VALUES(importance_level), core_topics_json=VALUES(core_topics_json), summary=VALUES(summary), notes=VALUES(notes), status=VALUES(status);

INSERT INTO historical_box (id, business_code, unit_id, subject_unit_id, dynasty_id, title, category_key, shilue_kind, blurb, start_year, end_year, importance_level, priority_code, priority_reason, status, detail_md, detail_md_flash, detail_md_pro, original_ref_json)
VALUES ('box_wutai_1079', NULL, 'huaxia_song_shenzong', NULL, NULL, '乌台诗案', 'shilue', NULL, '文字狱风波节点', 1079, 1079, 5, NULL, NULL, 1, '苏轼在湖州的谢表被弹劾，引发文字狱风波。', NULL, NULL, '{"title":"24史原文对照","items":[{"work":"宋史","chapter":"苏轼传","url":"https://example.com"}]}')
ON DUPLICATE KEY UPDATE title=VALUES(title), category_key=VALUES(category_key), shilue_kind=VALUES(shilue_kind), blurb=VALUES(blurb), start_year=VALUES(start_year), end_year=VALUES(end_year), importance_level=VALUES(importance_level), status=VALUES(status),
  detail_md=VALUES(detail_md), original_ref_json=VALUES(original_ref_json);

INSERT INTO box_graph_node (box_id, node_key, node_type, name, extra_json)
VALUES ('box_wutai_1079','event_wutai','event','乌台诗案','{}'),
       ('box_wutai_1079','person_sushi','person','苏轼','{"targetBoxId":"box_wutai_1079"}')
ON DUPLICATE KEY UPDATE node_type=VALUES(node_type), name=VALUES(name), extra_json=VALUES(extra_json);

INSERT INTO box_graph_edge (box_id, from_node_key, to_node_key, label)
VALUES ('box_wutai_1079','event_wutai','person_sushi','主角');

INSERT INTO box_critique (box_id, title, author, era_text, year_value, content, source, blurb, sort_order)
VALUES ('box_wutai_1079','党议与诗案','朱熹','南宋 · 1200',1200,'轼之狱，非为诗也，为党议也……','《朱子语类》卷一三一','朱熹论乌台诗案性质',1);

INSERT INTO box_relic (box_id, name, image_url, summary, description, museum, priority_code, priority_reason, sort_order)
VALUES ('box_wutai_1079','黄州寒食帖','https://example.com/relics/hs.jpg','苏轼黄州第三年寒食','苏轼被贬黄州第三年寒食节所写。','台北故宫博物院','P0',NULL,1),
       ('box_wutai_1079','相关文书（示例）',NULL,'制度与文本','制度与文本证据占位。','馆藏待补充','P2',NULL,2),
       ('box_wutai_1079','碑刻（示例）',NULL,'碑刻见证','见证条目最多 3 条（PRD）。','馆藏待补充','P2',NULL,3);

INSERT INTO search_hot_keyword (keyword, is_hot, sort_order, status)
VALUES ('王安石变法', 1, 1, 1),
       ('文艺复兴', 1, 2, 1),
       ('乌台诗案', 1, 3, 1),
       ('唐玄宗', 0, 4, 1),
       ('奥斯曼帝国', 0, 5, 1),
       ('玛雅', 0, 6, 1),
       ('郑和下西洋', 0, 7, 1),
       ('宋神宗', 0, 8, 1),
       ('苏轼', 0, 9, 1),
       ('贞观之治', 0, 10, 1);

INSERT INTO membership_plan (id, name, price_cent, duration_days, is_default, tag_text, benefits_json, status)
VALUES
  ('month','月度',990,30,0,NULL,'["解锁评述","解锁见证","原文对照"]',1),
  ('quarter','季度',1990,90,0,NULL,'["解锁评述","解锁见证","原文对照"]',1),
  ('year','年度',4990,365,1,'最划算','["解锁评述","解锁见证","原文对照"]',1)
ON DUPLICATE KEY UPDATE name=VALUES(name), price_cent=VALUES(price_cent), duration_days=VALUES(duration_days), is_default=VALUES(is_default), tag_text=VALUES(tag_text), benefits_json=VALUES(benefits_json), status=VALUES(status);
