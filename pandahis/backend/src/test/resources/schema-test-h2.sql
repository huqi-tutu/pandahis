CREATE TABLE IF NOT EXISTS civilization_l1 (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  display_name VARCHAR(64) NOT NULL,
  code VARCHAR(16) NULL,
  color_hex CHAR(7) NOT NULL,
  tab_image_url VARCHAR(512) NULL,
  sort_order INT NOT NULL DEFAULT 0,
  status TINYINT NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS historical_dynasty (
  id VARCHAR(32) PRIMARY KEY,
  civilization_l1_id BIGINT NOT NULL,
  civilization_name VARCHAR(64) NULL,
  civilization_code VARCHAR(16) NULL,
  name VARCHAR(128) NOT NULL,
  start_year INT NULL,
  end_year INT NULL,
  start_year_raw VARCHAR(32) NULL,
  end_year_raw VARCHAR(32) NULL,
  sort_order INT NOT NULL DEFAULT 0,
  status TINYINT NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS historical_regime (
  id VARCHAR(128) PRIMARY KEY,
  name VARCHAR(128) NOT NULL,
  dynasty_id VARCHAR(64) NOT NULL,
  dynasty_name VARCHAR(128) NOT NULL,
  civilization_l1_id BIGINT NOT NULL,
  civilization_name VARCHAR(64) NULL,
  start_year INT NULL,
  end_year INT NULL,
  sort_order INT NOT NULL DEFAULT 0,
  status TINYINT NOT NULL DEFAULT 1
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
  era_name VARCHAR(64) NULL,
  enthronement_year INT NULL,
  abdication_year INT NULL,
  reign_duration INT NULL,
  importance_level TINYINT NULL,
  tags TEXT NULL,
  card_image_url VARCHAR(512) NULL,
  sort_order INT NOT NULL DEFAULT 0,
  status TINYINT NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS historical_box (
  id VARCHAR(128) PRIMARY KEY,
  emperor_id VARCHAR(128) NOT NULL,
  regime_id VARCHAR(128) NOT NULL,
  dynasty_id VARCHAR(64) NOT NULL,
  civilization_code VARCHAR(16) NOT NULL,
  title VARCHAR(128) NOT NULL,
  category_key VARCHAR(16) NOT NULL,
  blurb VARCHAR(64) NULL,
  start_year INT NOT NULL,
  end_year INT NOT NULL,
  priority_code VARCHAR(8),
  priority_reason TEXT,
  importance_level TINYINT,
  peak_year INT,
  peak_reason TEXT,
  peak_type VARCHAR(64),
  person_tag VARCHAR(64),
  entry_source VARCHAR(16) NOT NULL DEFAULT 'extract',
  status TINYINT NOT NULL DEFAULT 1,
  detail_md TEXT,
  original_ref_json TEXT
);

CREATE TABLE IF NOT EXISTS box_graph_node (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  component_id VARCHAR(64) NOT NULL,
  shilue_id VARCHAR(128) NOT NULL,
  shilue_name VARCHAR(128) NOT NULL,
  box_id VARCHAR(128) NOT NULL,
  node_key VARCHAR(64) NOT NULL,
  node_type VARCHAR(16) NOT NULL,
  name VARCHAR(64) NOT NULL,
  extra_json TEXT,
  UNIQUE (component_id),
  UNIQUE (box_id, node_key)
);

CREATE TABLE IF NOT EXISTS box_graph_edge (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  box_id VARCHAR(128) NOT NULL,
  from_node_key VARCHAR(64) NOT NULL,
  to_node_key VARCHAR(64) NOT NULL,
  label VARCHAR(32) NOT NULL
);

CREATE TABLE IF NOT EXISTS box_relic (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  component_id VARCHAR(64) NOT NULL,
  shilue_id VARCHAR(128) NOT NULL,
  shilue_name VARCHAR(128) NOT NULL,
  box_id VARCHAR(128) NOT NULL,
  name VARCHAR(128) NOT NULL,
  image_url VARCHAR(512),
  summary VARCHAR(256) NULL,
  description TEXT,
  museum VARCHAR(128),
  priority_code VARCHAR(8) NULL,
  sort_order INT NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS app_user (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  nickname VARCHAR(64) NOT NULL,
  avatar_url VARCHAR(512),
  phone_e164 VARCHAR(20),
  read_balance INT NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS user_favorite_box (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id BIGINT NOT NULL,
  box_id VARCHAR(128) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (user_id, box_id)
);

CREATE TABLE IF NOT EXISTS user_footprint (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id BIGINT NOT NULL,
  box_id VARCHAR(128) NOT NULL,
  last_viewed_at TIMESTAMP NOT NULL,
  view_count INT NOT NULL DEFAULT 1,
  UNIQUE (user_id, box_id)
);

CREATE TABLE IF NOT EXISTS user_reading_daily (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id BIGINT NOT NULL,
  read_date DATE NOT NULL,
  box_id VARCHAR(128) NOT NULL,
  UNIQUE (user_id, read_date, box_id)
);

CREATE TABLE IF NOT EXISTS user_box_read_completion (
  user_id BIGINT NOT NULL,
  box_id VARCHAR(128) NOT NULL,
  completed_at TIMESTAMP NOT NULL,
  PRIMARY KEY (user_id, box_id)
);

CREATE TABLE IF NOT EXISTS user_home_matrix_state (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id BIGINT NOT NULL,
  civilization_code VARCHAR(16) NOT NULL DEFAULT 'HX',
  last_dynasty_key VARCHAR(64) NULL,
  collapsed_dynasty_keys_json TEXT NULL,
  last_scroll_top_px INT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (user_id)
);

CREATE TABLE IF NOT EXISTS membership (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id BIGINT NOT NULL,
  status VARCHAR(16) NOT NULL,
  end_at TIMESTAMP NULL
);

CREATE TABLE IF NOT EXISTS search_hot_keyword (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  keyword VARCHAR(64) NOT NULL,
  is_hot TINYINT NOT NULL DEFAULT 0,
  sort_order INT NOT NULL DEFAULT 0,
  status TINYINT NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS app_kv (
  k VARCHAR(64) PRIMARY KEY,
  v TEXT NOT NULL
);
