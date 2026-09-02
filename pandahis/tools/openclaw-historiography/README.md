# 历史图谱标注与翻译工具

本目录从 OpenClaw 历史类 skills 迁移而来，路径与脚本已对齐项目 `data/` 目录。

## 数据目录（相对 `HISTOGRAPH_ROOT`，默认 `pandahis/pandahis`）

| 用途 | 路径 |
|------|------|
| 原文母本 | `data/00原文母本/二十四史原文/` |
| 史料原文 | `data/02二十四史拆分后/` |
| 标注索引（v2） / skeleton / 段落索引 | `data/10新标注条目/`（现行 SSOT） |
| 标注索引（v1 历史） | `data/03索引标注条目/`（废弃待删；勿再作为默认输入） |
| 翻译终态产出（v2） | `data/11新标注条目翻译/` |
| 翻译终态产出（v1 历史） | `data/04史料翻译/` |
| 翻译汇总 | `data/11新标注条目翻译/` 或 `data/04史料翻译/史略翻译_汇总.json` |
| **中间产物** | `data/05工作流中间产物/`（标注 / 翻译 / 编排） |

路径 SSOT：`paths_config.py`（含根目录硬校验，禁止指向 OpenClaw / 旧桌面目录）

工作流约束：`WORKFLOW.md`  
执行前自检：`python3 scripts/verify_workflow_roots.py`

## LLM Provider

```bash
export HIST_LLM_PROVIDER=deepseek   # 默认 deepseek；可选 openclaw
export DEEPSEEK_API_KEY=你的密钥
```

详见 `.env.example`。

## 常用命令

```bash
# 标注（v2）
export HIST_ANNOTATE_TRACK=v2
# Agent 入口见 historiography-pipeline-v2/SKILL.md · historiography-annotate-v2/SKILL.md
python3 historiography-pipeline/run_volume_pipeline.py --track v2 next --work 01史记

# 翻译
cd historiography-translate
python3 translate.py init
python3 translate.py run-one --id GLBL_00001 --dry-run
```

## 目录结构

- `llm/` — OpenClaw / DeepSeek provider
- `paths_config.py` — 工作流路径配置
- `historiography-annotate/` — 标注共享脚本与规则 SSOT（见 README）
- `historiography-annotate-v2/` — 标注 Agent 入口（Step 1/4）
- `historiography-translate/` — 翻译脚本
- `historiography-pipeline/` — 单卷流水线脚本（`run_volume_pipeline.py`）
- `historiography-pipeline-v2/` — 标注调度 Agent 入口
- `historiography-orchestrator/` — v1 批量编排（维护用，见 README）
- `historiography-audit/` — 审计预检
- `historiography-compose/` — 翻译规则
