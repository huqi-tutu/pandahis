---
name: historiography-audit
description: >
  史料标注 Step 3（须 historiography-pipeline 调度）。预检 + LLM 六条语义审计。
  激活词：史料审计、Step 3、人物标注审计。
---

# 史料标注质量审计（Step 3 · 人物标注）

上游：`historiography-annotate` Step 1–2  
下游：Step 4 `fill_fields.py`

## Prerequisites

```bash
python3 historiography-annotate/check_format.py skeleton.json --phase skeleton
python3 historiography-audit/audit_precheck.py skeleton.json
```

**LLM 审计前必读**：`historiography-annotate/reference/人物标注规则.md`

---

## 6 条自检（LLM 层）

| # | 检查 |
|---|------|
| 1 | 喊数：全文段落已覆盖（块优先展开后 1..N 无遗漏） |
| 2 | 段落覆盖：无遗漏 |
| 3 | 原文引用：spot-check |
| 4 | 密度：对照 precheck |
| 5 | 人物归类：四类 + 优先级 |
| 6 | 合传主人公 / 本纪多君王 + **合传块边界无张冠李戴** |

预检已覆盖：密度阈值、孤儿归属、废弃分类、单段单归属。

---

## 结论

| 结论 | 下一步 |
|------|--------|
| ✅ 修正后通过 | Step 4 |
| ❌ 退回 | Step 1 重标 |

删条目须同步 `segment_attribution`；ID 保留空号。模板：`reference/审计模板.md`

---

## 落盘

`$HISTOGRAPH_ROOT/data/03索引标注条目/标注审计/{编号}{著作名}_标注审计.md`

**每卷独立 `## 卷NNN` 区块**，禁止全书只写一次。
