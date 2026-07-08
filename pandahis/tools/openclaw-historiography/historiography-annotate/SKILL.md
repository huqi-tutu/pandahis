---
name: historiography-annotate
description: >
  史料标注 Step 1/2/4（非调度入口）。批量/多卷/全流程必须先走 historiography-pipeline。
  Step 1 必读 reference/人物标注规则.md。卷型补充、格式规范、人物归因仍适用。
  Step 1 或 Step 4。激活词：史料标注、史略标注、人物标注。
---

# 史料标注工作流

## When NOT to Activate（改用 historiography-pipeline）

- 用户说「批量标注」「标百卷」「标下一卷」「按流程标」
- 需要查进度、验证 Step 是否完成
- **禁止**在本 skill 内自写批量脚本

调度 skill：`pandahis/pandahis/tools/openclaw-historiography/historiography-pipeline/SKILL.md`

## When to Activate

- pipeline 指示当前步为 **Step 1** 或 **Step 4**
- 用户要求标注某卷原文（如「标注史记·五帝本纪」）且已走 pipeline
- 已有骨架 JSON 需格式自检（Step 2）
- Step 3 审计退回后需重新标注
- Step 4 字段补全或终检（`--phase final`）
- 用户提到 `segment_attribution`、`史略ID`、`条目索引`

## 角色

**块优先、边界精判**：先划叙事块与人物清单，再展开 `segment_attribution` + `entries`。  
严格按 `reference/人物标注规则.md`（v2）与 `reference/人物归因.md` 执行。  
Step 1 负责「该不该建条、块归谁」；Step 3（audit）负责语义复核与删改决策。

**原则**：按卷提取**人物**与**尽可能完整的连续叙事段**；块内不轻易 exclude。表 / 志 / 书无卷主人公则 **skip**；本纪可有多名**君王**（如五帝本纪），但本纪不出士臣 / 庶众 / 宗戚。合传 / 多人本纪须在**块边界**精读，防张冠李戴。

## 路径配置

默认根目录为项目 `pandahis/pandahis`（`paths_config.py` 自动推导），可通过环境变量覆盖：

```bash
export HISTOGRAPH_ROOT=/path/to/pandahis/pandahis   # 可选
```

| 用途 | 路径（相对 HISTOGRAPH_ROOT） |
|------|------------------------------|
| 原文 | `data/02二十四史拆分后/` |
| 卷骨架（Step 1 产出） | `data/03索引标注条目/{编号}{著作名}_{卷号}_{卷名}_skeleton.json` |
| 著作索引（merge 产出） | `data/03索引标注条目/{编号}{著作名}_条目索引.json` |
| 统计 | `data/03索引标注条目/标注统计/{编号}{著作名}_标注统计.md` |
| 审计日志 | `data/03索引标注条目/标注审计/{编号}{著作名}_标注审计.md` |
| **标注中间产物** | `data/05工作流中间产物/标注/` |
| 帝王参考 | `reference/帝王.json` |
| 政权参考 | `reference/政权.json` |
| 朝代参考 | `reference/朝代.json` |
| 文明参考 | `reference/文明.json` |
| **准入标准（权威）** | `reference/人物标注规则.md` |
| **块优先归属** | `reference/人物归因.md` |
| **峰值年规则** | `reference/峰值年规则.md` |
| **卷型补充** | `reference/卷型补充/<卷类型>.md` |

Skill 目录：`pandahis/pandahis/tools/openclaw-historiography/historiography-annotate/`

---

## 流水线总览

```
Step 1  LLM 标注 → skeleton.json（按卷独立文件）
Step 2  check_format.py --phase skeleton  → exit 0 才继续
Step 3  audit_precheck.py → historiography-audit LLM 审计 → 修正后重跑 2+3
Step 4  fill_fields.py → LLM 补全 → peak_year.py（Step4d）→ check_format.py --phase final
        → generate_stats.py → 落盘统计
Step M  merge_volumes.py → 著作级索引 {著作}_条目索引.json
```

**任一 Step 失败 → STOP，修正后从失败步重跑，不得跳步。**

