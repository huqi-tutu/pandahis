## Step 1 任务（blocks 草稿 · 全著作通用）

**前置**：须已完成 **Step1a**（`protagonists.json`）且 **identity_gate 已通过**。  
本步 **只读段落索引原文**，按 Step1a 清单划块；**禁止**改用正文里出现的皇帝/太后当新主轴。

编排器可用 `expand_blocks` 机械展开；**禁止**直接输出完整 skeleton（除非环境强制 fallback）。

### 你只负责

1. 读段落索引 `paragraphs[].text` —— **必须先读 P1 全文**
2. 对照页眉 **【正文结构 · …】**（按著作拆分 txt 实际形态，与 `classify_paragraph_header` 一致）
3. 标 **叙事 blocks** + **excludes**
4. 写出 **blocks 草稿 JSON**

### 按著作区分（必读页眉结构提示）

| 形态 | 典型著作 | P1 | 卷末论赞 | 合传 |
|------|----------|----|---------|----|
| 无卷首标题，开篇即叙事 | 史记 | 正文归 block，**非**卷首标题 | `太史公曰` | 按传记段首逐人划块 |
| 有卷首标题行 | 汉书 | P1 → `卷首标题` | `赞曰`（**非**太史公曰） | 按卷名顺序、传记段首划块；注意同段接力 |
| 志/表/书 | 各史 | 依卷型 skip 或全 exclude | — | — |

**汉书合传要点**（如郦陆朱刘叔孙传）：

- P1：`卷四十三…传第十三` → `卷首标题`
- 五人按卷名顺序；段内可能出现「…陆贾，楚人也」「…硃建，楚人也」接力
- 块边界以**各人传记段首**为准，勿因同段内前文仍属上一人而整段归错
- 末段 `赞曰：…` → exclude

**史记合传要点**（如列传导）：

- P1 即第一人叙事或过渡，**无**卷首标题 exclude
- 末段 `太史公曰` → exclude

### blocks 草稿格式

**`exclude_reason` 只能填下列字面量之一：**

`太史公曰` · `世系链` · `过渡叙事` · `纯纪年` · `志书数据` · `艺文目录` · `卷首标题` · `篇内小标题` · `无故事弧` · `其他`

```json
{
  "total_paragraphs": <与段落索引 total 一致>,
  "excludes": [
    {"paragraph_from": 1, "paragraph_to": 1, "exclude_reason": "卷首标题"},
    {"paragraph_from": 17, "paragraph_to": 17, "exclude_reason": "赞曰"}
  ],
  "blocks": [
    {"name": "主人公标准名", "category": "文臣", "paragraph_from": 2, "paragraph_to": 4}
  ]
}
```

- `category`：君王 / 宗戚 / 宦官 / 文臣 / 武将 / 蕃祚 / 庶众
- 块 `name` 必须与 Step1a `protagonists` **完全一致**
- 每段须被 **恰好一个 block** 或 **exclude** 覆盖

### 返工反例

| 场景 | 错误 | 正确 |
|------|------|------|
| 汉书列传 P1 | `篇内小标题` 或归第一人 | `卷首标题` exclude |
| 汉书末段 | `太史公曰` | `赞曰` |
| 史记 P1 本纪 | `卷首标题` | 归入君王 block |
| 汉书合传 P8 | 整段归陆贾 | 硃建起笔段起归朱建 |
| 秦本纪末段总述 | 秦始皇 block | exclude「其他」 |
| 礼书 / 乐书 | 汉高祖 block | 志书 skip |

### Done

1. JSON 落盘至 `blocks 产出路径`
2. 回复：`STEP1_BLOCKS_DONE` + 块数 + exclude 数
