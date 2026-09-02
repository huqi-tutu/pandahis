---
name: historiography-translate
description: >
  GLBL 全局索引 → 程序 M 清单 → 分批成稿 → 引入/结尾 → verify。
  规则 SSOT：historiography-compose/references/翻译规则.md。
---

# 史略翻译（GLBL 编排器）

## 精简四步（默认 `TRANSLATE_PIPELINE=streamlined`）

```
1. recall
2. 程序 M 清单（coverage ledger；无 LLM plan）
3. 分批成稿（每批完整规则；顺译+成稿时他书补充一次完成）
4. 引入（translate_intro.md）+ 结尾（translate_ending.md）两次短 call → 程序拼正文
5. verify（语义覆盖仅终稿；长文内部分批复核）
6. promote / sync（分离）
```

引入/结尾提示词：`prompts/translate_intro.md`、`prompts/translate_ending.md`（结尾不注入正文；不用 plan 前置素材；不灌整包规则）。

Legacy：`TRANSLATE_PIPELINE=abcd` 或 `legacy` 回退旧路径。

## 命令

```bash
export HISTOGRAPH_ROOT=/path/to/pandahis/pandahis
cd tools/openclaw-historiography/historiography-translate

python3 translate.py run-one --id GLBL_00149
python3 translate.py promote --id GLBL_00149 [--sync]
python3 translate.py verify --id GLBL_00149
```

## 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `TRANSLATE_PIPELINE` | `streamlined` | `abcd`/`legacy` 回退旧 ABCD |
| `TRANSLATE_MOTHER_BATCH` | `18` | 每批目标 M 条数（切批优先 P 边界） |
| `TRANSLATE_BATCH_TAIL_CHARS` | `600` | 上批末段白话注入字数上限 |
| `TRANSLATE_BATCH_MOTHER_TAIL` | `5` | 本批前注入的母本摘句条数 |
| `TRANSLATE_BATCH_SEMANTIC` | `0` | `1` 才在批内跑语义 L2（默认关） |
| `TRANSLATE_BATCH_MAX_RETRIES` | `2` | 分批成稿重试 |
| `TRANSLATE_AUTO_SYNC` | `0` | 试跑保持 0 |
| `TRANSLATE_LENGTH_RATIO` | `1.2` | 成稿 vs 母本软警告 |

## 中间产物

`data/05工作流中间产物/翻译/`

| 文件 | 说明 |
|------|------|
| `{id}_{名}.plan.json` | M 清单（coverage ledger） |
| `{id}_{名}.mother-bNN.json` | 分批成稿 |
| `{id}_{名}.mother.json` | 合并正文 |
| `{id}_{名}.assemble.json` | 引入+结尾 |

## 本传主退场补全（编排器实现）

规则写作要点见 `翻译规则.md` 规则二「本传主退场完整性」。程序侧：

| 步骤 | 模块 | 行为 |
|------|------|------|
| 1 | `apply_recall_subject_filter` | 从本条目母本过滤**他人**退场展开句 |
| 2 | `inject_exit_supplements` | 仅当 `find_exit_events_in_text(母本, 本传主)` 为空时，从同卷他条目提取退场句 → `本传缺漏补全` |
| 3 | `inject_exit_supplements_plan` | 生成 plan 项：`与母本关系: 母本段落域未收录该退场句，须在正文尾部补入` |
| 4 | 成稿动笔前 | 正文已交代退场 → 跳过该类 plan 项（即使误标 `采用:true`） |

交接双挂段按本传主镜头压缩他传侧；详见规则二「交接双挂段」。

## 相关 Skill

- [`historiography-compose`](../historiography-compose/SKILL.md)
