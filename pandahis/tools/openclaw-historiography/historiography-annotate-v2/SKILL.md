---
name: historiography-annotate-v2
description: >
  史料标注 Step 1/2/4（v2 轨道，唯一 Agent 入口）。批量/多卷须走 historiography-pipeline-v2。
  先定卷主轴（≤5人）再整卷划块、脚本展开；单人/蕃祚不调 LLM 划块。
  激活词：史料标注、人物标注、史略标注、新版标注、标注v2。
---

# 史料标注工作流（v2 · 整卷划块）

> 产出写入 **`data/10新标注条目/`**。Step 2–4 与硬检脚本共用 `historiography-annotate/`（见该目录 README）。  
> 老版 v1 Agent Skill 已移除；`data/03` 历史索引只读保留。

## 设计原则（v2.5）

| 原则 | 说明 |
|------|------|
| **整卷理解** | hezhuan 须读 P1..PN 全文后再逐段判主语，禁止未读全文填表 |
| **两步 Step1b** | **α LLM 逐段 primary_subject** → **β 脚本合并 blocks** |
| **块内同质** | 块内默认全归块主人；不在块内二次猜 owner |
| **机械展开** | LLM 只产出 `primary_subjects.json`；blocks 由 `v2_aggregate_blocks.py` 生成 |
| **边界专审** | 块交界 ±3 段须精读；失败只重跑边界，不重跑整卷 |
| **主轴锁定** | Step1a 名单 = 全部 entry；禁止名单外新建 |
| **exclude 收紧** | 6 类（含共段总述、**世系链**）；叙事段禁止滥用 v1 标签 |

权威规则：`reference/人物标注规则-v2.md` · `reference/Step1b-整卷划块专则.md`  
LLM prompt：`prompts/step1b_primary_subjects.md`（Step1b-α）  
聚合脚本：`scripts/v2_aggregate_blocks.py`（Step1b-β）

---

## When NOT to Activate

- 批量标注 / 标下一卷 / 查进度 → 必须先走 **`historiography-pipeline-v2`**
- **禁止**在本 skill 内自写批量脚本

## When to Activate

- 用户说「**史料标注**」「**人物标注**」「史略标注」「新版标注」「标注 v2」
- `historiography-pipeline-v2` 指示 Step 1 或 Step 4
- v2 轨道 Step 3 审计退回后重标

## 环境

```bash
export HIST_ANNOTATE_TRACK=v2
export HIST_LLM_PROVIDER=deepseek
# 标注模型由代码写死：ensure_annotate_model() → deepseek-v4-flash
python3 pandahis/pandahis/tools/openclaw-historiography/scripts/verify_workflow_roots.py
```

**LLM 通道**：编排器 `run_agent_turn` 入口 **`ensure_annotate_model()`** → **`deepseek-v4-flash`**；Step1b gate/expand 不调 LLM。

---

## 流水线总览

```
Step 0   count_paragraphs.py
Step 1a  LLM：著作+卷名 → protagonists.json（不读段落）
Step 1b-α  LLM：读全文 → primary_subjects.json（逐段 narrative 主语）
Step 1b-β  v2_aggregate_blocks.py → blocks.json（机械合并）
Step 1b-C  v2_blocks_gate.py（硬门）
Step 1b-D  v2_expand_to_skeleton.py → skeleton.json
Step 1b-E  （可选）边界失败时 LLM 只修交界 ±3 段 → 重跑 C/D
Step 2   check_format.py --phase skeleton
Step 3   historiography-audit
Step 4   fill_fields → peak_year → check_format --phase final
Step M   merge_volumes.py
```

**分支**：

| narrative_mode | Step1b |
|----------------|--------|
| skip | 不写 skeleton |
| single / fanzuo | **脚本机械 blocks**（不调 LLM） |
| hezhuan | **α LLM 逐段主语 → β 脚本合并 blocks** |

**任一 Step 失败 → STOP，从失败步重跑。**

---

## 路径（track=v2）

| 用途 | 路径 |
|------|------|
| 卷 skeleton | `data/10新标注条目/{著作}_{卷号}_{卷名}_skeleton.json` |
| 中间 · 主轴 | `data/05工作流中间产物/标注-v2/{著作}_{卷号}_protagonists.json` |
| 中间 · 逐段主语 | `data/05工作流中间产物/标注-v2/{著作}_{卷号}_primary_subjects.json` |
| 中间 · 划块 | `data/05工作流中间产物/标注-v2/{著作}_{卷号}_blocks.json` |
| **混写卷清单** | `data/10新标注条目/标注进度/{著作}_混写卷.json` |
| 段落索引 | `data/03索引标注条目/段落索引/`（v1/v2 共用 SSOT，不在 10 下复制） |

