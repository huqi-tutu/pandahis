-- 朝代收藏（与 user_favorite_box 史略收藏分离）
CREATE TABLE IF NOT EXISTS user_favorite_unit (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id BIGINT NOT NULL,
  unit_id VARCHAR(64) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (user_id, unit_id),
  CONSTRAINT fk_user_favorite_unit_user FOREIGN KEY (user_id) REFERENCES app_user (id),
  CONSTRAINT fk_user_favorite_unit_dynasty FOREIGN KEY (unit_id) REFERENCES historical_dynasty (id)
);
