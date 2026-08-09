---
name: historiography-dynasty-knowledge
description: >
  朝代知识补全（事略/典制/论著/人物七类）。与 historiography-annotate-v2（二十四史卷级标注）完全独立。
  按朝代 + LLM 史学共识补全，不经著作抽取。激活词：朝代补全、事略补全、典制补全、论著补全、人物补全、帝王补全。
---

# 朝代知识补全工作流

## 与标注流水线的关系

| 模块 | 职责 | 输入 |
|------|------|------|
| **historiography-annotate-v2** | 卷级人物标注（v2 → data/10） | 著作 + 卷 |
| **historiography-dynasty-knowledge**（本 skill） | 二期：事略 / 典制 / 论著 + 人物缺口补全，按朝代 LLM 补全 | 朝代 |

**禁止**在标注 skill 中引用本目录 `reference/`；**禁止**在本 skill 中跑 Step1 卷级切块。

## When to Activate

- 用户要求为某朝代补全事略、典制、论著、**人物**
- 用户提到「朝代知识」「二期补全」「dynasty supplement」「人物补全」
- 五帝等试点朝代的候选清单 / 入库

## 规范 SSOT（本目录）

| 文档 | 用途 |
|------|------|
| `reference/朝代知识补全总则.md` | 总纲、Workflow、**§零 读者交付物** |
| `reference/事略补全规则.md` | 事略五要素 |
| `reference/典制补全规则.md` | 典制准入 |
| `reference/典制与思想分界.md` | 典制 vs 思想权威分界 |
| `reference/论著补全规则.md` | 论著（含典籍/名篇/思想） |
| `reference/朝代补全格式规范.md` | JSON / GLBL 字段 |
| `reference/人物补全规则.md` | 人物缺口补全、去重、六类边界 |
| `reference/详情写作_共用规范.md` | **§0 读者交付物**（《明朝那些事儿》文体、禁元叙述）+ compose 共用规范 |
| `reference/详情撰写规则.md` | 事略/典制/论著专属：起承转合、checklist |
| `reference/人物详情撰写规则.md` | 人物七类专属：六类侧重、记忆点 |
| `reference/附录/` | 示例反例、工作流、字数详表（人类参考，不进 prompt） |
| `reference/执行纪律.md` | **三类分步、详情逐条、LLM 模型**（必读） |
| `reference/维基底稿使用规范.md` | compose-detail 维基分层、条目坐标聚焦（必读） |

共享（只读引用，不写入 annotate）：

- `historiography-compose/references/翻译规则.md` — 叙事风格 SSOT（继承）
- `historiography-annotate/reference/峰值年规则.md` — 峰值类型
- `historiography-annotate/reference/朝代优先级规则.md` — P0–P3

## LLM

与 `dynasty_priority.py` / `peak_year.py` **不同通道**：

- **朝代知识补全**：`dynasty_supplement_lib.call_llm` 入口 **`ensure_deepseek_v4_pro()`** → **`deepseek-v4-flash`**
- **标注附属**（峰值年/优先级/人物标签）：`ensure_annotate_model()` → `deepseek-v4-flash`

补全**创作**阶段遵守 `执行纪律.md`：三类分步、详情逐条；**不得**照搬 enrichment 默认批量（≤20 条/批）。

## 路径（相对 HISTOGRAPH_ROOT）

| 用途 | 路径 |
|------|------|
| 中间产物（研究/候选） | `data/05工作流中间产物/朝代知识补全/` |
| **正式产出根目录** | `data/06朝代知识补全/` |
| 索引条目 JSON | `data/06朝代知识补全/索引条目/` |
| 详情译文 JSON | `data/06朝代知识补全/详情/`（**`翻译详情` = 小程序读者正文**，见总则 §零） |
| 维基摘录（compose grounding） | `data/06朝代知识补全/维基摘录/` |
| 朝代元数据 | `data/01历史坐标数据/朝代.json` |
| 并入目标 | `data/03索引标注条目/史略索引_01至02.json` |

> `06` 与 `03索引标注条目`、`04史料翻译` 隔离，专用于朝代知识补全（事略/典制/论著/人物）的一步到位产出。

## 命令

```bash
cd historiography-dynasty-knowledge/scripts

# Step 1 研究报告
python3 dynasty_supplement.py --dynasty 五帝 --step research --dry-run

# Step 2–4 候选（每次仅一类，禁止多类同 prompt）
python3 dynasty_supplement.py --dynasty 五帝 --step candidates-shilue --dry-run
python3 dynasty_supplement.py --dynasty 五帝 --step candidates-dianzhi --dry-run
python3 dynasty_supplement.py --dynasty 五帝 --step candidates-lunzhu --dry-run

# Step 2.5 人物候选（第四分支 · 一次调用六类串行）
python3 dynasty_supplement.py --dynasty 五帝 --step candidates-renwu --dry-run

# 遗漏审阅提示词（可复制到其他大模型查漏；各生成步骤结束后亦自动更新）
python3 dynasty_supplement.py --dynasty 五帝 --step export-omission-prompt
# 产出：data/05工作流中间产物/朝代知识补全/{朝}_遗漏审阅提示词.md

# Step 6 详情（每次仅一条；compose-detail 自动拉维基底稿，可用 wiki-fetch 单独预拉）
python3 dynasty_supplement.py --dynasty 五帝 --step wiki-fetch --entry-id GLBL_00xxx
python3 dynasty_supplement.py --dynasty 五帝 --step compose-detail --entry-id GLBL_00xxx --dry-run

# fill / gate renwu
python3 dynasty_supplement.py --dynasty 五帝 --step fill-renwu --dry-run
python3 dynasty_supplement.py --dynasty 五帝 --step gate-renwu

# 增量补漏 compose 后必跑（优先级/峰值年/人物标签）
python3 dynasty_supplement.py --dynasty 五帝 --step enrich-all
```

**禁止** `--step all`。增量补漏见 `reference/Agent执行纪律.md` §六（compose 后不可省略 `enrich-all`）。详见 `reference/执行纪律.md`。

## 入库

补全条目经 gate 后：

1. `append_dynasty_supplement.py` 将 `06/索引条目/` 并入 `史略索引_01至02.json`
2. `import_box_index_json.py` 导入 `historical_box`
3. 详情 JSON（`06/详情/`）导入 `historical_box_detail`（待实现专用 import）
