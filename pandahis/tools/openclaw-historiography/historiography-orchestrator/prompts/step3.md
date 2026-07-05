## Step 3 任务（人物标注审计）

**目标**：复核 Step1 是否按**块优先**流程覆盖全文，并按 **人物标注规则** 正确提取人物与段落。

### 必读

1. 激活 `historiography-audit` skill  
2. Read：`reference/人物标注规则.md`  
3. 对照段落索引 + skeleton

### 必跑

- `check_format --phase skeleton`  
- `audit_precheck.py`

### 审计 MD（每卷独立区块）

路径：`data/03索引标注条目/标注审计/{著作}_标注审计.md`

```markdown
## 卷{三位卷号}：{卷名}

### 段落覆盖清单
（每段一行，禁止 P1-P5 压缩）

### 准入过程
…

### 声明块（6 条须全部出现）
- 喊数 / 段落覆盖 / 原文引用 / 密度 / 人物归类 / 合传主人公+块边界

### 审计结论
✅ 修正后通过
```

硬检：`semantic_audit_verify.py` 校验六条声明关键词。

### Done

- 审计 MD 已追加本卷区块  
- 回复：`STEP3_DONE`
