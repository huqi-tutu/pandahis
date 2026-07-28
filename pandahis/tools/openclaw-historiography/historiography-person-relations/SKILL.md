---
name: historiography-person-relations
description: >
  人物史略关系数据补全（家庭/同僚/师从/外敌/好友）。按 GLBL 或朝代批量产出 JSON 至 data/07人物关系/。
  与 historiography-dynasty-knowledge、historiography-translate 独立。激活词：人物关系、关系补全、关系表、07人物关系。
origin: ECC
---

# 人物关系补全工作流

## 与相邻模块的关系

| 模块 | 职责 | 产出 |
|------|------|------|
| **historiography-annotate** | 一期卷级人物标注 | 03 索引 |
| **historiography-dynasty-knowledge** | 朝代知识 + 人物详情 | 06 详情 |
| **historiography-translate** | 史略译文 | 04 史料翻译 |
| **historiography-person-relations**（本 skill） | **人物关系图谱** | **07 人物关系** |

**禁止**为非人物类史略（事略 / 典制 / 论著 / 蕃祚）建关系表。

## When to Activate

- 用户要求补全**特定人物**或**某朝代人物**的关系数据
- 用户提到「人物关系」「关系表」「07人物关系」「关系图谱 JSON」
- 用户指定 `@data/07人物关系` 或引用 `黄帝关系表.json` 格式

## 规范 SSOT（必读顺序）

| 顺序 | 文档 | 用途 |
|------|------|------|
| 1 | [`../../../关系数据整理提示词.md`](../../../关系数据整理提示词.md) | **关系 taxonomy 唯一权威**（四类、层级、停止规则） |
| 2 | [`reference/schema.md`](reference/schema.md) | JSON 字段、边标签、`所属*关系` 链式写法 |
| 3 | [`reference/execution-discipline.md`](reference/execution-discipline.md) | ECC 执行纪律（逐人、verify 门禁） |
| 4 | [`../../../data/07人物关系/黄帝关系表.json`](../../../data/07人物关系/黄帝关系表.json) | **格式样例**（类别名以 SSOT 为准，见 schema 迁移说明） |

动笔前 **必须先读 SSOT #1**；禁止只读本 SKILL 摘要。

## 路径（相对 `HISTOGRAPH_ROOT` = `pandahis/pandahis`）

| 用途 | 路径 |
|------|------|
| **正式产出** | `data/07人物关系/` |
| 单人物文件 | `data/07人物关系/{关联史略名称}关系表.json` |
| 人物索引 / GLBL | `data/03索引标注条目/史略索引_01至02.json` |
| 人物详情（grounding） | `data/04史料翻译/`、`data/06朝代知识补全/详情/` |
| 校验脚本 | `tools/openclaw-historiography/historiography-person-relations/scripts/verify_relations.py` |
| 导入脚本 | `tools/openclaw-historiography/historiography-person-relations/scripts/import_relations_lib.py` |

> `07` 与 `03/04/06` 隔离，专用于人物关系 JSON；入库 `box_graph_*` 另走 import 流程（待接）。

## 执行清单（每人必做）

```
Task Progress:
- [ ] 1. 确认目标为人物类史略（君王/宗戚/文臣/武将/宦官/庶众）
- [ ] 2. 读取 SSOT + schema；读该人物详情/译文作 grounding
- [ ] 3. relations.py compose-one（DeepSeek v4 Pro 成稿）
- [ ] 4. verify_relations.py --strict
- [ ] 5. relations.py import-one（或 compose-one --sync）写入 box_graph_*
- [ ] 6. （可选）更新批次 manifest
```

**端到端**：`compose-one --sync` = 成稿 + verify + 入库一步完成。

**禁止**一次 prompt 批量混写多人物；**禁止**跳过 verify / import。

## 单人物补全

1. 解析输入：`GLBL_00149` / `黄帝` / 二者之一即可。
2. 在 `03索引标注条目` 确认 `category_key` 为人物六类之一。
3. 读 `04` 或 `06/详情` 中该人物 `翻译详情`。
4. 依 taxonomy 填四类关系；路径**最多四级**（见 SSOT）。
5. 输出 `{关联史略名称}关系表.json`。
6. 运行 verify（见下）。

## 朝代批量补全

1. 从索引筛出该朝代 + 人物六类条目清单。
2. **逐人串行**：每人走「单人物补全」全流程 + verify。
3. 可选：写 `data/07人物关系/{朝代}_关系补全_manifest.json` 记录 GLBL、文件名、条数、verify 时间。

```json
{
  "dynasty": "五帝",
  "completed": [
    { "glbl": "GLBL_00149", "name": "黄帝", "file": "黄帝关系表.json", "count": 18, "verified_at": "2026-07-19" }
  ]
}
```

## 命令

```bash
export HISTOGRAPH_ROOT=/path/to/pandahis/pandahis
cd tools/openclaw-historiography/historiography-person-relations/scripts

# 测试 DeepSeek v4 Pro 连通（固定 deepseek-v4-pro）
python3 relations.py test-llm

# 补全单人物（成稿 + 入库一步）
python3 relations.py compose-one --id GLBL_00149 --sync --sql-out /tmp/huangdi_graph.sql

# 仅导入已有 JSON
python3 relations.py import-one --name 黄帝
python3 relations.py import-all --sql-out /tmp/graph_sql/

# 只看 prompt（不调 LLM）
python3 relations.py compose-one --id GLBL_00149 --dry-run

# 朝代批量（逐人串行，--max 控制人数）
python3 relations.py compose --dynasty 五帝 --max 3

# 校验
python3 relations.py verify --name 黄帝
python3 verify_relations.py --strict "$HISTOGRAPH_ROOT/data/07人物关系/黄帝关系表.json"
```

**LLM 通道（强制）**：脚本启动时设 `HIST_LLM_PROVIDER=deepseek`、`DEEPSEEK_MODEL=deepseek-v4-pro`，经 `llm.provider.run_agent_turn` 调用；**不会**走 Cursor 对话模型。

## LLM 纪律
- **固定** `DEEPSEEK_MODEL=deepseek-v4-pro`（脚本内强制，见 `relations_lib.ensure_deepseek_v4_pro`）。
- **Cursor 对话补全已弃用**；请用 `relations.py compose-one`。
- 无史料不编造；`关系简述` 须可追溯到文献或项目已有详情。
- 完成后 **必须** 跑 verify；Critical 级错误不得入库。

## 输出质量门禁

verify 通过标准见 `reference/execution-discipline.md`。摘要：

- `关系类别` ∈ {家庭, 同僚, 师从, 外敌, 好友}
- `关系层级` ∈ {一级, 二级, 三级, 四级}（**禁止五级**）
- 同一文件内 `关联史略名称` 一致
- `关系ID` 唯一；`所属*关系` 链与层级一致
- 同僚·外敌 判类不混（见 SSOT §二、§四）

## 附加资源

- JSON 字段与边标签映射 → [reference/schema.md](reference/schema.md)
- ECC 执行纪律 → [reference/execution-discipline.md](reference/execution-discipline.md)