**混写卷怎么记**：Step1a/`protagonists.json` 写 `volume_texture: "interleaved"`；expand 写入 skeleton 同名字段，并自动登记清单。查询：

```bash
python3 historiography-annotate-v2/scripts/v2_interleaved_registry.py --work 01史记 --list
python3 historiography-annotate-v2/scripts/v2_interleaved_registry.py --work 01史记 --vol 081
```

翻译质检：清单内卷须按 `entries[].paragraphs` **多段拼接**读，勿按段号顺序假定连贯。

Skill 目录：`historiography-annotate-v2/`

---

## Step 0 · 段落数

```bash
python3 pandahis/pandahis/tools/openclaw-historiography/historiography-annotate/count_paragraphs.py \
  --work 01史记 --vol 001
```

---

## Step 1a · 卷主轴（LLM · 不读段落）

与旧 v2 相同：仅据著作+卷名锁主人公（默认 ≤5），产出 `protagonists.json`。  
**例外**：《周本纪》允许 **6** 人（补周穆王：犬戎/甫刑）；`protagonists.json` 可写 `protagonists_cap_note` 说明。

| 模式 | 人数 |
|------|------|
| single | 1 |
| hezhuan | 2–5 |
| fanzuo | 1 |
| skip | 0 |

须含 `narrative_mode` 与 `volume_subtype`（见规则文档）：

- `benji_multi` — 多人本纪（五帝本纪）
- `liezhuan_hezhuan` — 列传合传（屈原贾生）
- `liezhuan_single` / `shijia` / 等

**禁止** Step1a 读段落原文。

### 卷型 A / B / C（Step1a 先定「怎么切」，不是见世家就一种切法）

| 代号 | 什么意思 | 例子 | narrative_mode |
|------|----------|------|----------------|
| **A 单人卷** | 整卷 basically 一个人 | 项羽本纪、秦始皇本纪、**孔子世家** | `single` |
| **B 多人卷** | 卷里好几个「重头戏」 | 秦本纪、吴太伯世家、齐太公世家 | `hezhuan`（2–5 人） |
| **C 合传** | 卷名多人或并列 | 屈原贾生（顺接）/ 廉颇蔺相如（**混写**） | `hezhuan` + `liezhuan_hezhuan` |

混写合传（`volume_texture=interleaved`）：双「X者」同段→归段首；双人同场→叙事主推进者；配角戏挂主轴。详见 `Step1b-整卷划块专则.md`「混写合传」。

注意：

- **世家 ≠ 国君**（孔子是文臣，不是诸侯）
- **世家也不一定是多人卷**（孔子世家是 **A**）
- **吴太伯世家是 B**（多个吴国国君 + 中间享国链划出去）

Step1a JSON 建议增加字段 **`volume_arc`**：`"A"` / `"B"` / `"C"`（与 `narrative_mode` 一致即可）。

### 卷型黄灯（只提醒，不拦批量）

跑完 skeleton 自检后，脚本会比对：**Step1a 说的卷型** 和 **实际切法** 是否搭调。例如：

- 判成 **A** 却切出多条 entry → ⚠️ 像 B，请抽检
- 判成 **B** 却几乎整卷一人 → ⚠️ 像 A（031 初版就是这种）

**默认不 FAIL**，批量可继续；你愿意时再改那一卷。

```bash
python3 historiography-annotate-v2/scripts/v2_volume_profile_hints.py \
  --work 01史记 --vol 031
```

---

## Step 1b · 段落归属

### single / fanzuo（脚本 · 不调 LLM）

```bash
python3 historiography-annotate-v2/scripts/v2_expand_to_skeleton.py \
  --work 01史记 --vol 007 --mechanical
```

- exclude：卷首标题（汉书 P1）+ 太史公曰/论赞/赞曰
- 史记本纪/列传 P1 通常**非**卷首 exclude，归入 narrative block
- 其余段落 → 唯一主人公（single）或蕃祚 entry（fanzuo）

### hezhuan（Step1b-α LLM + Step1b-β 脚本）

