# 人物关系补全 · 执行纪律（ECC）

## 核心原则

1. **SSOT 优先**：taxonomy 以 `关系数据整理提示词.md` 为准；字段以 `schema.md` 为准。
2. **逐人串行**：一次只完成一个 `{名称}关系表.json`，verify 通过后再下一人。
3. **Verify 门禁**：未通过 `verify_relations.py` 的文件视为未完成。
4. **证据约束**：每条 `关系简述` 须能在项目详情、史料译文或公认典籍中找到依据；不确定则不写。
5. **最小充分**：适用子类写全；不适用子类留空；不为凑满四级编造节点。

## 禁止事项

- 禁止为非人物类史略建表
- 禁止一次 prompt 输出多人物合并 JSON
- 禁止 `关系层级` 为 `五级` 或更深
- 禁止跳过 verify 直接声称完成
- 禁止将外部敌手写入 `同僚·敌对`，或将同朝政敌写入 `外敌`；私交情谊写入 `好友` 而非 `同僚`

## Verify 严重级别

| 级别 | 含义 | 处理 |
|------|------|------|
| **CRITICAL** | 类别非法、层级超限、主题名不一致、ID 重复、链断裂、**同类别同层级同标题重复** | 必须修复 |
| **WARN** | 缺 `record_id`、边标签非推荐词、简述过短 | 建议修复 |
| **INFO** | legacy 类别名（君臣/旧敌对） | 仅非 strict 模式 |

## 单人工作流

```
relations.py compose-one --id GLBL_xxx
    ↓
DeepSeek v4 Pro 成稿（relations_lib：按类别分轮调用 + 失败重试）
    ↓
写入 data/07人物关系/{名称}关系表.json
    ↓
verify_relations.py --strict
    ↓
失败 → 自动修订一轮 → 再 verify
```

## 朝代批量工作流

```
筛人物清单（索引 × 朝代 × 六类）
    ↓
for each 人物:
    单人工作流
    append manifest
    ↓
verify 整个目录
```

## 完成定义（Definition of Done）

- [ ] 文件位于 `data/07人物关系/{名称}关系表.json`
- [ ] 数组非空（若该人物确无任何可考关系，需与用户确认后产出空数组并注明）
- [ ] `verify_relations.py` 退出码 0
- [ ] strict 模式下零 CRITICAL
- [ ] manifest（批量时）已更新
