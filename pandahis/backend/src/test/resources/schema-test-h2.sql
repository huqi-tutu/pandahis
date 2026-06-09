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
  name VARCHAR(128) NOT NULL,
  start_year INT NULL,
  end_year INT NULL,
  sort_order INT NOT NULL DEFAULT 0,
  status TINYINT NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS historical_unit (
  id VARCHAR(64) PRIMARY KEY,
  name VARCHAR(128) NOT NULL,
  ruler_name VARCHAR(64) NULL,
  dynasty_name VARCHAR(64),
  dynasty_id VARCHAR(32) NULL,
  era_name VARCHAR(64),
  civilization_l1_id BIGINT NOT NULL,
  start_year INT NOT NULL,
  end_year INT NOT NULL,
  duration_years INT NOT NULL,
  importance_level TINYINT NULL,
  core_topics_json TEXT,
  summary TEXT,
  card_image_url VARCHAR(512) NULL,
  status TINYINT NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS historical_box (
  id VARCHAR(128) PRIMARY KEY,
  unit_id VARCHAR(64) NOT NULL,
  title VARCHAR(128) NOT NULL,
  category_key VARCHAR(16) NOT NULL,
  blurb VARCHAR(64) NULL,
  start_year INT,
  end_year INT,
  importance_level TINYINT,
  status TINYINT NOT NULL DEFAULT 1,
  detail_md TEXT,
  original_ref_json TEXT
);

CREATE TABLE IF NOT EXISTS box_graph_node (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  box_id VARCHAR(128) NOT NULL,
  node_key VARCHAR(64) NOT NULL,
  node_type VARCHAR(16) NOT NULL,
  name VARCHAR(64) NOT NULL,
  extra_json TEXT,
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
