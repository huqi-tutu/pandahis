INSERT INTO civilization_l1 (id, display_name, code, color_hex, sort_order, status)
VALUES (1, '华夏', 'HX', '#84572F', 1, 1);

INSERT INTO historical_dynasty (id, civilization_l1_id, name, start_year, end_year, sort_order, status)
VALUES ('dyn_song_hx', 1, '宋', 960, 1279, 10, 1);

INSERT INTO app_user (id, nickname, avatar_url, phone_e164)
VALUES (1, '测试用户', NULL, '+8613812345678');

INSERT INTO historical_unit (id, name, dynasty_name, dynasty_id, era_name, civilization_l1_id, start_year, end_year, duration_years, importance_level, core_topics_json, summary, status)
VALUES
  ('huaxia_song_shenzong', '宋神宗', '宋', 'dyn_song_hx', '熙宁', 1, 1067, 1085, 18, 5, '["王安石变法","乌台诗案"]', '宋神宗在位推行熙宁变法。', 1),
  ('huaxia_song_zhezong', '宋哲宗', '宋', 'dyn_song_hx', '元符', 1, 1085, 1100, 15, 4, '[]', '宋哲宗，神宗之子。', 1);

INSERT INTO historical_box (id, unit_id, title, category_key, blurb, start_year, end_year, importance_level, status, detail_md, original_ref_json)
VALUES
  ('box_wutai_1079', 'huaxia_song_shenzong', '乌台诗案', 'shilue', '文字狱', 1079, 1079, 5, 1, '苏轼文字狱。', '{}'),
  ('box_bianfa', 'huaxia_song_shenzong', '熙宁变法', 'dianzhi', '变法', 1069, 1076, 4, 1, '变法概述。', '{}');

INSERT INTO box_graph_node (box_id, node_key, node_type, name, extra_json)
VALUES ('box_wutai_1079', 'person_sushi', 'person', '苏轼', '{"category":"人物","role":"主角","level":"一级","lineage":"父亲 · 苏洵","summary":"北宋文学家苏轼。"}');

INSERT INTO user_footprint (user_id, box_id, last_viewed_at, view_count)
VALUES
  (1, 'box_wutai_1079', TIMESTAMP '2026-06-01 10:00:00', 2),
  (1, 'box_bianfa', TIMESTAMP '2026-06-02 11:00:00', 1);

INSERT INTO search_hot_keyword (keyword, is_hot, sort_order, status)
VALUES ('乌台诗案', 1, 1, 1);
