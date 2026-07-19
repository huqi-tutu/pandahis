---
name: historiography-commentary-witness
description: >
  史略评述（08）与见证文物（09）数据补全。同一 Skill、子命令分开；按 GLBL 或朝代批量，
  固定 DeepSeek v4 Pro。激活词：评述补全、见证补全、文物补全、08评述、09见证、
  commentary、witness。
origin: ECC
---

# 评述与见证补全工作流

## 与相邻模块的关系

| 模块 | 职责 | 产出 |
|------|------|------|
| **historiography-annotate** | 一期卷级人物标注 | 03 索引 |
| **historiography-dynasty-knowledge** | 朝代知识 + 详情 | 06 |
| **historiography-person-relations** | 人物关系图谱 | 07 |
| **historiography-commentary-witness**（本 skill） | **评述 + 见证文物** | **08 / 09** |

- **覆盖全部史略分类**（君王/宗戚/文臣/武将/宦官/庶众/蕃祚/论著/典制/事略…）
- **输入**：史略 ID、史略名称、二级朝代坐标 + 遴选规则；**不**依赖原文召回或翻译正文
- **子命令分开**：`commentary-*` 与 `witness-*` 独立；不默认两者同跑

## When to Activate

- 「梳理某朝代所有史略的评述 / 见证（文物）」
- 「给某某史略补评述 / 补文物」
- 提到 `08评述`、`09见证`、`GLBL_*_P01`、`GLBL_*_W01`

## 规范 SSOT（必读顺序）

| 顺序 | 文档 | 用途 |
|------|------|------|
| 1 | [`reference/评述遴选规则.md`](reference/评述遴选规则.md) | 评述：找分歧、跨时代、字段约束 |
| 2 | [`reference/见证遴选规则.md`](reference/见证遴选规则.md) | 见证：四维度、优先级、字段约束 |
| 3 | [`reference/schema.md`](reference/schema.md) | JSON 信封、ID、状态枚举 |
| 4 | [`reference/execution-discipline.md`](reference/execution-discipline.md) | ECC 逐条、verify 门禁 |

动笔前 **必须先读** 对应 mode 的遴选规则 + schema；禁止只读本 SKILL 摘要。

## 路径（相对 `HISTOGRAPH_ROOT` = `pandahis/pandahis`）

| 用途 | 路径 |
|------|------|
| **评述正式产出** | `data/08评述/{史略ID}_{史略名称}_评述.json` |
| **见证正式产出** | `data/09见证/{史略ID}_{史略名称}_见证.json` |
| 中间产物 / logs | `data/05工作流中间产物/评述见证补全/` |
| 史略索引 | `data/03索引标注条目/史略索引_01至02.json` |
| 批次 manifest | `data/08评述/{朝代}_评述_manifest.json` / `data/09见证/{朝代}_见证_manifest.json` |

## ID 规则

| 类型 | 格式 | 示例 |
|------|------|------|
| 评述 | `{史略ID}_P{序号两位}` | `GLBL_00129_P01` |
| 见证 | `{史略ID}_W{序号两位}` | `GLBL_00129_W01` |

同一文件内序号从 `01` 起连续；条目为空时不生成 ID。

## 空结果策略

找不到有实质分歧的评述、或找不到直接相关文物时：

- 仍写出正式 JSON
- `status` = `"已处理·无可用"`
- `entries` = `[]`
- 计为**已处理**（进入 manifest）

## 执行清单（每条史略 · 每个 mode）

```
Task Progress:
- [ ] 1. 确认 mode（commentary | witness）与目标（--id / --name / --dynasty）
- [ ] 2. 读对应遴选规则 + schema
- [ ] 3. cw.py {mode}-one（DeepSeek v4 Pro）
- [ ] 4. verify 门禁 --strict（CRITICAL=0）
- [ ] 5. （批量）更新 manifest
```

**禁止**一次 prompt 混写多史略；**禁止**跳过 verify 声称完成；**禁止**让模型填写文物图片 URL（字段恒为空字符串）。

## 命令

```bash
export HISTOGRAPH_ROOT=/path/to/pandahis/pandahis
cd tools/openclaw-historiography/historiography-commentary-witness/scripts

python3 cw.py test-llm

# —— 评述 ——
python3 cw.py commentary-one --id GLBL_00129
python3 cw.py commentary-one --name 舜 --dry-run
python3 cw.py commentary --dynasty 五帝 --max 3
python3 cw.py verify-commentary --id GLBL_00129 --strict

# —— 见证 ——
python3 cw.py witness-one --id GLBL_00129
python3 cw.py witness --dynasty 五帝 --max 3
python3 cw.py verify-witness --id GLBL_00129 --strict
```

**LLM**：脚本强制 `HIST_LLM_PROVIDER=deepseek`、`DEEPSEEK_MODEL=deepseek-v4-pro`。

## 输出质量门禁（摘要）

**评述**：ID 形如 `*_P##`；标题「史略名·角度」；简介 ≤20 字；内容 50–200 字；同文件史略 ID/名称一致；空文件须 `已处理·无可用`。

**见证**：ID 形如 `*_W##`；优先级 P0–P4 不重复；介绍 100–200 字；`文物图片` 必须为 `""`；空文件须 `已处理·无可用`。

详见 `reference/execution-discipline.md`。

## 附加资源

- Schema → [reference/schema.md](reference/schema.md)
- 执行纪律 → [reference/execution-discipline.md](reference/execution-discipline.md)
- 源头提示词（人类参考，以本目录 reference 为准）：
  - `pandahis/评述数据整理提示词.md`
  - `pandahis/文物数据整理提示词.md`