1. **Read** 段落索引全文 P1..PN（必须读完，不可跳段）
2. **Read** `prompts/step1b_primary_subjects.md` + `reference/Step1b-整卷划块专则.md`
3. 对照 Step1a 的 `volume_subtype` 选用卷型参数（开传信号、更替归属）
4. **Step1b-α** 产出 `primary_subjects.json`（每段 `primary_subject` + `disposition`）
5. **Step1b-β** 运行 `v2_aggregate_blocks.py` 合并为 `blocks.json`
6. **禁止** LLM 直接写 blocks / skeleton / `segment_attribution`

```bash
# 仅重跑聚合（已有 primary_subjects 时）
python3 historiography-annotate-v2/scripts/v2_aggregate_blocks.py \
  --work 01史记 --vol 032

# 单卷流水线（hezhuan 自动走 α→β）
python3 historiography-annotate-v2/scripts/run_v2_volume_llm.py \
  --work 01史记 --vol 032 --skip-1a --skip-primary-subjects
```

### blocks.json 要点（Step1b-β 产出）

```json
{
  "total_paragraphs": 42,
  "volume_subtype": "benji_multi",
  "excludes": [
    {"paragraph_from": 41, "paragraph_to": 41, "exclude_reason": "太史公曰"}
  ],
  "blocks": [
    {
      "name": "尧",
      "category": "君王",
      "paragraph_from": 14,
      "paragraph_to": 27,
      "boundary_evidence": {
        "open_paragraph": 14,
        "open_phrase": "帝喾娶陈锋氏女",
        "close_note": "P27 尧崩禅让收束，末句「是为帝舜」仍归尧"
      }
    }
  ],
  "multi_owner_segments": []
}
```

- **`共段总述` exclude**：段内**并列**点名多位 Step1a 主轴，**无单一叙事主角**，无法归一人（如五帝本纪 P40）→ **exclude**，**禁止** multi_owner
- `boundary_evidence.open_phrase` **必须**为原文子串（gate 校验）
- `multi_owner_segments`：**v2 不使用**（平行多归属一律 `共段总述` exclude）

### Step 1b-B · 硬门

```bash
export HIST_ANNOTATE_TRACK=v2
python3 historiography-annotate-v2/scripts/v2_blocks_gate.py \
  --work 01史记 --vol 001
```

检查：覆盖 1..N · v2 exclude 白名单 · 禁止夹心 exclude · 边界证据子串 · 块名 ∈ Step1a

### Step 1b-C · 展开 skeleton

```bash
python3 historiography-annotate-v2/scripts/v2_expand_to_skeleton.py \
  --work 01史记 --vol 001
```

### Step 1b-D · 边界专审（gate 报 `BOUNDARY_*` 时）

仅重读失败交界 **±3 段**，修正对应 block 的 `paragraph_from/to` 与 `boundary_evidence`，重跑 gate + expand。**禁止**为修边界重跑全文逐段。

---

## Step 2–4 · Step M

与 v1 脚本共用，执行前 `export HIST_ANNOTATE_TRACK=v2`：

```bash
python3 .../historiography-annotate/check_format.py skeleton.json --phase skeleton
python3 .../historiography-audit/audit_precheck.py skeleton.json
python3 .../historiography-annotate/fill_fields.py skeleton.json
python3 .../historiography-annotate/peak_year.py skeleton.json --llm
python3 .../historiography-annotate/check_format.py skeleton.json --phase final
python3 .../historiography-annotate/merge_volumes.py 01史记
```

---

## Done when（Step 1）

- [ ] Step 0 通过
- [ ] 已 Read 规则 + Step1b 专则
- [ ] Step1a 合法；hezhuan 已产出 primary_subjects.json + blocks.json（非 skeleton 直写）
- [ ] `v2_blocks_gate.py` exit 0
- [ ] `v2_expand_to_skeleton.py` 落盘 skeleton
- [ ] `segment_attribution` 1..N 完整；与 entries 双向一致

---

## 与 v1 / 旧 v2 对照

| 项 | v1 | 旧 v2 | **v2.5（本版）** |
|----|----|-------|------------------|
| Step1b | 块优先 + 宽 exclude | hezhuan 逐段 LLM | **α 逐段主语 LLM + β 脚本合并 blocks** |
| exclude | 10 种 | 4 种 | **5 种（含共段总述）+ gate** |
| 覆盖保证 | expand | LLM 自填 N 行 | **expand 硬门** |
| 边界 | 文档要求，无 gate | 逐段隐式 | **boundary_evidence + 专审** |
| 本纪/合传 | 混用 | 规则区分 | **volume_subtype 参数化** |

---

## 测试建议

见 `reference/测试卷清单.md`：含 v1 问题卷与 v1 正常卷对照组。
