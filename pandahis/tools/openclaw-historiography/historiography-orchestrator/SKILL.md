---
name: historiography-orchestrator
description: >
  史料标注著作级编排（hist）。批量标注必须经 hist run-work，禁止对话内 for 循环。
  激活词：hist、run-work、bootstrap、标注队列。
---

# historiography-orchestrator

**著作级班长。** 一卷一 job、一步一 verify；进度写入 `data/05工作流中间产物/编排/state.sqlite`。

## 禁止

- ❌ 对话里「标完 58 卷」
- ❌ agent 自写批量脚本
- ❌ `mark --force` 刷 progress（须 `data/05工作流中间产物/编排/allow_force` 文件）
- ❌ 绕过 `hist.py` 直接循环 `run_volume_pipeline.py verify` / `fill_fields` / `check_format`

## 硬门（工具 enforce，违反 exit 2）

| 门 | 规则 |
|----|------|
| 编排租约 | `verify`/`mark`/`fill_fields`/`check_format` 须存在 `data/05工作流中间产物/编排/active_job.json`，且著作/卷号匹配 |
| 卷序 | 卷 N 操作前，卷 N-1 须 `overall=done`（progress.json） |
| 金标 | 非金标卷在 `approve-gold` 前拒绝 |
| init --scan | 每次最多登记**下一卷**（禁止一次扫 58 卷） |
| 修复通道 | 单卷手工修复：`HIST_REPAIR=1`（仅此模式可跳过 Step1 LLM） |
| Step1 时长 | **仅** `<5s` 硬失败（防秒回）；建议用时告警已关闭；**主门控为 verify** |
| Step3 时长 | 同上 |
| 原文挑战 | `evidence_verify`：8 段抽样 + 审计表与 skeleton 一致 |
| Step3 语义 | `semantic_audit_verify`：按卷独立块 + 段落覆盖表 + 六条声明 |
| Step3 打回 | 审计写 `❌ 退回` → verify 失败并重置本卷 Step1–3 jobs |
| Step2 帝王表 | verify 前 `step2_prepare`：合并待补录 + 从 skeleton 自动补帝王.json；**仅**帝王表/君王名失败不打回 Step1 |
| 长卷 Step1 | `total_paragraphs ≥ 40` → **blocks 模式**（LLM 只写 blocks.json，脚本 expand → skeleton） |
| Step3 审计 | **脚本-only**：`build_audit_block.py` 从 skeleton 生成审计 MD，**不调用 LLM** |
| 重试熔断 | 每步最多 2 次失败，超限 paused（防 token 死循环） |

唯一批量入口：

| 场景 | 命令 |
|------|------|
| **生产跑批（推荐）** | `hist run-batch --work 01史记 --loop` |
| 单书连续跑 | `hist run-work --work 01史记`（**勿**加 `--max-jobs 1`） |
| 调试单步 | `hist run-work --work 01史记 --max-jobs 1` |

**LLM 分工（不可脚本替代）**

| Step | LLM 负责 |
|------|----------|
| 1（短卷 <40 段） | 完整 skeleton |
| 1（长卷 ≥40 段） | **仅 blocks 草稿**（叙事块 + exclude） |
| 4 | 优先级、优先级判定理由（及缺年/坐标推断） |

Step3 由 `build_audit_block.py` 脚本生成，不占用 LLM。

Step 2 / 脚本 merge-auto / finalize 为硬检与坐标对齐，不替代上述判断。

## 批量跑批（2000+ 卷）

```bash
export HISTOGRAPH_ROOT=pandahis/pandahis
cd pandahis/pandahis/tools/openclaw-historiography/historiography-orchestrator

# 1. 金标卷人工确认一次（全书质量锚点）
python3 hist.py approve-gold --work 01史记

# 2. 无人值守循环（逐卷 Step1→4，每步仍调 hist-worker LLM）
export HIST_BATCH_AUTO=1          # 自动 resume / 坐标冲突默认 emperor-ssot
bash scripts/run_batch_daemon.sh 01史记

# 或前台跑一整本书直到阻塞
python3 hist.py run-batch --work 01史记 --loop
```

