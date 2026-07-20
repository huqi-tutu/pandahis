DELETE FROM box_graph_edge WHERE box_id='GLBL_00575';
DELETE FROM box_graph_node WHERE box_id='GLBL_00575';
INSERT INTO box_graph_node (component_id, shilue_id, shilue_name, box_id, node_key, node_type, name, extra_json) VALUES ('GLBL_00575_REL_center', 'GLBL_00575', '嫫母', 'GLBL_00575', 'center', 'event', '嫫母', '{}');
INSERT INTO box_graph_node (component_id, shilue_id, shilue_name, box_id, node_key, node_type, name, extra_json) VALUES ('GLBL_00575_REL_cat_fam', 'GLBL_00575', '嫫母', 'GLBL_00575', 'cat_fam', 'category', '家庭', '{"关系类别": "家庭", "isCategoryNode": true}');
INSERT INTO box_graph_edge (box_id, from_node_key, to_node_key, label) VALUES ('GLBL_00575', 'center', 'cat_fam', '家庭');
INSERT INTO box_graph_node (component_id, shilue_id, shilue_name, box_id, node_key, node_type, name, extra_json) VALUES ('GLBL_00575_REL_HD_FAM_001', 'GLBL_00575', '嫫母', 'GLBL_00575', 'hd_fam_001', 'person', '黄帝', '{"关系ID": "HD-FAM-001", "关系类别": "家庭", "关系层级": "一级", "上级连接线标题": "丈夫", "关系简述": "黄帝次妃，貌丑德充，助治后宫，见《吕氏春秋·遇合》。", "record_id": "rec810855c193eb"}');
INSERT INTO box_graph_edge (box_id, from_node_key, to_node_key, label) VALUES ('GLBL_00575', 'cat_fam', 'hd_fam_001', '丈夫');
