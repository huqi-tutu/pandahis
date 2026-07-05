## Step 1 任务（skeleton fallback · 仅 blocks 不可用时）

优先走 **blocks 草稿**（见 `step1_blocks.md`），由 `expand_blocks` 展开。  
**禁止**自创 JSON 结构（`attribution` / `entry_index` / `from`·`to` / entries 内嵌段落 `text`）。

若环境强制要求完整 skeleton，须按下述格式，并**严格遵守页眉【正文结构】**。

### 标准 skeleton 格式

```json
{
  "volume": "郦陆朱刘叔孙传",
  "source_file": "02汉书_053_郦陆朱刘叔孙传第十三.txt",
  "total_paragraphs": 17,
  "volume_type": "纪传叙事",
  "segment_attribution": [
    {"paragraph": 1, "owners": [], "exclude_reason": "卷首标题"},
    {"paragraph": 2, "owners": [{"name": "郦食其", "category": "文臣"}]},
    {"paragraph": 17, "owners": [], "exclude_reason": "赞曰"}
  ],
  "entries": [
    {
      "史略ID": "HANSHU_053_01",
      "史略名称": "郦食其",
      "史略简介": "郦食其",
      "原文字句": "郦食其，陈留高阳人也。好读书，家贫落魄，无衣食业。为里监门，然吏县中贤豪不敢役，皆谓之狂生。",
      "史略分类": "文臣",
      "主要史料出处": "《汉书·卷53·郦陆朱刘叔孙传》",
      "paragraphs": [{"volume": "郦陆朱刘叔孙传", "paragraph_from": 2, "paragraph_to": 4}]
    }
  ]
}
```

**硬性字段名（禁止改名）**

| 位置 | 必须 | 禁止 |
|------|------|------|
| segment_attribution | `owners[]` + `name`/`category` 或 `exclude_reason` | `attribution`、`entry_index`、`from`/`to` |
| entries | `史略ID`、`史略名称`、`史略分类`、`原文字句`、`paragraphs[]` | `name`、`entry_index`、内嵌 `text` |
| entries.paragraphs | `volume`、`paragraph_from`、`paragraph_to` | `paragraph`、`from`/`to` |

### 划段要点（依页眉【正文结构】，勿混用著作规则）

| 著作 | P1 | 论赞 | 原文字句 |
|------|----|------|----------|
| **汉书** | 多为 `卷首标题` exclude；正文从 P2 | `赞曰`（非太史公曰） | 取 entry **开篇段**段首逐字 ≥12 字 |
| **史记** | 无卷首标题；P1 即叙事 | `太史公曰` | 同上 |

- 合传：按 Step1a 人物顺序与**传记段首**划界；同段接力时从下一人起笔段起归其人
- 君王 `史略名称` = `帝王.json`「帝王名称」标准名
- `史略简介` ≤20 字

### Done

1. blocks 或 skeleton 落盘
2. 回复：`STEP1_DONE` 或 `STEP1_BLOCKS_DONE` + 块数/条目数
