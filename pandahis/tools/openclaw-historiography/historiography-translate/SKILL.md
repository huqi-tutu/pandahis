---
name: historiography-translate
description: >
  GLBL 全局索引 → recall → source_plan → Phase1 母本顺译 → Phase2 说书润色
  （短卷整篇；长卷默认分章 polish）→ Phase3 只质检 → Phase4 自动定向修复
  → Phase5 复检 → verify/sync。规则 SSOT：historiography-compose/references/翻译规则.md。
  Phase2 默认不注 plan 补全清单；旧分章补全见 TRANSLATE_PHASE2_MODE=enrich。
---

# 史略翻译（GLBL 编排器）

## 何时使用

- 批量或单条 `GLBL_*` 史略翻译
- 调试 recall / plan / 两阶段 draft / verify
- 汇总入库 `historical_box_detail`

## 规则 SSOT

**写作细则**：[`../historiography-compose/references/翻译规则.md`](../historiography-compose/references/翻译规则.md)  
**内容 QA 合同**（十条 · L1–L5 · A–G）：[`../historiography-compose/references/历史内容编辑合同.md`](../historiography-compose/references/历史内容编辑合同.md)  
**质量宪法**（八大守恒 · 新增三条 · Backtrace）：[`../historiography-compose/references/历史翻译质量宪法.md`](../historiography-compose/references/历史翻译质量宪法.md)

- 编排器：`lib/rule_bundle.py` **按阶段切片注入**；`lib/quality_constitution.py` 注入八大守恒（Phase1/2/3；polish 路径直接注入）
  - **plan**：默认仅母本清单骨架（**不挖外部补全**）；旧选题见 `TRANSLATE_PLAN_EXTERNAL=1`
  - **Phase1**：顺译骨架；主防 A/C/D/G
  - **Phase2**：说书润色 + 自挖补充；主防 C/D/E/F/G；有补充须列参考著作
  - **Phase3–5**：按 A–G 质检 → 定向修 → Integrity 复检
- Agent 改 prompt/流程前：**必须先读**上述 SSOT；禁止把单篇病例写成全局规则

## 执行清单（每条必做）

```
1. recall / source_plan
2. Phase1 母本顺译（可分批）→ verify_mother
3. Phase2 整篇润色（一次全文；**结构账本 S 序** + 说书；默认不注 plan；L1 守恒优先、L3/L4 按需；**禁整段删情节**；漏段时程序只标夹缝由模型补洞；地名/纪年走标注账本硬检）
4. Phase3 第一轮质检（只找问题）→ *.qa.md + *.qa.json
5. Phase4 自动定向修复（列入报告的 P0–P3 都修；无人工确认）→ 写回成稿
6. Phase5 最终复检 → *.recheck.*（通过再 sync）
旧路径：TRANSLATE_PHASE2_MODE=enrich|chapter → 分章+plan 锚点补全
```

**硬原则**：质检与修复仍分两步提示（禁止「检查并直接改正文」一步完成）；流畅性不得凌驾时间真实性。无待修问题时跳过 Phase4/5。纯品味不立项。
`TRANSLATE_AUTO_REPAIR=0` 可只出质检报告、不自动修。

## 长文兼容（编排器档位 · 不改规则 SSOT）

**理念**：同一套翻译规则；长卷 Phase1 分批保覆盖；Phase2 默认**分章说书**（合并若干母本批 + 上章声口样例续写），**不削规则、不另开润色轮**。短文与长文的文风均在 Phase2 落地。

