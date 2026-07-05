# 历史图谱标注与翻译工作流 — 项目内约束

## 唯一真相（SSOT）

| 类型 | 位置 |
|------|------|
| 脚本 / 规则 / prompt | `pandahis/pandahis/tools/openclaw-historiography/` |
| 路径配置 | `paths_config.py` |
| LLM 调用 | `llm/`（默认 DeepSeek，不用 OpenClaw agent 落盘） |
| 原文母本 | `data/00原文母本/二十四史原文/` |
| 史料原文（拆分） | `data/02二十四史拆分后/` |
| 标注终态产出 | `data/03索引标注条目/` |
| 翻译终态产出 | `data/04史料翻译/` |
| **中间产物 / 运行态** | `data/05工作流中间产物/` |

### `05工作流中间产物` 子目录

| 子目录 | 用途 |
|--------|------|
| `标注/` | 标注 LLM 草稿、召回缓存等中间文件 |
| `翻译/` | 翻译 plan、分块 chunks、chunk 正文等 |
| `翻译/队列/` | 翻译队列 state.sqlite |
| `编排/` | 编排 state.sqlite、active_job、decisions、allow_force |

**禁止**再改 `~/.openclaw-autoclaw/skills/` 或 `~/Desktop/历史图谱`。

## 环境变量（建议写入 `.env` 或 shell profile）

```bash
export HISTOGRAPH_ROOT=/Users/rachelcheng/Desktop/padanhis/pandahis/pandahis
export HIST_LLM_PROVIDER=deepseek
export DEEPSEEK_API_KEY=...
```

不设 `HISTOGRAPH_ROOT` 时，默认就是上面的项目根。

## 执行入口（只用项目脚本）

```bash
# 自检
python3 tools/openclaw-historiography/scripts/verify_workflow_roots.py

# 翻译
cd tools/openclaw-historiography/historiography-translate
python3 translate.py init

# 标注编排
cd ../historiography-orchestrator
python3 hist.py bootstrap --work 01史记
```

不要用 `openclaw agent`、飞书 hist-worker、或 OpenClaw skill 目录里的副本脚本跑生产。

## 修改规范

1. 改规则 → 改项目内 `reference/`、`prompts/`、`翻译规则.md`
2. 改路径 → 只改 `paths_config.py`
3. 改 LLM → 只改 `llm/`，保持 `HIST_LLM_PROVIDER=deepseek`
4. 终态 JSON/MD → `data/03*` / `data/04*`
5. **中间产物** → `data/05工作流中间产物/*`（由 `paths()` 决定）

## 为什么不会跑到 OpenClaw

- 数据读写路径全部经 `paths_config.histograph_paths()`，且 `validate_histograph_root()` 禁止外部根目录
- DeepSeek 模式下模型只返回文本，由脚本解析后写入 `artifact_paths` 指定文件
- OpenClaw provider 仅作兼容保留；默认已关闭
