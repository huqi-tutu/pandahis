---
name: historiography-translate
description: >
  GLBL 全局索引 → recall → source_plan → Phase1 母本顺译 → Phase2 补全成稿 → verify → 04史料翻译。
  规则 SSOT：historiography-compose/references/翻译规则.md（每次 LLM 请求全量注入）。
---

# 史略翻译（GLBL 编排器）

## 何时使用

- 批量或单条 `GLBL_*` 史略翻译
- 调试 recall / plan / 两阶段 draft / verify
- 汇总入库 `historical_box_detail`

## 规则 SSOT

**唯一文件**：[`../historiography-compose/references/翻译规则.md`](../historiography-compose/references/翻译规则.md)

- 编排器：`lib/rule_bundle.py` 按阶段注入四层规则（**动笔前**，非仅 verify）
- Agent 改 prompt/流程前：**必须先读**上述 SSOT，禁止只读本 SKILL 摘要

## 执行清单（每条必做）

```
1. recall     → 段落索引逐 block 召回
2. source_plan → 母本 M 清单 + 外部补全（默认采用:false）
3. Phase1     → draft_mother（仅母本，无他书）
4. verify_mother → 必现词 + 覆盖 + 禁他书
5. Phase2     → draft_enrich（锚点补异说/背景/细节，禁重复母本）
6. verify     → 全文 + plan 出处
7. aggregate  → 史略翻译_汇总.json
8. sync       → 自动 upsert 线上 historical_box_detail（`TRANSLATE_AUTO_SYNC=1` 默认开）
```

## 流水线

```
史略索引_01至02.json (GLBL_*)
  → recall
  → source_plan（M001… + 必现词 + 外部补全筛选）
  → Phase1 draft_mother  → {id}.mother.json
  → verify_mother_draft
  → Phase2 draft_enrich   → {id}_{名称}.json
  → verify
  → aggregate → sync（单条 upsert 线上 DB）
```

**分块**（长史略）：仍走 chunk plan+draft；两阶段对短条目默认开启（`TRANSLATE_TWO_PHASE=1`）。

## 命令

```bash
export HISTOGRAPH_ROOT=/path/to/pandahis/pandahis
cd tools/openclaw-historiography/historiography-translate

python3 translate.py init
python3 translate.py recall --id GLBL_00149
python3 translate.py run-one --id GLBL_00149
python3 translate.py verify --id GLBL_00149
python3 translate.py aggregate
python3 translate.py sync --id GLBL_00149   # 手动补同步
python3 translate.py sync --all           # 全量同步（等同 import 脚本）
python3 ../../scripts/import_box_translate_json.py
```

## 中间产物

`data/05工作流中间产物/翻译/`

| 文件 | 阶段 |
|------|------|
| `{id}_{名}.plan.json` | source_plan |
| `{id}_{名}.mother.json` | Phase1 母本顺译 |
| `{id}_{名}.chunk-NN.*` | 分块模式 |

## 外部补全纪律（plan + enrich）

仅当相对母本有 **异说 / 冲突观点 / 必要背景 / 母本未载细节 / 评价差异** 时 `采用:true`。  
**禁止**把母本已述事实换说法再引他书。

## 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `TRANSLATE_TWO_PHASE` | `1` | `0` 回退单次 draft |
| `TRANSLATE_COVERAGE_STRICT` | `1` | 覆盖不足则失败 |
| `TRANSLATE_COVERAGE_MIN_RATIO` | `0.85` | M 清单命中率 |
| `TRANSLATE_PLAN_MIN_RATIO` | `0.95` | plan 条数 / 母本分句 |
| `HIST_LLM_PROVIDER` / `DEEPSEEK_API_KEY` | — | LLM |

## 相关 Skill

- [`historiography-compose`](../historiography-compose/SKILL.md) — 规则 SSOT 与手工 compose
- [`historiography-annotate`](../historiography-annotate/SKILL.md) — 召回与索引（非翻译入口）
