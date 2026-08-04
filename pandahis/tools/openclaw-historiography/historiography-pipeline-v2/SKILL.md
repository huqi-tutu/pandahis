---
name: historiography-pipeline-v2
description: >
  新版史料标注调度入口（v2 轨道 → data/10）。单卷 Step1→4 闭环；批量=逐卷重复。
  v2.5：逐段主语 + 脚本合并 blocks + gate + 展开。
  激活词：新版标注流水线、pipeline v2、新版标下一卷、新版批量标注。
---

# 新版史料标注流水线（v2 调度）

**本 skill 是 v2 批量标注的唯一入口。**  
细则：`historiography-annotate-v2`（v2.5 先逐段主语再合并 blocks）· Step 3：`historiography-audit`

## 轨道开关

```bash
export HIST_ANNOTATE_TRACK=v2
```

---

## v2.5 Step 1 流程（摘要）

```
Step1a  protagonists.json（LLM · 不读段）
Step1b-α  primary_subjects.json（LLM 逐段主语）
Step1b-β  blocks.json（v2_aggregate_blocks.py · 或 single/fanzuo 机械）
Step1b-C  v2_blocks_gate.py
Step1b-D  v2_expand_to_skeleton.py
Step 2–4  与 v1 脚本共用
```

详见 `historiography-annotate-v2/SKILL.md`。

---

## 单卷命令

### Step 0

```bash
export HIST_ANNOTATE_TRACK=v2
python3 .../historiography-annotate/count_paragraphs.py --work 01史记 --vol 001
```

### Step 1

1. 激活 **`historiography-annotate-v2`**
2. 必读：`reference/人物标注规则-v2.md` · `reference/Step1b-整卷划块专则.md`
3. Step1a → Step1b-α（LLM primary_subjects）→ Step1b-β（脚本 blocks，**非** skeleton）
4. 硬门 + 展开：

```bash
python3 .../historiography-annotate-v2/scripts/v2_blocks_gate.py --work 01史记 --vol 001
python3 .../historiography-annotate-v2/scripts/v2_expand_to_skeleton.py --work 01史记 --vol 001
```

5. single/fanzuo 可一步机械：

```bash
python3 .../historiography-annotate-v2/scripts/v2_expand_to_skeleton.py \
  --work 01史记 --vol 007 --mechanical
python3 .../historiography-annotate-v2/scripts/v2_blocks_gate.py --work 01史记 --vol 007
```

6. 验证：

```bash
python3 .../run_volume_pipeline.py --track v2 verify --work 01史记 --vol 001 --step 1
```

### Step 2–4 · Step M

与旧版相同，`--track v2` 或 `export HIST_ANNOTATE_TRACK=v2`。

---

## 测试

`historiography-annotate-v2/reference/测试卷清单.md`  
示例 blocks：`reference/examples/`（001 · 084 金标准，仅供对照）

---

## 与 v1 pipeline

| | v1 | v2 |
|--|----|----|
| 产出 | data/03 | data/10 |
| Step1b | 块优先 + 宽 exclude | **整卷划块 + v2 gate** |
| 进度 | 03/标注进度 | 10/标注进度 |
