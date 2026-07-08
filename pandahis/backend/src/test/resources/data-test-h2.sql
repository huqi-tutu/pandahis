INSERT INTO civilization_l1 (id, display_name, code, color_hex, sort_order, status)
VALUES (1, '华夏', 'HX', '#84572F', 1, 1);

INSERT INTO historical_dynasty (id, civilization_l1_id, civilization_name, civilization_code, name, start_year, end_year, sort_order, status)
VALUES ('dyn_song_hx', 1, '华夏', 'HX', '宋', 960, 1279, 10, 1);

INSERT INTO historical_regime (id, name, dynasty_id, dynasty_name, civilization_l1_id, civilization_name, start_year, end_year, sort_order, status)
VALUES ('regime_song_hx', '北宋', 'dyn_song_hx', '宋', 1, '华夏', 960, 1127, 1, 1);

INSERT INTO app_user (id, nickname, avatar_url, phone_e164)
VALUES (1, '测试用户', NULL, '+8613812345678');

INSERT INTO historical_emperor (id, name, dynasty_name, dynasty_id, regime_id, regime_name, era_name, civilization_l1_id, enthronement_year, abdication_year, reign_duration, importance_level, tags, status)
VALUES
  ('huaxia_song_shenzong', '宋神宗', '宋', 'dyn_song_hx', 'regime_song_hx', '北宋', '熙宁', 1, 1067, 1085, 18, 5, '["王安石变法","乌台诗案"]', 1),
  ('huaxia_song_zhezong', '宋哲宗', '宋', 'dyn_song_hx', 'regime_song_hx', '北宋', '元符', 1, 1085, 1100, 15, 4, '[]', 1);

INSERT INTO historical_box (
  id, emperor_id, regime_id, dynasty_id, civilization_code, title, category_key, blurb,
  start_year, end_year, priority_code, priority_reason, importance_level,
  peak_year, peak_reason, peak_type, status, detail_md, original_ref_json
)
VALUES
  ('box_wutai_1079', 'huaxia_song_shenzong', 'regime_song_hx', 'dyn_song_hx', 'HX', '乌台诗案', 'shilue', '文字狱', 1079, 1079, 'P0', '测试优先级', 0, 1079, '乌台诗案发生', 'event_climax', 1, '苏轼文字狱。', '{}'),
  ('box_bianfa', 'huaxia_song_shenzong', 'regime_song_hx', 'dyn_song_hx', 'HX', '熙宁变法', 'dianzhi', '变法', 1069, 1076, 'P0', '测试优先级', 0, 1069, '变法开始', 'reform_start', 1, '变法概述。', '{}');

INSERT INTO box_graph_node (box_id, node_key, node_type, name, extra_json)
VALUES ('box_wutai_1079', 'person_sushi', 'person', '苏轼', '{"category":"人物","role":"主角","level":"一级","lineage":"父亲 · 苏洵","summary":"北宋文学家苏轼。"}');

INSERT INTO user_footprint (user_id, box_id, last_viewed_at, view_count)
VALUES
  (1, 'box_wutai_1079', TIMESTAMP '2026-06-01 10:00:00', 2),
  (1, 'box_bianfa', TIMESTAMP '2026-06-02 11:00:00', 1);

INSERT INTO search_hot_keyword (keyword, is_hot, sort_order, status)
VALUES ('乌台诗案', 1, 1, 1);
