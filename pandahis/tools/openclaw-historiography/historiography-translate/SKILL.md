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
2. source_plan → 母本 M 清单 + 外部补全（默认采用:false）；`前置引入素材` 由编排器自动注入
3. Phase1     → draft_mother（仅母本，无他书）
4. verify_mother → 必现词 + 覆盖 + 禁他书
5. Phase2     → draft_enrich（锚点补异说/背景/细节，禁重复母本）；**先写笼统引入（60–250 字）再进正文**
6. postprocess → 段落合并、去加粗、归因清洗、尾部退场补全（自动）
7. verify     → 全文 + plan 出处 + **L1 覆盖概率** +（长文灰区）**L2 语义复核**
8. aggregate  → 史略翻译_汇总.json
9. sync       → 自动 upsert 线上 historical_box_detail（`TRANSLATE_AUTO_SYNC=1` 默认开）
```

## 流水线

```
史略索引_01至02.json (GLBL_*)
  → recall
  → source_plan（M001… + 必现词 + 外部补全 + 自动注入前置引入素材）
  → Phase1 draft_mother  → {id}.mother.json（分批时每批译完即本批语义覆盖）
  → verify_mother_draft（合并后轻量补验 + 必现词全篇）
  → Phase2 draft_enrich   → {前置引入 + 锚点补全} → {id}_{名称}.json
  → postprocess（段落合并/去加粗/去分节词）
  → verify（格式 + 母本覆盖；引入区无程序硬拦）
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
python3 translate.py refine --id GLBL_00149 --scope intro --instructions "补写阅读框架与过渡句"
python3 translate.py refine --id GLBL_00144 --scope attribution --no-llm  # 规则清洗，零 token
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
| `TRANSLATE_COVERAGE_MODE` | `semantic` | `semantic`=增量 LLM+账本；`l1`=legacy 脚本比对 |
| `TRANSLATE_COVERAGE_INCREMENTAL` | `1` | `0` 关闭分批增量语义覆盖（回退合并后全检） |
| `TRANSLATE_COVERAGE_SEMANTIC_MIN_RATIO` | `0.80` | 合并后语义覆盖传达率下限 |
| `TRANSLATE_COVERAGE_SEMANTIC_MAX_FAIL` | `3` | 合并后未传达条数上限（与传达率二选一） |
| `TRANSLATE_COVERAGE_SEMANTIC_BATCH_MIN_RATIO` | `0.90` | 分批本批语义覆盖传达率下限 |
| `TRANSLATE_COVERAGE_SEMANTIC_BATCH_MAX_FAIL` | `1` | 分批本批未传达条数上限 |
| `TRANSLATE_COVERAGE_STRICT` | `1` | L1 模式下覆盖不足则失败 |
| `TRANSLATE_COVERAGE_MIN_RATIO` | `0.70` | 覆盖单元命中率（默认 70%） |
| `TRANSLATE_COVERAGE_MIN_RATIO_LONG` | `0.65` | 清单 ≥80 条时长文阈值 |
| `TRANSLATE_COVERAGE_ITEM_MIN` | `0.32` | 单条/句群单元及格线（非逐词硬控） |
| `TRANSLATE_MUST_PHRASE_MIN_RATIO` | `0.40` | 硬锚点全局命中率下限（低于才阻断） |
| `TRANSLATE_MUST_PHRASE_MIN_RATIO_LONG` | `0.40` | 清单 ≥80 条时长文硬锚点下限 |
| `TRANSLATE_COVERAGE_L2` | `1` | L1 灰区时长文启用 LLM 语义复核 |
| `TRANSLATE_COVERAGE_L2_GRAY_BAND` | `0.12` | L1 低于阈值在此带宽内才触发 L2 |
| `TRANSLATE_COVERAGE_L2_MIN_CHECKLIST` | `50` | 清单少于此条数不跑 L2 |
| `TRANSLATE_COVERAGE_L2_BATCH` | `6` | 语义覆盖每批复核条数（原 12，缩小以降低 JSON 失败率） |
| `TRANSLATE_COVERAGE_L2_DEGRADE` | `1` | 解析失败时本批标 unclear 降级，不阻断整条翻译 |
| `TRANSLATE_COVERAGE_L2_MAX_CLAIMS` | `24` | L1 灰区路径单次最多复核弱覆盖单元数 |
| `TRANSLATE_PLAN_MIN_RATIO` | `0.95` | plan 条数 / 母本分句 |
| `HIST_LLM_PROVIDER` / `DEEPSEEK_API_KEY` | — | LLM |

## 相关 Skill

- [`historiography-compose`](../historiography-compose/SKILL.md) — 规则 SSOT 与手工 compose
- [`historiography-annotate`](../historiography-annotate/SKILL.md) — 召回与索引（非翻译入口）