环境变量：

| 变量 | 默认 | 含义 |
|------|------|------|
| `HIST_BATCH_AUTO` | 0 | 1=自动 resume、自动坐标决策 |
| `HIST_AUTO_COORD` | emperor-ssot | 坐标冲突默认策略 |
| `HIST_AUTO_GOLD` | 0 | 1=自动 approve-gold（不建议，应人工金标） |
| `HIST_SCRIPT_PRIORITY` | 0 | 1=君王优先级脚本兜底（默认关，交 LLM） |
| `HIST_REPAIR` | 0 | 单卷手工修复，跳过 Step1 LLM |

效率要点：**不要用 `--max-jobs 1` 做生产**——那只会每跑 1 个 job 就停，相当于手动点 8000+ 次（2000 卷×4 步）。

## 命令（用户或 agent 只执行这些）

```bash
export HISTOGRAPH_ROOT=pandahis/pandahis
python3 pandahis/pandahis/tools/openclaw-historiography/historiography-orchestrator/hist.py bootstrap --work 01A尚书
python3 .../hist.py run-work --work 01A尚书
python3 .../hist.py status --work 01A尚书
python3 .../hist.py approve-gold --work 01A尚书
python3 .../hist.py approve-work --work 01A尚书
```

默认 LLM 为 **DeepSeek**（`HIST_LLM_PROVIDER=deepseek`）。若使用 OpenClaw agent，需 **AutoClaw / Gateway 运行**。

## 死锁规避（重要）

编排器 LLM 步调用 **`hist-worker` agent**（非 `main`）。  
若用 `main`，飞书对话正在占用 main 时会死锁：编排器等 main，main 等编排器。

飞书触发时流程：
1. 飞书 main 只执行 `hist.py`（exec）
2. `hist.py` 内部回调 **hist-worker** 做标注
3. 两者并行，不互相阻塞

### 常见误判（必读）

- ❌ **不要用 `agents_list` 判断 hist-worker** — 该工具对 main 通常只返回 `main`，但 CLI `openclaw agent --agent hist-worker` 仍可用
- ✅ 运行 `hist.py doctor` 验证 worker 与 Gateway
- ⏳ `run-work` 单步可能 **5–15 分钟无 stdout**，属正常；**禁止 kill** exec 进程
- exec 超时建议 **≥900 秒**（Step1）
- Step1/3：**&lt;5s 硬失败**（防秒回）；**无建议用时告警**；快慢以 verify 为准

卡住后：`hist resume --work 01A尚书`，再 `run-work --max-jobs 1`。

全书重标：`hist reset-work --work 01A尚书`（删除全部 skeleton + 重置 jobs）

审计批量烂卷：`hist audit-volumes --work 01A尚书`

## 段落与翻译

- 段落 SSOT：`data/03索引标注条目/段落索引/`（bootstrap 写入 `paragraph_mode`）
- 翻译召回：`historiography-annotate/recall_paragraphs.py`（与标注同段号，勿重切 txt）

## Step4 防漏字段

编排器 Step4 流程（LLM 不可删临时字段）：

1. `fill_fields.py` + `--merge-auto`（脚本合并归属/君纪年）
2. LLM 仅补 `_needs_llm` 所列缺失正式字段
3. `--verify` → `--finalize`（脚本删 `_auto_filled`）
4. `check_format --phase final`

失败时自动 `fill_fields` 恢复 scratch，可 `hist resume` 重试。

## 与下游

| 组件 | 角色 |
|------|------|
| hist | 著作队列、job、OpenClaw 调用 |
| historiography-pipeline | 卷级 verify（hist 内部调用） |
| historiography-annotate / audit | 单步 SOP（prompt 引用） |
