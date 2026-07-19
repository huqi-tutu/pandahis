# 评述与见证 · 执行纪律（ECC）

## 核心原则

1. **SSOT 优先**：遴选以 `评述遴选规则.md` / `见证遴选规则.md` 为准；字段以 `schema.md` 为准。
2. **子命令隔离**：`commentary-*` 与 `witness-*` 不得在同一次 prompt 中混写。
3. **逐条串行**：一次只完成一条史略的一个 mode；verify 通过后再下一条。
4. **Verify 门禁**：未通过 `--strict` 的文件视为未完成。
5. **证据约束**：评述须可考著作；文物须直接相关；不确定则不写，宁空勿凑。
6. **空结果合法**：确认无可用时写入 `status=已处理·无可用` + `entries=[]`，仍算完成。

## 禁止事项

- 禁止依赖翻译正文 / 段落原文作为本环节输入（仅用名称+朝代+分类+规则）
- 禁止让模型生成或猜测文物图片 URL（`文物图片` 恒为 `""`）
- 禁止一次 prompt 输出多史略合并 JSON
- 禁止跳过 verify 直接声称完成
- 禁止为凑满 3–5 条评述或 5 件文物而编造分歧 / 硬凑泛泛同时代物

## Verify 严重级别

| 级别 | 含义 | 处理 |
|------|------|------|
| **CRITICAL** | 缺必填、ID 非法/重复、史略不一致、字数越界、优先级重复、图片非空、status 与空数组矛盾 | 必须修复 |
| **WARN** | 条数建议区间外、年代排序可疑、现藏地点格式松散 | 建议修复 |
| **INFO** | 空结果已合法标记 | 仅记录 |

## 单条工作流

```
cw.py commentary-one | witness-one --id GLBL_xxx
    ↓
DeepSeek v4 Pro 成稿
    ↓
写入 08/09 正式 JSON
    ↓
verify-commentary | verify-witness --strict
    ↓
失败 → 修订一轮 → 再 verify
```

## 朝代批量工作流

```
筛索引（二级朝代坐标 = 目标朝代，全部史略分类）
    ↓
for each 史略:
    单条工作流（指定 mode）
    append manifest
```

## Definition of Done

- [ ] 文件位于 `data/08评述/` 或 `data/09见证/`，命名符合 schema
- [ ] `status` ∈ {`done`, `已处理·无可用`}；后者 `entries` 为空
- [ ] verify `--strict` 退出码 0，零 CRITICAL
- [ ] 批量时 manifest 已更新
