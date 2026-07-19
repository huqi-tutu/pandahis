-- 盒子组件表对齐：每条关联 / 评述 / 见证记录具备全局唯一 component_id，并冗余史略ID与史略名称。
-- 执行前请备份。MySQL 8+。若列/索引已存在可忽略对应报错。
-- 约定：box_id 与 shilue_id 同值，均指向 historical_box.id（史略ID）。

-- ── 关联节点 box_graph_node ──
ALTER TABLE box_graph_node
  ADD COLUMN component_id VARCHAR(64) NULL COMMENT '组件ID（全局唯一）' AFTER id,
  ADD COLUMN shilue_id VARCHAR(128) NULL COMMENT '史略ID' AFTER component_id,
  ADD COLUMN shilue_name VARCHAR(128) NULL COMMENT '史略名称' AFTER shilue_id;

UPDATE box_graph_node n
JOIN historical_box b ON b.id = n.box_id
SET n.shilue_id = n.box_id,
    n.shilue_name = b.title,
    n.component_id = CONCAT(n.box_id, '_REL_', n.node_key)
WHERE n.component_id IS NULL;

ALTER TABLE box_graph_node
  MODIFY COLUMN component_id VARCHAR(64) NOT NULL COMMENT '组件ID（全局唯一）',
  MODIFY COLUMN shilue_id VARCHAR(128) NOT NULL COMMENT '史略ID',
  MODIFY COLUMN shilue_name VARCHAR(128) NOT NULL COMMENT '史略名称';

CREATE UNIQUE INDEX uk_box_graph_node_component_id ON box_graph_node (component_id);
CREATE INDEX idx_box_graph_node_shilue_id ON box_graph_node (shilue_id);

-- ── 评述 box_critique ──
ALTER TABLE box_critique
  ADD COLUMN component_id VARCHAR(64) NULL COMMENT '组件ID（全局唯一）' AFTER id,
  ADD COLUMN shilue_id VARCHAR(128) NULL COMMENT '史略ID' AFTER component_id,
  ADD COLUMN shilue_name VARCHAR(128) NULL COMMENT '史略名称' AFTER shilue_id;

UPDATE box_critique c
JOIN historical_box b ON b.id = c.box_id
SET c.shilue_id = c.box_id,
    c.shilue_name = b.title,
    c.component_id = CONCAT(c.box_id, '_CRIT_', LPAD(c.sort_order, 3, '0'))
WHERE c.component_id IS NULL;

ALTER TABLE box_critique
  MODIFY COLUMN component_id VARCHAR(64) NOT NULL COMMENT '组件ID（全局唯一）',
  MODIFY COLUMN shilue_id VARCHAR(128) NOT NULL COMMENT '史略ID',
  MODIFY COLUMN shilue_name VARCHAR(128) NOT NULL COMMENT '史略名称';

CREATE UNIQUE INDEX uk_box_critique_component_id ON box_critique (component_id);
CREATE INDEX idx_box_critique_shilue_id ON box_critique (shilue_id);

-- ── 见证 box_relic ──
ALTER TABLE box_relic
  ADD COLUMN component_id VARCHAR(64) NULL COMMENT '组件ID（全局唯一）' AFTER id,
  ADD COLUMN shilue_id VARCHAR(128) NULL COMMENT '史略ID' AFTER component_id,
  ADD COLUMN shilue_name VARCHAR(128) NULL COMMENT '史略名称' AFTER shilue_id;

UPDATE box_relic r
JOIN historical_box b ON b.id = r.box_id
SET r.shilue_id = r.box_id,
    r.shilue_name = b.title,
    r.component_id = CONCAT(r.box_id, '_RELIC_', LPAD(r.sort_order, 3, '0'))
WHERE r.component_id IS NULL;

ALTER TABLE box_relic
  MODIFY COLUMN component_id VARCHAR(64) NOT NULL COMMENT '组件ID（全局唯一）',
  MODIFY COLUMN shilue_id VARCHAR(128) NOT NULL COMMENT '史略ID',
  MODIFY COLUMN shilue_name VARCHAR(128) NOT NULL COMMENT '史略名称';

CREATE UNIQUE INDEX uk_box_relic_component_id ON box_relic (component_id);
CREATE INDEX idx_box_relic_shilue_id ON box_relic (shilue_id);
