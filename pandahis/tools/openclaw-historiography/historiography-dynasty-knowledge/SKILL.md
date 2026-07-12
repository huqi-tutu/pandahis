---
name: historiography-dynasty-knowledge
description: >
  朝代知识补全（事略/典制/论著）。与 historiography-annotate（二十四史卷级人物标注）完全独立。
  按朝代 + LLM 史学共识补全，不经著作抽取。激活词：朝代补全、事略补全、典制补全、论著补全。
---

# 朝代知识补全工作流

## 与标注流水线的关系

| 模块 | 职责 | 输入 |
|------|------|------|
| **historiography-annotate** | 一期：人物七类，从二十四史卷抽取 | 著作 + 卷 |
| **historiography-dynasty-knowledge**（本 skill） | 二期：事略 / 典制 / 论著，按朝代 LLM 补全 | 朝代 |

**禁止**在标注 skill 中引用本目录 `reference/`；**禁止**在本 skill 中跑 Step1 卷级切块。

## When to Activate

- 用户要求为某朝代补全事略、典制、论著
- 用户提到「朝代知识」「二期补全」「dynasty supplement」
- 五帝等试点朝代的候选清单 / 入库

## 规范 SSOT（本目录）

| 文档 | 用途 |
|------|------|
| `reference/朝代知识补全总则.md` | 总纲与 Workflow |
| `reference/事略补全规则.md` | 事略五要素 |
| `reference/典制补全规则.md` | 典制准入 |
| `reference/典制与思想分界.md` | 典制 vs 思想权威分界 |
| `reference/论著补全规则.md` | 论著（含典籍/名篇/思想） |
| `reference/朝代补全格式规范.md` | JSON / GLBL 字段 |
| `reference/详情撰写规则.md` | 详情正文：仅下限、起承转合、风格 |
| `reference/执行纪律.md` | **三类分步、详情逐条、LLM 模型**（必读） |

共享（只读引用，不写入 annotate）：

- `historiography-compose/references/翻译规则.md` — 叙事风格 SSOT（继承）
- `historiography-annotate/reference/峰值年规则.md` — 峰值类型
- `historiography-annotate/reference/朝代优先级规则.md` — P0–P3

## LLM

与 `dynasty_priority.py` / `peak_year.py` **同通道**（`llm.provider` → DeepSeek）：

- `DEEPSEEK_MODEL=deepseek-v4-pro`（见 `tools/openclaw-historiography/.env`）

补全**创作**阶段遵守 `执行纪律.md`：三类分步、详情逐条；**不得**照搬 enrichment 默认批量（≤20 条/批）。

## 路径（相对 HISTOGRAPH_ROOT）

| 用途 | 路径 |
|------|------|
| 中间产物（研究/候选） | `data/05工作流中间产物/朝代知识补全/` |
| **正式产出根目录** | `data/06朝代知识补全/` |
| 索引条目 JSON | `data/06朝代知识补全/索引条目/` |
| 详情译文 JSON | `data/06朝代知识补全/详情/` |
| 朝代元数据 | `data/01历史坐标数据/朝代.json` |
| 并入目标 | `data/03索引标注条目/史略索引_01至02.json` |

> `06` 与 `03索引标注条目`、`04史料翻译` 隔离，专用于朝代知识补全（事略/典制/论著）的一步到位产出。

## 命令

```bash
cd historiography-dynasty-knowledge/scripts

# Step 1 研究报告
python3 dynasty_supplement.py --dynasty 五帝 --step research --dry-run

# Step 2–4 候选（每次仅一类，禁止三类同 prompt）
python3 dynasty_supplement.py --dynasty 五帝 --step candidates-shilue --dry-run
python3 dynasty_supplement.py --dynasty 五帝 --step candidates-dianzhi --dry-run
python3 dynasty_supplement.py --dynasty 五帝 --step candidates-lunzhu --dry-run

# Step 6 详情（每次仅一条）
python3 dynasty_supplement.py --dynasty 五帝 --step compose-detail --entry-id GLBL_00xxx --dry-run
```

**禁止** `--step all`。详见 `reference/执行纪律.md`。

## 入库

补全条目经 gate 后：

1. `append_dynasty_supplement.py` 将 `06/索引条目/` 并入 `史略索引_01至02.json`
2. `import_box_index_json.py` 导入 `historical_box`
3. 详情 JSON（`06/详情/`）导入 `historical_box_detail`（待实现专用 import）