**⚠️ 关键规则：每卷独立文件，绝不覆盖已有卷。** Step 1 产出仅写当前卷的 skeleton，通过 merge_volumes.py 合并为著作级索引。

---

## 君王命名规则（强制）

**君王** `史略名称` 必须与 `reference/帝王.json`「帝王」字段完全一致。

补录 / 对齐：`emperor_gap.py`、`posthumous_emperor.py`（追尊场景仍可能君王+士臣双条，见脚本说明）。

质检：君王名 ≠ 四级帝王坐标 ≠ 帝王表「帝王」→ 硬失败。

---

## Step 0：段落数（硬门）

见上文 `count_paragraphs.py`；段数 SSOT = `段落索引/{著作}_{卷}.json`。

---

## Step 1：人物标注

**顺序（强制）**

1. **Step1a** — 仅据 **著作 + 卷名** 判定主人公清单 → `protagonists.json`（不读段落）→ **identity_gate 硬检**
2. **Step1b** — 读原文，按清单划 **blocks** → 展开 `segment_attribution` + `entries`
3. **定类** — 主人公已锁定后，用分类链为 **同一人** 消歧

**失败恢复（编排器自动，勿等人工）**

- **卷型 / 主轴人数**：Step1a LLM 写入 `protagonists.json`（`volume_type_guess` + 名单）；展开 skeleton 时合并为 `volume_subtype` / `protagonist_count`。**禁止**用脚本书名「纪/传」推断单人/合传。
- verify 失败 → `failure_classifier` 归类根因 → 失效 protagonists/blocks/skeleton → 脚本 autofix / `repair_registry` **机械返工** → **再 LLM**
- 主轴类错误 → **强制删除** `protagonists.json` 重跑 Step1a
- Step2 打回 Step1 → 默认删除 blocks + skeleton；主轴错误时连 protagonists 一并删除
- 志书/表卷若误建 entries → 跑批前 `repair_skip_narrative_volume` 清空

**repair 边界（硬，违反即 STOP）**

| 允许（机械） | 禁止（须 LLM） |
|-------------|----------------|
| 表/志全段 exclude、段首原文字句摘录 | 段落块界、segment_attribution |
| 合传人名白名单校验 | 史略分类（文臣/武将/庶众…） |
| 坐标 ID 从帝王表反查（名称已定后） | 四级帝王坐标归属、起止年 |
| `knowledge_provenance` skip 标记 | `pop(_needs_llm)` 假装 Step4 完成 |

《汉书》等 `require_llm_knowledge: true` 著作：**禁止**叙事卷 repair 旁路；Step4 `force_step4_llm` 强制调 LLM。  
final 检：`knowledge_provenance.step1/step4.source` 须为 `llm`（表志 skip 卷为 `skip_non_narrative`）。

**人工介入条件**：同一卷同一根因重试 ≥ `max_retries` 且卷级返工脚本仍失败时，才 `awaiting_decision`。

### 必读

```
reference/人物标注规则.md
reference/人物归因.md
reference/卷型补充/{卷类型}.md
```

### 块优先工作流（Step 1）

```
Step1a  著作+卷名 → protagonists 清单（不读段）
Step 0  段数 = 段落索引 total
Step B  叙事块 paragraph_from / to（块主人 ∈ Step1a 清单）
Step C  合传 / 多人本纪：块边界 + exclude 候选段精读
Step D  展开 segment_attribution（块内机械填充；可用 expand_blocks.py）
Step E  归纳 entries + paragraphs + 原文字句
```

**禁止**：事略 / 典制 / 民录 / 论著 entry；同段多 owner；未读原文按人名切块。  
**分类**：只在 entry 定一次；段上不必逐段判四类。  
**exclude**：`太史公曰`、卷首标题、明确世系链、纯纪年；块内叙事尽量归人物。  
表志书无主人公 → **skip 整卷**

可选辅助：

```bash
python3 pandahis/pandahis/tools/openclaw-historiography/historiography-annotate/expand_blocks.py \
  draft_blocks.json -o /tmp/attr.json --merge-entries
```

### 产出示例

