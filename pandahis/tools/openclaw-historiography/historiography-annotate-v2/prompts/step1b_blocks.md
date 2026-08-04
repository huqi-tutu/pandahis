## Step 1b 任务（v2 · 边界专审 / 遗留参考）

> **hezhuan 默认路径（v2.5）**：**Step1b-α** `prompts/step1b_primary_subjects.md` → **Step1b-β** `scripts/v2_aggregate_blocks.py`。  
> 本文件主要用于 **Step1b-D 边界专审**（gate 报 `BOUNDARY_*` 时只修交界 ±3 段），**不再**作为 hezhuan 整卷 LLM 直写 blocks 的主 prompt。

**前置**：`protagonists.json` 已通过 identity_gate。  
**边界专审时**可只产出/修正 `blocks.json` 中交界 block，禁止输出 skeleton / segment_attribution / entries。

---

### 你必须做的

1. **读完**段落索引 **P1 至 PN 全部正文**（不可跳段、不可只读段首）
2. **`benji_multi` / `shijia_zhuhou`**：先 **Step1b-α** 逐段判叙事主语，再 **Step1b-β** 聚合 blocks（见 `Step1b-整卷划块专则.md` §2）
3. 根据 `volume_subtype` 划 **叙事 blocks** 与 **excludes**
4. 每个 block 填写 **boundary_evidence**（open_phrase 须为原文子串，≥6 字；须出自 block **叙事开段**，非 mention 段）
5. 多主轴**完全并列**、无单一叙事主角 → **exclude=共段总述**（**禁止** multi_owner）
6. **与他君主轴无直接关系的世系/享国表** → **exclude=世系链**
7. 对照 `reference/Step1b-整卷划块专则.md` 的三问决策

### 结构位优先（在判 owner 之前）

1. 论赞 / 太史公曰 → 先判 **夹叙单段** vs **卷末论赞块**，再 exclude（**禁止**见论赞盲延）  
2. 正式开传 → 新 block 起点  
3. 前代收束 / 摄政 → 仍属前 block（**benji_multi**）  
4. 合传过渡 → 后传主 block（**liezhuan_hezhuan**）  
5. 多主轴**并列总述**、无单一主角 → **exclude=共段总述**

**禁止**用 v1 的 `过渡叙事` / `世系链` / `无故事弧` exclude。

---

### exclude_reason 白名单（仅此六种）

`卷首标题` · `太史公曰` · `论赞` · `赞曰` · **`共段总述`** · **`世系链`**

- **共段总述**：并列点名多位 Step1a 主轴，无法归一人（五帝本纪 P40）
- **世系链**：族谱/享国纪年/罗列**他君**，与本卷主人公**无直接身世关系**（秦始皇本纪 P93–135）；本传开篇父母、直系子嗣**仍归主人**

- **史记**本纪/列传：P1 通常是正文，**不是**卷首标题  
- **汉书**列传：P1 往往是 `卷首标题`  
- 赋、颂、制度、子嗣、世系嵌入 → **归 block 主人**，不 exclude  

### 论赞边界（gate 硬查）

- **夹叙**：叙事未收束、下一段回归编年 → 通常 **仅** exclude 该段 `太史公曰`
- **卷末论赞块**：block 已收束 → `太史公曰` + 续段 `论赞` 至评论结束；**之后不得**再划同一传主 block
- **006 范例**：P76 收束 · P77 太史公曰 · P78–92 论赞 · P93 世系链

---

### volume_subtype 参数

| volume_subtype | 开传 | 更替 |
|----------------|------|------|
| benji_multi | `帝X者` / `X者，名曰` | 崩/禅/摄政归前帝，直到下一人正式开传 |
| liezhuan_hezhuan | `X名Y` / 里居 / `X者…` | 过渡句归后传主；勿过早切到下一传主 |

---

### 输出 JSON 格式

```json
{
  "work": "<著作ID>",
  "vol": "<三位卷号>",
  "total_paragraphs": <与索引一致>,
  "volume_subtype": "<benji_multi|liezhuan_hezhuan|...>",
  "excludes": [
    {"paragraph_from": 40, "paragraph_to": 40, "exclude_reason": "共段总述"},
    {"paragraph_from": 41, "paragraph_to": 41, "exclude_reason": "太史公曰"}
  ],
  "blocks": [
    {
      "name": "<须与 protagonists 一致>",
      "category": "<与 protagonists 一致>",
      "paragraph_from": 1,
      "paragraph_to": 8,
      "boundary_evidence": {
        "open_paragraph": 1,
        "open_phrase": "<该段原文子串>",
        "close_paragraph": 8,
        "close_note": "<为何在此收束，一句>"
      }
    }
  ],
  "multi_owner_segments": []
}
```

- 每段必须被 **恰好一个 block 范围覆盖**，或在 **exclude** 内  
- block 之间 **不重叠**；block 与 exclude **不重叠**  
- `name` **不得**超出 Step1a 名单  

---

### 验收锚点（勿错）

**殷本纪 003（Top5 · 崩逝收束）**

- P1–P2 → 世系链  
- 成汤 **P3–P11**（P11 汤崩归成汤）  
- 太甲 **P12–P13**  
- P14–P20 → 世系链；P21 → 论赞  
- 盘庚 **P22–P24**（P24 盘庚崩归盘庚）  
- 武丁 **P25–P27**  
- P28–P32 → 世系链；帝辛 **P33–P40**

**夏本纪 002（Top5 · 崩逝收束）**

- 禹 **P1–P38**（P38 崩于会稽、授益归禹）；启 **P39–P41**（勿从 P38 起）

**秦本纪 005（Top5 · 逐段主语）**

- P1–P7 → 世系链；非子 **P8–P9**  
- P10–P29 → 世系链（含 P26–P29 德公/宣公/成公，**非**穆公）  
- 秦穆公 **P30–P58**（从「缪公任好元年」起）  
- 秦孝公 **P82–P93**（含孝公卒、诛鞅收束）  
- 秦昭襄王 **P100–P113**（P99 立昭襄为世系链）  
- 秦庄襄王 **P115**

**五帝本纪 001**

- 尧 block 含 P14–P27（含摄政 P22–26、崩 P27）  
- 舜 block 从 P28「虞舜者」起  
- P27 归尧（非舜）  
- P28 起归舜  
- **P40 → exclude（共段总述）**，禁止 multi_owner / 五人 owners  

**屈原贾生 084**

- 屈原 block 含 P1–P21（**含 P15 怀沙赋**）  
- 贾谊从 P22 过渡或 P23「贾生名谊」起  
- **禁止** P15 exclude  

---

### 落盘

`data/05工作流中间产物/标注-v2/{work}_{vol}_blocks.json`

### 完成回复

`STEP1B_BLOCKS_DONE` + 块数 + exclude 数 + volume_subtype

---

### 禁止

- ❌ 直接写 segment_attribution 或 entries  
- ❌ 使用白名单外 exclude_reason  
- ❌ 未读全文就划块  
- ❌ 新建 protagonists 名单外人物  