| 档位 | 触发 | 行为 |
|------|------|------|
| 分批禁越界 | Phase1 分批 | 批末禁写完下批情节；批首禁释义重开已写事件；合并去重+事件指纹 |
| Phase2 分章说书 | 母本超阈值且存在 `-b*`（默认） | 每 ~4 个 Phase1 批收成一章；注入上章末尾声口样例；合并去重 |
| Phase2 旧分批 | `TRANSLATE_PHASE2_MODE=legacy_batch` | 按 Phase1 批逐批独立 enrich（易声口不齐，仅回退用） |
| 原文窗口 | Phase1：本批 M「原文摘句」（按 P 分组展示），只译列出摘句，同组合段禁一句一段；Phase2：本章段落窗 + 前后各 3 段（`TRANSLATE_CONTEXT_PARAS`），`must_translate` 才写，`context_*` 仅理解 |
| 经典引用候选 | plan 落盘 | 按规则四软配额标注 `经典引用候选`；Phase1 仅对候选镶嵌史料「」；用后融入接叙，忌同义破折号主腔 |
| 索引补充纠偏 | plan 落盘 | 平行正史禁止整卷「去重不用」→「异说」筛差异；**不**充当外部补全书单 |
| 长文 plan 决策聚焦 | M≥40 | 母本清单程序生成；**默认不跑外部补全选题** |
| 参考著作 | Phase2 成稿 | 有补充必须文末列出；缺则 Phase2/Phase3 拦 |
| 外部补全逐条验收 | 仅旧 enrich | `TRANSLATE_PHASE2_MODE=enrich` 时仍按 plan 采用项落地 || 引号风格 autofix | Phase1/2 质检前 | A 弯引原文→「」；B 直角白话→“”；不因此整章重试 |
| 章界双写 heal | 声口样例 + 合并 + 补洞 | 样例去情节；合并静默丢后段释义双写；补洞拒引号内/主题已写；**不加双写硬失败** |
| 定向补洞 L2 | 仅补全落地失败 | 小调用插入缺失句；默认最多 2 次（`TRANSLATE_ENRICH_PATCH_MAX`）；仍失败再整章重试 |
| 分章文风 | Phase2 每章 | 提示词要求本章即流畅说书叙事；文风密度软警告（「」过少等） |

## 流水线

