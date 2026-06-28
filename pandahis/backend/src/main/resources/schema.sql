CREATE TABLE IF NOT EXISTS civilization_l1 (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  display_name VARCHAR(64) NOT NULL,
  code VARCHAR(16) NULL,
  color_hex CHAR(7) NOT NULL,
  tab_image_url VARCHAR(512) NULL,
  sort_order INT NOT NULL DEFAULT 0,
  status TINYINT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_civilization_l1_code (code)
);

CREATE TABLE IF NOT EXISTS historical_dynasty (
  id VARCHAR(64) PRIMARY KEY,
  civilization_l1_id BIGINT NOT NULL,
  civilization_name VARCHAR(64) NULL,
  civilization_code VARCHAR(16) NULL,
  name VARCHAR(128) NOT NULL,
  start_year INT NULL,
  end_year INT NULL,
  start_year_raw VARCHAR(32) NULL,
  end_year_raw VARCHAR(32) NULL,
  summary TEXT NULL COMMENT '朝代简介',
  sort_order INT NOT NULL DEFAULT 0,
  status TINYINT NOT NULL DEFAULT 1,
  CONSTRAINT fk_dynasty_civ FOREIGN KEY (civilization_l1_id) REFERENCES civilization_l1 (id)
);

CREATE TABLE IF NOT EXISTS historical_regime (
  id VARCHAR(128) PRIMARY KEY,
  name VARCHAR(128) NOT NULL,
  dynasty_id VARCHAR(64) NOT NULL,
  dynasty_name VARCHAR(128) NOT NULL,
  dynasty_zy VARCHAR(128) NULL,
  civilization_l1_id BIGINT NOT NULL,
  civilization_name VARCHAR(64) NULL,
  civilization_code VARCHAR(16) NULL,
  start_year INT NULL,
  end_year INT NULL,
  start_year_raw VARCHAR(32) NULL,
  end_year_raw VARCHAR(32) NULL,
  sort_order INT NOT NULL DEFAULT 0,
  status TINYINT NOT NULL DEFAULT 1,
  INDEX idx_regime_dynasty (dynasty_id),
  INDEX idx_regime_civ (civilization_l1_id),
  CONSTRAINT fk_regime_dynasty FOREIGN KEY (dynasty_id) REFERENCES historical_dynasty (id),
  CONSTRAINT fk_regime_civ FOREIGN KEY (civilization_l1_id) REFERENCES civilization_l1 (id)
);

CREATE TABLE IF NOT EXISTS historical_emperor (
  id VARCHAR(128) PRIMARY KEY,
  name VARCHAR(128) NOT NULL,
  ruler_name VARCHAR(64) NULL,
  regime_id VARCHAR(128) NOT NULL,
  regime_name VARCHAR(128) NOT NULL,
  dynasty_id VARCHAR(64) NOT NULL,
  dynasty_name VARCHAR(128) NOT NULL,
  civilization_l1_id BIGINT NOT NULL,
  civilization_name VARCHAR(64) NULL,
  civilization_code VARCHAR(16) NULL,
  temple_name VARCHAR(64) NULL,
  era_name VARCHAR(64) NULL,
  enthronement_year INT NULL,
  abdication_year INT NULL,
  enthronement_year_raw VARCHAR(32) NULL,
  abdication_year_raw VARCHAR(32) NULL,
  reign_duration INT NULL,
  importance_level TINYINT NULL,
  tags TEXT NULL,
  card_image_url VARCHAR(512) NULL,
  sort_order INT NOT NULL DEFAULT 0,
  status TINYINT NOT NULL DEFAULT 1,
  INDEX idx_emperor_regime (regime_id),
  INDEX idx_emperor_dynasty (dynasty_id),
  INDEX idx_emperor_civ (civilization_l1_id),
  CONSTRAINT fk_emperor_regime FOREIGN KEY (regime_id) REFERENCES historical_regime (id),
  CONSTRAINT fk_emperor_dynasty FOREIGN KEY (dynasty_id) REFERENCES historical_dynasty (id),
  CONSTRAINT fk_emperor_civ FOREIGN KEY (civilization_l1_id) REFERENCES civilization_l1 (id)
);