```json
{
  "segment_attribution": [
    {"paragraph": 1, "owners": [{"name": "黄帝", "category": "君王"}]},
    {"paragraph": 47, "owners": [], "exclude_reason": "太史公曰"}
  ],
  "entries": [{
    "史略ID": "SHIJI_001_01",
    "史略名称": "黄帝",
    "史略分类": "君王",
    "paragraphs": [{"volume": "五帝本纪", "paragraph_from": 1, "paragraph_to": 9}]
  }]
}
```

### Done when（Step 1）

- [ ] Step 0 通过  
- [ ] 已 Read 人物标注规则 + 人物归因 + 卷型补充  
- [ ] 叙事块已划分；合传 / 多人本纪边界已精判  
- [ ] 段数 = total_paragraphs；segment_attribution 1..N 完整；单段单归属  
- [ ] skeleton 落盘（或 skip 卷已标记）

---

## 字段规范

| 字段 | 要求 |
|------|------|
| 史略分类 | 君王 / 宗戚 / 宦官 / 文臣 / 武将 / 蕃祚 / 庶众 |
| 史略名称 | 君王对齐帝王.json |
| 原文字句 | 开篇段逐字引用 |

---

## Step 2：脚本硬门

```bash
python3 pandahis/pandahis/tools/openclaw-historiography/historiography-annotate/check_format.py \
  /path/to/skeleton.json \
  --phase skeleton
```

检查项：**段落数与原文对照**、结构、`segment_attribution` 完整性、entries 字段、归属双向一致、原文字句逐字验证（自动定位原文，不依赖错误的 `source_file`）。

### Done when（Step 2）

- [ ] 命令 **exit 0**
- [ ] 无 ❌ 错误（警告也需人工确认）

**exit 1 → STOP，退回 Step 1，不得进入 Step 3。**

---

## Step 3：质检审计

激活 **`historiography-audit`** skill（下游专用，勿在本 skill 内重复语义质检）。

### 进入条件

Step 2 `check_format.py --phase skeleton` 必须 **exit 0**。

### 审计流程（annotate → audit 协同）

```bash
# audit：确定性预检
python3 pandahis/pandahis/tools/openclaw-historiography/historiography-audit/audit_precheck.py \
  /path/to/skeleton.json

# audit：LLM 六条语义审计（见 historiography-audit/SKILL.md）
# 若删/改条目 → 同步 segment_attribution + audit_revision → 重跑 Step 2 + 预检
```

**ID 策略**：删除条目后**保留空号**（如 10→12 缺 11），在 `audit_revision.deleted_entry_ids` 记录。

**卷类型**：默认由预检脚本按规则判定；可 JSON 覆盖 `volume_type` + `volume_type_reason`（方案 C）。

### 审计落盘（仅 HISTOGRAPH_ROOT）

`$HISTOGRAPH_ROOT/data/03索引标注条目/标注审计/{编号}{著作名}_标注审计.md`

模板见 `historiography-audit/reference/审计模板.md`

### Done when（Step 3）

- [ ] audit 结论 ✅ 修正后通过
- [ ] 删改后 Step 2 + audit_precheck 再次 exit 0
- [ ] 审计 MD 已落盘

**不通过 → STOP，退回 Step 1 或按 audit SOP 修正后重跑。**

---

## Step 4：字段补全

```bash
python3 pandahis/pandahis/tools/openclaw-historiography/historiography-annotate/fill_fields.py /path/to/skeleton.json
python3 .../fill_fields.py /path/to/skeleton.json --merge-auto
```

编排器自动：`prepare → 脚本加固 → LLM 补缺（仅仍缺项）→ 脚本加固 → --finalize → 考订补全 → check_format final`；**final 失败时再自动脚本修复一轮**，无需人工追问。

**脚本加固**（`step4_hardening.harden_shiji_step4_skeleton`，编排器在 LLM 前/后、finalize 后、check_format 失败时自动调用）：

1. `fill_fields.py --merge-auto`
2. `apply_person_years_from_tables` + `apply_volume_step4_fallback`（PERSON_PATCH / 学界表 / 坐标 / 主轴）
3. `backfill_provenance_fields.py`（补 `_年LLM依据` / `_坐标主轴说明`，不覆盖已有）
4. `fill_fields.py --sync-coord-ids`

