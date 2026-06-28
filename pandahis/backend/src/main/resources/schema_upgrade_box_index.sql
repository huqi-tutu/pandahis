-- historical_box 重构：对齐 data/史略索引_01至02.json
-- 执行: python scripts/import_box_index_json.py

-- 1) 清空依赖旧 box_id 的子表与用户记录
DELETE FROM box_graph_edge;
DELETE FROM box_graph_node;
DELETE FROM box_critique;
DELETE FROM box_relic;
DELETE FROM user_favorite_box;
DELETE FROM user_footprint;

-- 2) 解除子表对 historical_box 的外键（若存在）
-- （由 import_box_index_json.py 按 information_schema 动态处理）

-- 3) 重建 historical_box
DROP TABLE IF EXISTS historical_box;

CREATE TABLE historical_box (
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='史略';
