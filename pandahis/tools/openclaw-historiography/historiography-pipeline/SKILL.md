---
name: historiography-pipeline
description: >
  史料标注唯一调度入口。单卷 Step1→4 闭环；批量=逐卷重复本 skill，禁止自写批量脚本。
  激活词：标注流水线、pipeline、标下一卷、批量标注、标百卷、按流程标注。
---

# 史料标注流水线（总调度）

**本 skill 是批量标注与多步闭环的唯一入口。**  
`historiography-annotate` 只负责 Step 1/2/4 细则；`historiography-audit` 只负责 Step 3。不得跳过本调度直接「标完就下一卷」。

## 禁止项（违反即 STOP）

- ❌ **禁止** agent 自创 `批量标注.py` / 循环糊 JSON 的脚本
- ❌ **禁止** 一次会话标多卷（百卷 = 100 次单卷 pipeline）
- ❌ **禁止** 无 `progress.json` 记录就宣称「本卷完成」
- ❌ **禁止** 跳过 Step 3 审计或 Step 4 终检
- ❌ **禁止** 未跑 Step 0 / `verify` 失败时用 `mark --force` 刷 done（须 `data/05工作流中间产物/编排/allow_force`）
- ❌ **禁止** 尚书等按「2 段模板」批量产出（`check_format` / `verify` 会硬失败）
- ❌ **禁止** 绕过 `hist.py` 循环调用本脚本 `verify`/`mark`（无编排租约 exit 2）
- ✅ **只允许** `hist.py run-work --max-jobs 1` 驱动本脚本；单卷修复设 `HIST_REPAIR=1`

白名单脚本：

| 脚本 | 用途 |
|------|------|
| `historiography-pipeline/run_volume_pipeline.py` | 进度、验证、调度 |
| `historiography-annotate/count_paragraphs.py` | **Step 0** 段落数（标注前必跑） |
| `historiography-annotate/check_format.py` | Step 2 / Step 4 硬门 |
| `historiography-annotate/fill_fields.py` | Step 4 辅助 |
| `historiography-annotate/peak_year.py` | Step 4d 峰值年标注 |
| `historiography-annotate/merge_volumes.py` | 多卷合并（Step M） |
| `historiography-audit/audit_precheck.py` | Step 3 预检 |

---

## 进度文件（唯一真相）

路径：`$HISTOGRAPH_ROOT/data/03索引标注条目/标注进度/{著作}_progress.json`

每卷四步状态：`1` 标注 → `2` 格式 → `3` 审计 → `4` 补全  
**overall = done**（Step4 完成）才允许标下一卷（`hist_gates.py` 硬门 enforce）。

### 硬门说明

- `verify` / `mark` / `run`：检查上一卷 `overall=done` + 编排租约 + 金标
- `init --scan`：每次只登记下一卷（非 `HIST_REPAIR=1` 时）
- `fill_fields.py` / `check_format.py`：须匹配 `active_job.json` 中的卷
- 单卷修复：`export HIST_REPAIR=1`

---

## 单卷标准流程

### 0. 查下一卷

```bash
python3 pandahis/pandahis/tools/openclaw-historiography/historiography-pipeline/run_volume_pipeline.py next --work 01史记
```

### Step 0 — 段落数（脚本，标注前）

```bash
python3 pandahis/pandahis/tools/openclaw-historiography/historiography-annotate/count_paragraphs.py \
  --work 01A尚书 --vol 058
```

exit 0 → 记下「实际段落数」；尚书 = `　　` 行数。不得跳过。

### Step 1 — 标注（LLM）

1. 激活 **`historiography-annotate`**
2. 必读 reference：人物标注规则、人物归因、卷型补充（**尚书 + `尚书.md`**）
3. `total_paragraphs` 与 Step 0 一致；按**块优先**工作流展开 `segment_attribution`（1..N 每段一行；合传块边界须精读）
4. 落盘：`史料标注/{著作}_{卷号}_{卷名}_skeleton.json`
4. 验证：

```bash
python3 .../run_volume_pipeline.py verify --work 01史记 --vol 001 --step 1
```

### Step 2 — 格式硬门（脚本）

```bash
python3 .../run_volume_pipeline.py verify --work 01史记 --vol 001 --step 2
```

exit 0 → progress 自动记 done。失败 → 修 JSON，不得进 Step 3。

### Step 3 — 质检（预检脚本 + audit skill）

1. `verify --step 2` 已通过
2. 激活 **`historiography-audit`**，LLM 六条语义审计
3. 落盘：`data/03索引标注条目/标注审计/{著作}_标注审计.md`（**每卷独立 `## 卷NNN：卷名` 块**，含段落覆盖清单 + 声明块六条）
4. 删改条目后重跑 Step 2 + 预检
5. 验证（`semantic_audit_verify` + `evidence_verify` 硬检）：

```bash
python3 .../run_volume_pipeline.py verify --work 01史记 --vol 001 --step 3
```

### Step 4 — 补全（fill_fields + LLM + 峰值年 + 终检）

1. `fill_fields.py` 写临时字段，并自动补全四级坐标 ID
2. LLM 补：优先级、年份、文明/王朝/帝王归属（名称）；删 `_needs_llm`；**不得手填坐标 ID**
3. **`peak_year.py`（Step4d）**：年份终态后标注 `峰值年/峰值原因/峰值类型/峰值置信度`（规则 → LLM 分批 → 兜底；低置信进待审，不挡终检）
4. 验证：

```bash
python3 .../run_volume_pipeline.py verify --work 01史记 --vol 001 --step 4
```

### 本卷 Done when

- [ ] progress 中该卷 Step 1–4 均为 **done**
- [ ] `verify --vol XXX`（不指定 step）全部通过

然后才执行 `next` 开下一卷。

---

## 批量标注（正确说法）

用户说「标百卷」时，**必须回复并执行**：

> 按 pipeline 逐卷执行，一次只标一卷；每卷 Step1–4 全 done 后再 `next`。

不得改为写一个 for 循环脚本。

### 首批初始化

```bash
python3 .../run_volume_pipeline.py init --work 01史记 --scan
python3 .../run_volume_pipeline.py status --work 01史记
```

---

## Step M — 合并（著作级，非每卷必做）

全部或部分卷 `overall=done` 后：

```bash
python3 pandahis/pandahis/tools/openclaw-historiography/historiography-annotate/merge_volumes.py 01史记
```

---

## 会话纪律

- **一卷一会话**（或每卷结束后 compact / 新会话）
- 每步结束打印：`{著作} 卷{vol} Step{N} done`，并贴 `verify` 输出
- 用户追问「标完了吗」→ 只认 `status` / `progress.json`，不认口头声明

---

## 与下游 skill 关系

| Skill | 何时激活 |
|-------|----------|
| **historiography-pipeline**（本 skill） | 标一卷、标下一卷、批量、查进度 |
| historiography-annotate | 仅 Step 1 / 退回重标 / Step 4 补全 |
| historiography-audit | 仅 Step 3（Step 2 已过） |