**LLM 只补仍缺的正式字段（优先级、年份、坐标名称）；禁止 LLM 删除 `_auto_filled` / `_needs_llm`（脚本 finalize）。**

**坐标 ID（脚本自动，LLM 禁止手填）**：每条史略在四级坐标名确定后，由 `fill_fields.py` 自动写入 `文明ID` / `朝代ID` / `政权ID` / `帝王ID`（SSOT：`reference/文明.json` → `朝代.json` → `政权.json` → `帝王.json`）。已有卷可批量补 ID：

```bash
python3 .../fill_fields.py /path/to/skeleton.json --sync-coord-ids
```

1. 脚本 `--merge-auto`：归属 + 君王年份 + **坐标 ID** 确定性合并
2. LLM：补 `优先级` / `优先级判定理由` / 年份 / 归属（见 `_needs_llm`）
3. 脚本 `--finalize`：verify 通过后删临时字段
4. 终检：

```bash
python3 pandahis/pandahis/tools/openclaw-historiography/historiography-annotate/check_format.py \
  /path/to/skeleton.json --phase final
```

5. 生成统计：

```bash
python3 pandahis/pandahis/tools/openclaw-historiography/historiography-annotate/generate_stats.py \
  "$HISTOGRAPH_ROOT/data/03索引标注条目/01史记_条目索引.json"
```

### 年份规则（时间坐标，硬要求）

**每条史略必须有 `史略开始年` + `史略结束年`（整数，公元前为负）**，否则无法放入时间轴。

**人物类**生卒年与卷内是否有君王无关；须由大模型据史学界主流观点填写，**尽量体现正常生卒或即位/退位**，脚本不得覆盖已填年份。

| 分类 | 开始年 | 结束年 |
|------|--------|--------|
| 君王 | 即位年 | 退位/崩年 |
| 蕃祚 | 政权立国年 | 政权灭亡年 |
| 文臣 / 武将 / 宦官 / 庶众 / 宗戚 | 出生年 | 去世年 |

**蕃祚**：须由大模型据【著作+卷名+政权名】考订政权兴亡年代，勿用叙事跨度、勿用传主生卒。脚本兜底见 `collective_volume_subjects.py`。

**脚本兜底**（仅当 LLM 未填完整时；**编排器 Step4 在调 LLM 之前由脚本执行**）：

1. **学界有推测生卒**（含仅生年推测）→ 填完整出生年～去世年，写入 `_auto_filled._年LLM依据`  
2. **完全无出生年推测**、仅知去世年 → 开始年 = 结束年 = 去世年  
3. 不知去世年、知活跃期 → 取活跃期帝王在位起止年  
4. 活跃期亦未知 → 取对应朝代开始年（两年相同）

**禁止**：用四级帝王在位年（如汉高祖 -202～-195）代替人物生卒；有学界/PATCH 数据时不得退化为帝王在位年。

**学界生卒数据来源（脚本 SSOT，按优先级）**：

| 模块 | 范围 | 说明 |
|------|------|------|
| `shiji_scholarly_lifespans.py` | 031–130（按史略ID） | 学界主流生卒，含推测生年 |
| `shiji_person_fallback.py` → `PERSON_PATCH` | 全志人物名 | 077–130 见 `shiji_person_patch_077_130.py` |
| `person_year_fallback.py` | 上表未命中时 | 去世年单点 → 帝王在位 → 朝代起始 |

**《史记》Step4 脚本执行顺序**（`gates.step4_shiji_person_fallback` → `step4_hardening`，**LLM 之前/之后、finalize 后、check_format 失败时均会调用**）：

1. `fill_fields.py --merge-auto`（只写坐标元数据，**不**把帝王在位年写入人物生卒）  
2. `apply_person_years_from_tables`：PERSON_PATCH / 学界表预填生卒 + `_年LLM依据`  
3. `apply_volume_step4_fallback`：坐标、优先级、主轴说明  
4. `backfill_provenance_fields`：缺考订字段时自动补（不覆盖已有）  
5. `prepare_year_quality_repatch`：质检失败时清空错误年 → **再次**尝试 PATCH/学界表回填  
6. 仅当仍缺字段或无任何依据时 → 才调 LLM Step4  
7. `check_format final` 失败 → `step4_recover_before_fail` 再跑一轮 1–5 + finalize + 终检  

