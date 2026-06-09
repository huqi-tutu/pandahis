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
  id VARCHAR(32) PRIMARY KEY,
  civilization_l1_id BIGINT NOT NULL,
  name VARCHAR(128) NOT NULL,
  start_year INT NULL,
  end_year INT NULL,
  start_year_raw VARCHAR(32) NULL,
  end_year_raw VARCHAR(32) NULL,
  sort_order INT NOT NULL DEFAULT 0,
  status TINYINT NOT NULL DEFAULT 1,
  CONSTRAINT fk_dynasty_civ FOREIGN KEY (civilization_l1_id) REFERENCES civilization_l1 (id)
);

CREATE TABLE IF NOT EXISTS historical_unit (
  id VARCHAR(64) PRIMARY KEY,
  name VARCHAR(128) NOT NULL,
  ruler_name VARCHAR(64) NULL,
  dynasty_name VARCHAR(64),
  dynasty_id VARCHAR(32) NULL,
  era_name VARCHAR(64),
  temple_name VARCHAR(64) NULL,
  era_title VARCHAR(64) NULL,
  civilization_l1_id BIGINT NOT NULL,
  start_year INT NOT NULL,
  end_year INT NOT NULL,
  duration_years INT NOT NULL,
  importance_level TINYINT NULL,
  core_topics_json TEXT,
  summary TEXT,
  notes TEXT NULL,
  card_image_url VARCHAR(512),
  status TINYINT NOT NULL DEFAULT 1,
  CONSTRAINT fk_unit_dynasty FOREIGN KEY (dynasty_id) REFERENCES historical_dynasty (id),
  CONSTRAINT fk_unit_civ FOREIGN KEY (civilization_l1_id) REFERENCES civilization_l1 (id)
);

CREATE TABLE IF NOT EXISTS app_kv (
  k VARCHAR(64) PRIMARY KEY,
  v TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS historical_box (
  id VARCHAR(128) PRIMARY KEY,
  business_code VARCHAR(32) NULL,
  unit_id VARCHAR(64) NOT NULL,
  subject_unit_id VARCHAR(64) NULL,
  dynasty_id VARCHAR(32) NULL,
  title VARCHAR(128) NOT NULL,
  category_key VARCHAR(16) NOT NULL,
  shilue_kind VARCHAR(16) NULL,
  blurb VARCHAR(64) NULL,
  start_year INT,
  end_year INT,
  importance_level TINYINT,
  priority_code VARCHAR(8) NULL,
  priority_reason TEXT NULL,
  status TINYINT NOT NULL DEFAULT 1,
  detail_md TEXT,
  detail_md_flash TEXT NULL,
  detail_md_pro TEXT NULL,
  original_ref_json TEXT,
  UNIQUE KEY uk_historical_box_business_code (business_code),
  CONSTRAINT fk_box_unit FOREIGN KEY (unit_id) REFERENCES historical_unit (id),
  CONSTRAINT fk_box_subject_unit FOREIGN KEY (subject_unit_id) REFERENCES historical_unit (id),
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
