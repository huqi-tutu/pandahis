CREATE TABLE IF NOT EXISTS app_user (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  nickname VARCHAR(64) NOT NULL,
  avatar_url VARCHAR(512),
  phone_e164 VARCHAR(20),
  wx_openid VARCHAR(64) NULL,
  wx_unionid VARCHAR(64) NULL,
  last_login_at TIMESTAMP NULL,
  read_balance INT NOT NULL DEFAULT 0,
  UNIQUE KEY uk_app_user_wx_openid (wx_openid),
  UNIQUE KEY uk_app_user_wx_unionid (wx_unionid)
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

