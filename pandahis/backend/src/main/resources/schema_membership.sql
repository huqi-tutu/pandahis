CREATE TABLE IF NOT EXISTS membership_plan (
  id VARCHAR(32) PRIMARY KEY,
  name VARCHAR(32) NOT NULL,
  price_cent INT NOT NULL,
  duration_days INT NOT NULL,
  is_default TINYINT NOT NULL DEFAULT 0,
  tag_text VARCHAR(32),
  benefits_json TEXT,
  status TINYINT NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS membership (
  user_id BIGINT PRIMARY KEY,
  start_at TIMESTAMP NOT NULL,
  end_at TIMESTAMP NOT NULL,
  status VARCHAR(16) NOT NULL
);

CREATE TABLE IF NOT EXISTS biz_order (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id BIGINT NOT NULL,
  plan_id VARCHAR(32) NOT NULL,
  amount_cent INT NOT NULL,
  status VARCHAR(16) NOT NULL,
  wx_prepay_id VARCHAR(128),
  wx_transaction_id VARCHAR(128),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  paid_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS payment_callback_log (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  order_id BIGINT NOT NULL,
  wx_transaction_id VARCHAR(128),
  payload_json TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (wx_transaction_id)
);

