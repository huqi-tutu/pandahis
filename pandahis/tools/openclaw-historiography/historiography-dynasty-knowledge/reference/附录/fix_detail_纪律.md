# 精准改稿纪律（fix-detail · DeepSeek）

> **定位**：Kimi 检出硬史实错误后，DeepSeek **局部替换**，不是 compose-detail 从零/整篇重写。

---

## 与 compose-detail 的区别

| | compose-detail | fix-detail |
|---|----------------|------------|
| 输入 | 锚点 + 书目 + 规范 | **现有成稿** + Kimi `factual_errors` |
| 输出 | 整篇新 `翻译详情` | `edits[]` 局部 `original→revised` |
| 温度 | 按分类 0.3 等 | **0** |
| 纪律 | 起承转合、字数、开篇 | **只改错句，其余尽量不动** |

---

## 流程（review ↔ fix 循环）

```
第1轮 Kimi → 有错 → fix（正文+参考著作同步）
第2轮 Kimi → 有错 → fix
第3轮 Kimi → 仍有错 → forced_pass（不再 fix，不阻断 gate）
```

- 最多 **3 轮** Kimi 核查（`MAX_REVIEW_FIX_ROUNDS`）
- 典籍名/篇名错误：**正文与 `*参考著作` 段须同步改**
- `forced_pass` 条目见 `review_warns_汇总.md`，须人工裁定

关闭自动改稿：`--no-auto-fix-review`

产物：
- `logs/fixes/{史略ID}_fix_r{N}.json`
- `logs/reviews/{史略ID}_review.json`（含 `review_fix_round`、`forced_pass`）