```
史略索引_01至02.json (GLBL_*)
  → recall
  → source_plan（程序 M 清单 + 宏观外部选题 + 判重挂锚 + 索引裁决 + 前置引入）
  → Phase1 draft_mother  → {id}.mother.json（分批时每批译完即本批语义覆盖；合并去重）
  → verify_mother_draft（合并后轻量补验 + 必现词全篇）
  → Phase2 draft_enrich   → {前置引入 + 锚点嵌入 + 分章说书润色} → 程序重建参考著作 → {id}_{名称}.json
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
python3 translate.py run-one --id GLBL_00084 --from-phase phase2   # 润色+质检+自动修复/复检
python3 translate.py run-one --id GLBL_00084 --from-phase phase3   # 质检起（默认连带 4/5）
python3 translate.py run-one --id GLBL_00084 --from-phase phase4   # 仅修复+复检
python3 translate.py run-one --id GLBL_00084 --from-phase phase5   # 仅复检
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
| `{id}_{名}.qa.md` / `.qa.json` | Phase3 质检 |
| `{id}_{名}.before_repair.json` / `.repair.md` | Phase4 修复前备份与修改记录 |
| `{id}_{名}.recheck.md` / `.recheck.json` | Phase5 复检 |
| `{id}_{名}.chunk-NN.*` | 分块模式 |

## 外部补全纪律（默认交 Phase2）

**默认（polish）**：`source_plan` **不挖**外部补全；Phase2 润色时按规则自补；**凡补充须文末列「参考著作」**；史源/时间线靠 Phase3–5。

**旧两步法**（`TRANSLATE_PLAN_EXTERNAL=1` 且 `TRANSLATE_PHASE2_MODE=enrich`）：  
1. 宏观选题 → 全书母本判重 → 挂锚  
2. Phase2 按采用项嵌入  

`TRANSLATE_EXTERNAL_FLOOR` 默认关。

## 本传主退场与交接段（写作提示 · 必读）

与 v2 标注配套：交接可双挂；译文按**本传主镜头**，同篇退场不重复。

1. **先检后补**：Phase2 动笔前对照 Phase1——若正文已译出本传主崩/薨/卒/自沈等 → **禁止**再写尾部退场补叙。
2. **缺则补一句**：仅当 `本传缺漏补全` / plan 项 `本传退场/收束` 且母本段落域确无退场 → 篇末 **1 句**收束，优先采用 snippet 白话顺译，不扩写。
3. **交接不对称**：后君开篇遇「前君卒+本君立」→ 前君侧一两句过渡，不展开别人故事；前君收尾详写退场，后君「立」点到为止。

SSOT：[`翻译规则.md`](../historiography-compose/references/翻译规则.md) · 规则二「本传主退场完整性」「交接双挂段 · 角色不对称」。

## 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `TRANSLATE_TWO_PHASE` | `1` | `0` 回退单次 draft |
| `TRANSLATE_PLAN_MAX_RETRIES` | `2` | source plan 未通过（如空外部补全）时同轮带反馈重试次数 |
| `TRANSLATE_PLAN_EXTERNAL` | `0`（polish 默认） | `1` 时 plan 才挖外部补全；enrich 模式自动视为开启 |
| `TRANSLATE_EXTERNAL_MACRO` | `1` | 仅当 plan 挖补全时：宏观选题两步法 |
| `TRANSLATE_EXTERNAL_FLOOR` | `0` | `1` 时才对长文空采用做软提升凑数 || `TRANSLATE_EXTERNAL_DEDUPE` | `1` | plan 落盘后用全书母本信息点脚本粗筛外部补全；`0` 关闭 |
| `TRANSLATE_EXTERNAL_DEDUPE_LLM` | `1` | 对脚本标「可疑」项做 LLM 精判（宏观路径选题后也会跑）；`0` 只跑脚本 |
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
| `TRANSLATE_MUST_PHRASE_MIN_TOTAL_FOR_RATIO` | `5` | 硬锚点总数低于此值时不用比例，改看绝对缺失数 |
| `TRANSLATE_MUST_PHRASE_MAX_MISS_ABSOLUTE` | `4` | 小样本（硬锚点 <5）时绝对缺失数 ≥ 此值才阻断 |
| `TRANSLATE_COVERAGE_L2` | `1` | L1 灰区时长文启用 LLM 语义复核 |
| `TRANSLATE_COVERAGE_L2_GRAY_BAND` | `0.12` | L1 低于阈值在此带宽内才触发 L2 |
| `TRANSLATE_COVERAGE_L2_MIN_CHECKLIST` | `50` | 清单少于此条数不跑 L2 |
| `TRANSLATE_COVERAGE_L2_BATCH` | `6` | 语义覆盖每批复核条数（原 12，缩小以降低 JSON 失败率） |
| `TRANSLATE_COVERAGE_L2_DEGRADE` | `1` | 解析失败时本批标 unclear 降级，不阻断整条翻译 |
| `TRANSLATE_COVERAGE_L2_MAX_CLAIMS` | `24` | L1 灰区路径单次最多复核弱覆盖单元数 |
| `TRANSLATE_LENGTH_RATIO` | `1.2` | 成稿/母本顺译字数软警告：低于 `史料原文字符数×比例` 时 ⚠️ 提示，**不阻断** verify |
| `TRANSLATE_PHASE2_MAX_MOTHER_OVERLAP` | `0.95` | 短卷：与母本重合≥此值 → **硬失败** |
| `TRANSLATE_PHASE2_MAX_MOTHER_OVERLAP_LONG` | `0.85` | 长卷（母本≥`LONG_MOTHER_CHARS`）：重合硬线 |
| `TRANSLATE_PHASE2_LONG_MOTHER_CHARS` | `8000` | 长卷阈值（重合硬线 + 默认分章 polish） |
| `TRANSLATE_PHASE2_SOFT_MOTHER_OVERLAP` | `0.72` | 重合在此与硬门槛之间 → **软警告**（好稿约 0.5） |
| `TRANSLATE_PHASE2_TEMPERATURE` | `0.45` | Phase2 润色温度（誊抄重试封顶约 0.62，避免说书场表演） |
| `TRANSLATE_PROSE_CLEANLINESS` | `1` | 成文洁净硬拦（看官/加工说明/市井称谓）；`0` 关闭 |
| `TRANSLATE_PHASE1_RETRY_TEMPERATURE` | `0.4` | Phase1 质检失败重试时的温度 |
| `TRANSLATE_PHASE2_MODE` | `polish` | `polish`=短卷整篇 / 长卷分章润色；`polish_whole`=强制整篇；`chapter`/`polish_chapter`=强制分章；`enrich`/`legacy_batch`=旧补全 |
| `TRANSLATE_MOTHER_SPAN_GATE` | `1` | Phase2/3 母本连续漏段硬检；`0` 关闭 |
| `TRANSLATE_PLACE_NOW_GATE` | `1` | Phase2 对照表内地名首次今地硬检（仅母本已出现地名）；`0` 关闭 |
| `TRANSLATE_ERA_YEAR_GATE` | `1` | Phase2 显式纪年缺公元并注硬检；`0` 关闭 |
| `TRANSLATE_PHASE2_MIN_LENGTH_RATIO` | `1.15` | 成稿/母本字数比下限 |
| `TRANSLATE_PHASE2_MIN_LENGTH_RATIO_HARD` | `1` | 默认硬拦偏薄；`0` 仅警告 |
| `TRANSLATE_BASELINE_REGRESSION` | `1` | 相对 `_versions` 旧优稿变薄/丢收束硬拦 |
| `TRANSLATE_BASELINE_MIN_LENGTH_RATIO` | `0.85` | 新稿不得低于旧优稿字数×此比 |
| `TRANSLATE_PHASE3_QA` | `1` | Phase3 质检开关 |
| `TRANSLATE_AUTO_REPAIR` | `1` | Phase3 后自动 Phase4/5（列入即修）；`0`=只出报告 |
| `TRANSLATE_PHASE3_BLOCK_ON_P0` | `0` | 仅当关闭自动修复时：有 P0 是否硬失败 |
| `TRANSLATE_PHASE2_CHAPTER_BATCHES` | `4` | 分章 polish / 旧分章：每章母本批数 |
| `TRANSLATE_ENRICH_PATCH_MAX` | `2` | 仅旧分章补洞 |
| `TRANSLATE_PHASE2_VOICE_CHARS` | `140` | 分章声口样例字数 |
| `TRANSLATE_PHASE2_BATCH_CHARS` | `10000` | 长卷分章/旧分批阈值（与 LONG_MOTHER 取较大） |
| `DEEPSEEK_MAX_TOKENS` | `50000` | DeepSeek 单次输出上限（长卷 Phase2 防截断） |
| `HIST_LLM_PROVIDER` / `DEEPSEEK_API_KEY` | — | LLM |
| **模型（写死）** | `deepseek-v4-flash` | `lib/openclaw.run_agent_turn` 入口调用 `ensure_deepseek_v4_pro()` |

## Token 优化（不改翻译规则 / 终检门槛）

- **队列 done**：`scripts/run_v2_translate_queue.py` 与 Skill 对齐，以 `verify_output()` 为准（非仅 `has_11`）。
- **Phase2 分章说书润色**（长卷默认）：合并若干 Phase1 批为一章，同一套 polish 规则 + 上章声口样例；逐章验偏薄/重合；整篇失败可自动降级分章。
- **Phase2 旧 enrich 分批**：仅 `TRANSLATE_PHASE2_MODE=enrich` / `legacy_batch`。
- **语义覆盖账本**：`claim_fp` 未变则跳过 LLM；Phase1 重试仅 `clear_ledger_labels(本批)`；**Phase2 润色通过后 `clear_ledger`**，终检不得沿用 Phase1 conveyed（否则润色漏段验不到）。
- **母本段落门禁**：`lib/mother_span.py` 按母本 `\n\n` 段抽取专名锚点；连续 ≥2 段对不上则 Phase2 硬失败。重试时 `locate_span_backfill_slots` 只标「上一覆盖段之后 / 下一覆盖段之前」夹缝，由模型局部补洞并去掉概括顶替句；**程序不往成稿塞母本原文**。`TRANSLATE_MOTHER_SPAN_GATE=0` 关闭。
- **结构账本**：`lib/structure_ledger.py` 将母本段编为 S001→S…（顺序锁 + 回合 identity），注入 Phase2；顺序倒挂发 ⚠️（漏段仍硬拦）。
- **标注账本**：`lib/annotation_ledger.py` 从母本×对照表生成必标地名清单；Phase2 硬检地名今地 + 显式纪年公元并注（`TRANSLATE_PLACE_NOW_GATE` / `TRANSLATE_ERA_YEAR_GATE`）。
- **Phase2 体量**：默认硬拦偏薄（母本×1.15）；L3/L4 按需加厚，禁止用压缩母本换篇幅；相对旧优稿变薄/丢收束另有基线门禁。
- **Phase5 / verify 对齐**：程序门禁不过不得标「建议入库」；终检失败会撤销 Phase5 建议入库。
- **repair 分流**：`infer_translate_retry_from_phase` — 母本已验过则 `from_phase=phase2`；字数不足分 phase1/终稿归类。
- **重试 feedback**：`format_retry_feedback` 压缩错误堆栈；**规则 bundle 仍按阶段切片注入主 prompt**。

## 相关 Skill

- [`historiography-compose`](../historiography-compose/SKILL.md) — 规则 SSOT 与手工 compose
- [`historiography-annotate`](../historiography-annotate/README.md) — 共享规则与召回脚本（非 Agent 入口）
- [`historiography-annotate-v2`](../historiography-annotate-v2/SKILL.md) — 标注索引产出（data/10）
