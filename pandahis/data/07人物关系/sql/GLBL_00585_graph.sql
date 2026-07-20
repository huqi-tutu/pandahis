DELETE FROM box_graph_edge WHERE box_id='GLBL_00585';
DELETE FROM box_graph_node WHERE box_id='GLBL_00585';
INSERT INTO box_graph_node (component_id, shilue_id, shilue_name, box_id, node_key, node_type, name, extra_json) VALUES ('GLBL_00585_REL_center', 'GLBL_00585', '许由', 'GLBL_00585', 'center', 'event', '许由', '{}');
INSERT INTO box_graph_node (component_id, shilue_id, shilue_name, box_id, node_key, node_type, name, extra_json) VALUES ('GLBL_00585_REL_cat_col', 'GLBL_00585', '许由', 'GLBL_00585', 'cat_col', 'category', '同僚', '{"关系类别": "同僚", "isCategoryNode": true}');
INSERT INTO box_graph_edge (box_id, from_node_key, to_node_key, label) VALUES ('GLBL_00585', 'center', 'cat_col', '同僚');
INSERT INTO box_graph_node (component_id, shilue_id, shilue_name, box_id, node_key, node_type, name, extra_json) VALUES ('GLBL_00585_REL_HD_COL_001', 'GLBL_00585', '许由', 'GLBL_00585', 'hd_col_001', 'person', '尧', '{"关系ID": "HD-COL-001", "关系类别": "同僚", "关系层级": "一级", "上级连接线标题": "君王", "关系简述": "尧欲禅天下于许由，许由不受，逃隐箕山。事见《庄子·逍遥游》。", "record_id": "rec14fd4b90c119"}');
INSERT INTO box_graph_edge (box_id, from_node_key, to_node_key, label) VALUES ('GLBL_00585', 'cat_col', 'hd_col_001', '君王');
