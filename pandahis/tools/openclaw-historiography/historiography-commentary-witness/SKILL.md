---
name: historiography-commentary-witness
description: >
  史略评述（08）与见证（09）数据补全。见证含实物文物与文学虚拟见证（后世诗歌、词曲、戏剧等）。
  同一 Skill、子命令分开；按 GLBL 或朝代批量，固定 DeepSeek v4 Pro。激活词：评述补全、见证补全、
  文物补全、文学见证、08评述、09见证、commentary、witness。
origin: ECC
---

# 评述与见证补全工作流

## 唯一生效规范（必读）

| 文档 | 用途 |
|------|------|
| [`reference/评述遴选规则.md`](reference/评述遴选规则.md) | **评述 SSOT**（`cw.py` 实际注入） |
| [`reference/见证遴选规则.md`](reference/见证遴选规则.md) | **见证 SSOT**（`cw.py` 实际注入） |
| [`reference/schema.md`](reference/schema.md) | JSON 字段 / 文件名 |
| [`reference/execution-discipline.md`](reference/execution-discipline.md) | 逐条、verify、DoD |
| [`reference/质量与常见失败.md`](reference/质量与常见失败.md) | 质量偏差原因与下一轮优化 |

动笔前必须读对应 mode 的遴选规则 + schema；禁止只读本 SKILL 摘要。

## 与相邻模块的关系

| 模块 | 职责 | 产出 |
|------|------|------|
| **historiography-annotate-v2** | 卷级人物标注 | 10 索引 |
| **historiography-dynasty-knowledge** | 朝代知识 + 详情 | 06 |
| **historiography-person-relations** | 人物关系图谱 | 07 |
| **historiography-commentary-witness**（本 skill） | **评述 + 见证（实物 + 文学）** | **08 / 09** |

- **覆盖全部史略分类**（君王/宗戚/文臣/武将/宦官/庶众/蕃祚/论著/典制/事略…）
- **输入**：史略 ID、名称、朝代 + 遴选规则；评述会读取 `04`/`06` 详情文末**参考著作**作排除清单
- **评述**：增量、评价性、差异化；**优先正史论赞**（太史公曰/赞曰/史臣曰等，可破主书名排除）；禁止翻译体；上古存在性质疑可选但非片尾
- **见证**：实物 A+→F→E 分层；附加 F **额外 0–1 条**（最知名名作，不计 1–5 主名额）；E/F 不得 P0
- **子命令分开**：`commentary-*` 与 `witness-*` 独立
- **批次**：结束后 `python3 cw.py verify-dynasty-commentary --dynasty <朝代>`

## When to Activate

- 「梳理某朝代所有史略的评述 / 见证（文物或文学）」
- 「给某某史略补评述 / 补见证 / 补文学见证」
- 提到 `08评述`、`09见证`、`GLBL_*_P01`、`GLBL_*_W01`

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

## 空结果策略

- 仍写出正式 JSON
- `status` = `"已处理·无可用"`
- `entries` = `[]`
- 计为**已处理**（进入 manifest）

## 执行清单（每条史略 · 每个 mode）

```
Task Progress:
- [ ] 1. 确认 mode 与目标（--id / --name / --dynasty）
- [ ] 2. 读 reference 遴选规则 + schema
- [ ] 3. cw.py {mode}-one
- [ ] 4. verify --strict（CRITICAL=0）
- [ ] 5. 批量结束后 verify-dynasty-commentary
```

## 命令

```bash
export HISTOGRAPH_ROOT=/path/to/pandahis/pandahis
cd tools/openclaw-historiography/historiography-commentary-witness/scripts

python3 cw.py test-llm
python3 cw.py commentary-one --id GLBL_00129
python3 cw.py witness-one --id GLBL_00129
python3 cw.py verify-commentary --id GLBL_00129 --strict
python3 cw.py verify-witness --id GLBL_00129 --strict
python3 cw.py verify-dynasty-commentary --dynasty 五帝
```

**LLM**：`HIST_LLM_PROVIDER=deepseek`、`DEEPSEEK_MODEL=deepseek-v4-flash`。
