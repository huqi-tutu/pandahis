## Step 1b-α · 逐段叙事主语（v2）

**前置**：`protagonists.json` 已通过 Step1a。  
**本步只产出 `primary_subjects.json`**，禁止输出 blocks / skeleton。

---

### 你要做的事

对 **P1..PN 每一段**，只回答一个问题：

> **本段主要在记述谁？**（不是「谁被提到」「谁出现在句末」）

每段一行 JSON，**必须覆盖 1..N 全部段落，不可漏段**。

---

### primary_subject 怎么填

| 情况 | primary_subject | disposition | exclude_reason |
|------|-----------------|-------------|----------------|
| 本段主要写 Step1a 某主轴 | 与 protagonists.name **完全一致** | `block` | （不写） |
| 享国链 / 非 Top 小君 / 远祖谱 | `世系链` | `exclude` | `世系链` |
| 太史公曰起笔 | `太史公曰` | `exclude` | `太史公曰` |
| 论赞续段（非太史公曰起笔） | `论赞` | `exclude` | `论赞` |
| 并列多位主轴、无单一主角 | `共段总述` | `exclude` | `共段总述` |
| 汉书卷首篇名行 | `卷首标题` | `exclude` | `卷首标题` |

**硬规则**：

1. **崩逝/禅让/末句「立 X」** 若段内主功能是结束前一主轴 → 仍归 **outgoing 主轴**（`block`），不归世系链  
2. **正式开传**（「是为 XX」「王 XX 元年」「帝 X 者」等）→ 归 **incoming 主轴**（`block`）  
3. **两主轴直连交接（双挂）**：同段正文同时含 **前主轴卒/崩** 与 **后主轴立/是为**，且二人都在 Step1a →  
   - `primary_subject` = **后君**（incoming）  
   - `co_owner` = **前君**（outgoing）  
   - `disposition` = `block`  
   - 例：「威王卒，子宣王辟彊立」→ `primary_subject=齐宣王`，`co_owner=齐威王`  
   - **禁止**把中间君即位双挂到隔代主轴（襄公卒→成公立，不可 `co_owner=宋襄公` 且挂宋文公）  
4. 非 Top5 小君整段叙事（如季札聘国、中间国君）→ **`世系链` exclude**，不要贴给最近 Top5  
5. 史记本纪/列传 **P1 通常是 block**；但本纪远祖开篇（如「周后稷」）可为 **世系链**，勿强行挂最近 Top  
6. **混写合传**（`volume_texture=interleaved` / 廉蔺类）：  
   - 同段双「X者」→ **归段首开传者**（勿共段总述、勿双归属）  
   - 双人同场 → 归**叙事主推进者**（将相和→蔺相如）  
   - 配角戏挂主轴（赵括长平→廉颇），**勿**给配角单独 primary_subject 除非其在 Step1a Top  
7. **禁止段号硬切 / 时代伞**：不得用「pid≤N→某人」「厉宣并幽王」「东周并赧王」；只问本段记述谁、与 Top 有无**直接**关系  
8. **非 Top 的小君/远祖叙事 → 世系链合法**；内容门红了应核「是不是真链」，禁止为过门改塞 Top5  

详见 `reference/Step1b-整卷划块专则.md` §2 / 「混写合传」。

---

### 输出 JSON 格式

```json
{
  "work": "01史记",
  "vol": "032",
  "total_paragraphs": 97,
  "method": "Step1b-α LLM",
  "paragraphs": [
    {
      "paragraph": 1,
      "primary_subject": "齐太公",
      "disposition": "block"
    },
    {
      "paragraph": 47,
      "primary_subject": "齐宣王",
      "co_owner": "齐威王",
      "disposition": "block"
    },
    {
      "paragraph": 12,
      "primary_subject": "世系链",
      "disposition": "exclude",
      "exclude_reason": "世系链"
    },
    {
      "paragraph": 97,
      "primary_subject": "太史公曰",
      "disposition": "exclude",
      "exclude_reason": "太史公曰"
    }
  ]
}
```

可选 `text_snippet`（段首约 40 字）便于人工抽检。

---

### Done

1. JSON 落盘至 `primary_subjects 产出路径`  
2. 回复：`STEP1B_ALPHA_DONE` + 段数 + block/exclude 段数摘要  
