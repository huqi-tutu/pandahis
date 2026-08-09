# historiography-annotate（共享脚本与规则）

本目录**不是** Agent 激活入口，而是 v2 标注流水线的**共享基础设施**：

- Step 2–4：`check_format.py`、`fill_fields.py`、`peak_year.py`、`person_tag.py` 等
- 规则 SSOT：`reference/`（峰值年、人物标签、格式规范、异名表等）
- 翻译 / 朝代补全等模块亦引用本目录规则与工具

**史料标注 Agent 入口（唯一）**：

- Step 1/4 细则 → [`../historiography-annotate-v2/SKILL.md`](../historiography-annotate-v2/SKILL.md)
- 批量调度 → [`../historiography-pipeline-v2/SKILL.md`](../historiography-pipeline-v2/SKILL.md)

老版 v1 Agent Skill（`SKILL.md`）已移除；`data/03` 历史索引仍只读保留。