有 `_年LLM依据` 的条目：`check_format` 不再用「段落数 vs 生卒跨度」启发式否决。

**跨时期人物**（士臣 / 庶众）：一条 entry；四级帝王由大模型按 **主政/仕宦/最高官职/功业** 判定（难分则取更早帝王）；跨度 ≥30 年时填 `_auto_filled._坐标主轴说明`。**宗戚**不适用功业主轴，须按 **`reference/人物坐标归属规则.md` · 宗戚专则**：嫔妃 / 皇后 / 太后挂**丈夫（册封之君）**，公主等挂**生父**。详见 `reference/跨时期人物坐标.md`。

**时空坐标**：均须来自 `reference/*.json`；非君王由关联帝王反推二/三/四级。
`check_format.py --phase final` 与 `fill_fields.py --verify` 会按分类校验。

### Step 4d：峰值年（编排器自动，年份终态后）

在 Step4 主 LLM 补全年份/优先级/坐标 **之后**、`--finalize` **之前**，编排器自动调用 `peak_year.py`：

```bash
# 单卷手工补跑（通常不必；编排器已调用）
python3 pandahis/pandahis/tools/openclaw-historiography/historiography-annotate/peak_year.py \
  /path/to/skeleton.json --llm
```

**字段（中文键）**：`峰值年` / `峰值原因` / `峰值类型` / `峰值置信度`  
**规则 SSOT**：`reference/峰值年规则.md`  
**硬约束**：`史略开始年 ≤ 峰值年 ≤ 史略结束年`  
**幂等**：`_auto_filled._峰值指纹` 未变则跳过；`_峰值人工锁定=true` 永不被覆盖  
**待审**：置信度 &lt; 0.4 或越界 clamp → `_峰值待审`，写入 `data/05工作流中间产物/标注/{卷}_peak_review.md`，**不阻断** `check_format final`

**禁止**：把峰值年塞进 Step4 主 LLM prompt（易卡死、难幂等）。

**LLM 输入（`peak_year.py` 自动组装）**：`判定对象`（=史略名称）、史略分类、简介、年份区间、考订依据·坐标主轴/年、母本段落、母本原文字句（≤300字）、二/三/四级坐标；**不传**卷内优先级。合传/多源/蕃祚自动小批次（≤5）+ 事后守门（原因须点名判定对象）。

### Done when（Step 4）

- [ ] `check_format.py --phase final` exit 0
- [ ] 统计 MD 已生成
- [ ] progress 中该卷 Step 1–4 均为 **done**（Step4 完成即本卷标注完成）

---

## Step M：合并著作索引

每卷独立标注完成后，合并为著作级条目索引。

```bash
# 合并指定著作
python3 pandahis/pandahis/tools/openclaw-historiography/historiography-annotate/merge_volumes.py 01史记

# 或合并所有著作
python3 pandahis/pandahis/tools/openclaw-historiography/historiography-annotate/merge_volumes.py --all
```

**规则**：merge 脚本扫描 `史料标注/` 下所有 `{著作}_{卷号}_*_skeleton.json`，合并 entries 为著作级索引 `{著作}_条目索引.json`。可反复运行，幂等。

### Done when（Step M）

- [ ] 著作级索引已生成或更新
- [ ] 条目数 = 各卷条目数之和

---

## 文件命名

| 层级 | 文件 | 示例 |
|------|------|------|
| 卷骨架 | `{编号}{著作名}_{卷号}_{卷名}_skeleton.json` | `01史记_001_五帝本纪_skeleton.json` |
| 著作索引 | `{编号}{著作名}_条目索引.json` | `01史记_条目索引.json` |
| 著作统计 | `{编号}{著作名}_标注统计.md` | `01史记_标注统计.md` |

详细格式见 `reference/格式规范.md`。准入标准见 `reference/人物标注规则.md`。