CREATE TABLE IF NOT EXISTS app_kv (
  k VARCHAR(64) PRIMARY KEY,
  v TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS historical_box (
  id VARCHAR(64) PRIMARY KEY COMMENT '史略ID',
  parent_entry_id VARCHAR(64) NULL COMMENT '母本史略ID',
  emperor_id VARCHAR(128) NOT NULL COMMENT '帝王ID',
  regime_id VARCHAR(128) NOT NULL COMMENT '政权ID',
  dynasty_id VARCHAR(64) NOT NULL COMMENT '朝代ID',
  civilization_code VARCHAR(16) NOT NULL COMMENT '文明ID',
  civilization_name VARCHAR(64) NULL COMMENT '一级文明坐标',
  dynasty_name VARCHAR(128) NULL COMMENT '二级朝代坐标',
  regime_name VARCHAR(128) NULL COMMENT '三级政权坐标',
  emperor_name VARCHAR(128) NULL COMMENT '四级帝王坐标',
  title VARCHAR(128) NOT NULL COMMENT '史略名称',
  category_key VARCHAR(16) NOT NULL COMMENT '史略分类编码',
  blurb VARCHAR(64) NULL COMMENT '史略简介',
  start_year INT NOT NULL COMMENT '史略开始年',
  end_year INT NOT NULL COMMENT '史略结束年',
  priority_code VARCHAR(8) NULL COMMENT '优先级 P0-P3',
  priority_reason TEXT NULL COMMENT '优先级判定理由',
  importance_level TINYINT NULL COMMENT '由优先级推导',
  primary_source VARCHAR(256) NULL COMMENT '主要史料出处',
  original_text TEXT NULL COMMENT '原文字句',
  original_location VARCHAR(128) NULL COMMENT '原文出处',
  fine_coordinate VARCHAR(128) NULL COMMENT '五级细坐标',
  paragraph_anchor VARCHAR(256) NULL COMMENT '六级段落锚点',
  parent_work VARCHAR(32) NULL COMMENT '母本著作',
  source_entry_count INT NULL COMMENT '来源条目数',
  paragraph_block_count INT NULL COMMENT '段落域数',
  paragraphs_json LONGTEXT NULL COMMENT 'paragraphs',
  merge_sources_json LONGTEXT NULL COMMENT '合并来源',
  source_works_json LONGTEXT NULL COMMENT '来源著作',
  original_ref_json LONGTEXT NULL COMMENT 'API 兼容原文引用',
  detail_md TEXT NULL,
  detail_md_flash TEXT NULL,
  detail_md_pro TEXT NULL,
  auto_filled TINYINT NULL COMMENT '自动补全年份',
  needs_llm TINYINT NULL COMMENT '待 LLM 补全',
  sort_order INT NOT NULL DEFAULT 0,
  status TINYINT NOT NULL DEFAULT 1,
  INDEX idx_box_parent_entry (parent_entry_id),
  INDEX idx_box_emperor (emperor_id),
  INDEX idx_box_regime (regime_id),
  INDEX idx_box_dynasty (dynasty_id),
  INDEX idx_box_category (category_key),
  CONSTRAINT fk_box_emperor FOREIGN KEY (emperor_id) REFERENCES historical_emperor (id),
  CONSTRAINT fk_box_regime FOREIGN KEY (regime_id) REFERENCES historical_regime (id),
  CONSTRAINT fk_box_dynasty FOREIGN KEY (dynasty_id) REFERENCES historical_dynasty (id)
);

CREATE TABLE IF NOT EXISTS box_graph_node (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  box_id VARCHAR(128) NOT NULL,
  node_key VARCHAR(64) NOT NULL,
  node_type VARCHAR(16) NOT NULL,
  name VARCHAR(64) NOT NULL,
  extra_json TEXT,
  UNIQUE (box_id, node_key),
  CONSTRAINT fk_graph_node_box FOREIGN KEY (box_id) REFERENCES historical_box (id)
);

CREATE TABLE IF NOT EXISTS box_graph_edge (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  box_id VARCHAR(128) NOT NULL,
  from_node_key VARCHAR(64) NOT NULL,
  to_node_key VARCHAR(64) NOT NULL,
  label VARCHAR(32) NOT NULL,
  CONSTRAINT fk_graph_edge_box FOREIGN KEY (box_id) REFERENCES historical_box (id)
);

CREATE TABLE IF NOT EXISTS box_critique (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  box_id VARCHAR(128) NOT NULL,
  title VARCHAR(128) NULL,
  author VARCHAR(64) NOT NULL,
  era_text VARCHAR(64) NOT NULL,
  year_value INT,
  content TEXT NOT NULL,
  source VARCHAR(256),
  blurb VARCHAR(256) NULL,
  sort_order INT NOT NULL DEFAULT 0,
  CONSTRAINT fk_critique_box FOREIGN KEY (box_id) REFERENCES historical_box (id)
);

CREATE TABLE IF NOT EXISTS box_relic (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  box_id VARCHAR(128) NOT NULL,
  name VARCHAR(128) NOT NULL,
  image_url VARCHAR(512),
  summary VARCHAR(256) NULL,
  description TEXT,
  museum VARCHAR(128),
  priority_code VARCHAR(8) NULL,
  priority_reason TEXT NULL,
  sort_order INT NOT NULL DEFAULT 0,
  CONSTRAINT fk_relic_box FOREIGN KEY (box_id) REFERENCES historical_box (id)
);

CREATE TABLE IF NOT EXISTS historical_box_detail (
  box_id VARCHAR(64) PRIMARY KEY COMMENT '史略ID',
  translate_detail LONGTEXT NOT NULL COMMENT '翻译详情',
  CONSTRAINT fk_box_detail_box FOREIGN KEY (box_id) REFERENCES historical_box (id)
);
