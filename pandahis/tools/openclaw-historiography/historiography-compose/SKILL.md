---
name: historiography-compose
description: >
  史略译文 SSOT 入口：规则在 references/翻译规则.md；批量生产走 historiography-translate。
  手工单条 compose 须先读规则再动笔。
---

# 史料融合生成（SSOT 入口）

## 何时使用

- 需要了解或修改**史略翻译规则**（十二条 + 流水线约定）
- 手工 compose 单条译文（不经过编排器）
- 排查 translate 流水线与规则不一致的问题

**批量翻译不要在本 skill 里跑命令** → 使用 [`historiography-translate`](../historiography-translate/SKILL.md)。

## 规则 SSOT（唯一）

| 文件 | 作用 |
|------|------|
| [`references/翻译规则.md`](references/翻译规则.md) | **全部**写作原则、顺译定义、两阶段成稿、外部补全准入、验收标准 |

> 禁止在 SKILL 正文重复规则全文。Agent/编排器须通过 `rule_bundle` **在每次 LLM 请求前注入**该文件相关章节。

## ECC 结构诊断（本仓库）

| 层级 | 应有 | 原先问题 | 现状态 |
|------|------|----------|--------|
| **Skill** | 何时用、执行清单、SSOT 指针 | compose 仅 49 行，无 checklist | 本文件 + translate SKILL 分工 |
| **Reference** | 完整规则 SSOT | 规则在 reference 但 skill 未强制读取 | translate 编排器全量注入 draft 阶段 |
| **Prompt** | 阶段任务 + 规则节选 | 规则只在 verify 卡点 | Phase1/2 prompt 含四层 rule_bundle |
| **Verify** | 兜底质检 | 曾替代写作约束 | 与 prompt 同标准，不单独加严 |

**硬伤（已缓解）**：规则 living 在 reference 但 skill 太薄 → Agent 易跳过；**修复**：translate SKILL 写死执行顺序，runner 强制两阶段 + rule_bundle 全量注入。

## 手工 compose 执行清单

1. 通读 [`翻译规则.md`](references/翻译规则.md) 第零部分 + 规则一至十二
2. `recall_paragraphs.py` 召回母本（禁止读 `.txt` 自切）
3. **前置引入**：写 1-2 段引入，交代朝代身份定位 + 自然过渡句
4. **Phase1**：仅母本顺译（引原词 + 释词，无他书）
5. **Phase2**：在锚点补入异说/背景/细节（禁止重复母本）
6. 按规则十一自检（含引入检查 + 破折号检查），再落盘 JSON

## 召回示例

```bash
export HISTOGRAPH_ROOT=pandahis/pandahis
python3 pandahis/pandahis/tools/openclaw-historiography/historiography-annotate/recall_paragraphs.py \
  --skeleton "$HISTOGRAPH_ROOT/data/03索引标注条目/01史记_001_五帝本纪第一_skeleton.json" \
  --entry-id SHIJI_001_01 --json
```

## 产出

| 路径 | 说明 |
|------|------|
| `data/04史料翻译/{史略ID}_{史略名称}.json` | 编排器标准产出（推荐） |
| `产出/` 样例 | 手工 compose 本地格式参考 |
