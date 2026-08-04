# Step1b · 整卷划块专则

与 `人物标注规则-v2.md` 配套。LLM 执行 Step1b-A 时 **必读本文 + 段落索引全文**。

---

## 1. 输入 / 输出

### 输入

- `protagonists.json`（Step1a，已 identity_gate）
- 段落索引 `paragraphs[].text`，P1..PN **全部读完**
- `volume_subtype`（见规则表）

### 输出

- `blocks.json` → `data/05工作流中间产物/标注-v2/{著作}_{卷号}_blocks.json`
- **禁止**输出 skeleton / segment_attribution / entries

---

## 2. benji_multi / shijia_zhuhou：逐段主语 → 聚合（必读）

**适用**：`benji_multi`、`shijia_zhuhou`（多君主 + 中间继嗣链）。

**禁止**先定 Top5 再对 exclude 洞之间「整块贴标签」；**必须**先逐段判叙事主语，再聚合 blocks。

### Step1b-α · 逐段叙事主语

对 **P1..PN 每一段**，只答一个问题：

> **本段主要在记述谁？**（非「谁被提到」「谁出现在更替句末」）

| 信号 | 判读 |
|------|------|
| 段内行动/年号主语明确 | 归该人 |
| **前君崩逝/禅让/逊位/末次授政**（含葬、巡狩、授政，末句立下一人） | 主功能收束 → **outgoing**；若同段直连两 Top「卒+立」→ **双挂**（`primary_subject=后君`，`co_owner=前君`） |
| 下一人**正式开传**后的叙事 | **归 incoming 主人公**（新 block 从开传句起；交接双挂段可同时算双方边界） |
| 「X 卒，中间君立」而下一主轴隔代 | **禁止**双挂 X+隔代主轴；中间君无条 → 世系链 / 单挂 |
| 仅在子嗣名单、**且无**前君崩禅授政实质 | **世系链**（多为非 Top5 小君） |
| 远祖谱、`A 立…卒，生 B` 纯继嗣 | **世系链** |
| 非 Top5 小君整段 | **世系链** |
| 段落在 **Top5 君主纪年内**编年（含他国大事） | 归该 Top5 君主（纪年锚点） |
| 段落在 **非 Top5 君主纪年内** | **世系链** |
| 并列点名多位 Top5、无单一主角 | **共段总述** |

**反例（秦本纪 · 纯继嗣钩）**：
- P29 成公立四年卒，末句「立其弟缪公」→ **世系链**（成公非 Top5，且无穆公开传叙事）

**范例（崩逝收束 · 归前君）**：
- 尧 P27 末句「是为帝舜」→ **仍归尧**；舜 block 自 P28「虞舜者」起
- 禹 P38 会稽崩、天下授益 → **归禹**；启 block 自 P39 起
- 成汤 P11 汤崩、立太甲路径 → **归成汤**；太甲 block 自 P12 起
- 孝公 P91–P93 孝公卒、诛鞅 → **归孝公**

### Step1b-β · 聚合 blocks

1. 连续段主语相同且 ∈ Step1a → 合并为一个 block  
2. 主语为世系/小君/远祖 → `exclude（世系链）`  
3. 论赞 / 太史公曰 → 按 §2 原三问处理  
4. 填写 boundary_evidence（open 须为**该 block 第一段**叙事开句，非 mention）

---

## 3. 三问决策（每个 block 边界）

对每一位传主 block 的 **起止段**，按顺序回答：

### Q1 · 结构位

这段在整卷叙事里是什么？

- 若是 **论赞 / 太史公曰** → 先判 **夹叙单段** vs **卷末论赞块**（见下），再 exclude；**禁止**见论赞就盲延到卷末
- 若是 **正式开传** → 新 block 从该段起
- 若是 **前代收束**（含摄政）→ 仍属 **前 block**
- 若是 **合传过渡** → 归 **下一传主** block（列传）
- 若是 **无关世系/享国表** → **exclude（世系链）**（须与主轴无直接身世关系）

### Q2 · 更替边界

同段若有崩+立：

- 主功能是 **结束 A** → 整段归 A 的 block
- 主功能是 **开始 B**（已出现 B 的正式开传式）→ 整段归 B 的 block

**看前后 2–3 段**，不单看本段末句。

### Q3 · 一致性

- block 主人 ∈ Step1a
- 同传主 block 尽量合并为连续区间
- 块内子嗣/制度/赋颂 **不 exclude**

---

## 4. 卷型参数

| volume_subtype | 开传信号 | 更替默认 | 边界精读窗口 |
|----------------|----------|----------|--------------|
| benji_multi | `帝X者` / `X者，名曰` | 崩立归前帝至下一人开传 | ±2 段 |
| liezhuan_hezhuan | `X者…` / `X名Y` / 里居 | 过渡归后传主 | ±3 段 |
| benji_single | （不适用） | 单 block | ±1 段 |
| shijia_zhuhou | 嗣君开传 / 「X立」 | 崩立归前君 | ±2 段 |

---

## 5. blocks.json  schema

```json
{
  "work": "01史记",
  "vol": "001",
  "total_paragraphs": 42,
  "volume_subtype": "benji_multi",
  "excludes": [
    {"paragraph_from": 40, "paragraph_to": 40, "exclude_reason": "共段总述"}
  ],
  "blocks": [
    {
      "name": "黄帝",
      "category": "君王",
      "paragraph_from": 1,
      "paragraph_to": 8,
      "boundary_evidence": {
        "open_paragraph": 1,
        "open_phrase": "黄帝者，少典之子",
        "close_paragraph": 8,
        "close_note": "P8 末轩辕崩前叙事收束"
      }
    }
  ],
  "multi_owner_segments": []
}
```

### 世系链 exclude（必读）

**exclude** 当且仅当：段落在罗列**他君**享国/继嗣，且**不是**本传主的开篇身世、父母、直系子嗣收束。

| 归主人 | exclude 世系链 |
|--------|----------------|
| P1 庄襄王生始皇 | P93 襄公立享国十二年…（全表） |
| 舜 P28 七世父系 | 本纪末附「右秦襄公至二世六百年」 |
| 传内「生二子，后有天下」 | 纯 A生B生C 无行动且非直系 |

### 共段总述 exclude（hezhuan 必读）

**何时用**：段内**并列**出现 Step1a 中**多位**主轴（如依次点名五帝国号），**无单一叙事主角**，无法回答「最应归谁」。

**何时不用**：
- 段内虽有他人名，但叙事主轴明确 → 归 block 主人
- 子嗣、制度、赋颂嵌入 → 归当前 block 主人
- **同段双「X者」开传**（前半 A者…、末句 B者…）→ **归段首开传者**，**不要**共段总述（见下「混写合传」）

**禁止**使用 `multi_owner_segments` 挂多个 owner；v2 gate 会硬失败。

### 混写合传（liezhuan_hezhuan · interleaved）

适用于《廉颇蔺相如列传》一类：**卷名人物来回穿插**，中间再以「X者」开小传，**不是**先写完 A 再写 B。

| 规则 | 说明 |
|------|------|
| 主轴 | 卷名人物 + 正式「X者」开传者；**勿**把配角戏（如赵括）单独立 Top |
| 双开传同段 | 同段两个「X者」→ **归段首开传者**（081 P1→廉颇；末句「蔺相如者」=下传挂钩） |
| 双人同场 | 选**叙事主推进者**一人；将相和归蔺相如（081 P9–10） |
| 配角戏 | 挂被对照/被替换的主轴（长平赵括戏 → 挂廉颇，081 P16–23） |
| 同人非连续 | **允许**；β 多段 runs 合并到同一 entry，勿为求连续乱切 |

范例切法（081）：P1 廉 · P2–10 蔺（含将相和）· P11 廉 · P12–15 赵奢 · P16–23 廉 · P24–29 廉 · P30–35 李牧 · P8/P22 共段总述 · P36 太史公曰。

### boundary_evidence（hezhuan 每 block 必填）

| 字段 | 要求 |
|------|------|
| `open_paragraph` | 开段段号 |
| `open_phrase` | **≥6 字**原文子串，须出现在 `open_paragraph` |
| `close_paragraph` | 可选；末段段号 |
| `close_note` | 一句说明为何在此收束（供人工/gate 审） |

### multi_owner_segments

**v2 已废止。** 平行多主轴段落一律 `exclude_reason: 共段总述`。

### 论赞 / 太史公曰（必读 · gate `LUNZAN_*`）

1. **夹叙**：叙事未收束，插入议论后 **下一段回归编年** → 通常 **仅 exclude 该段** `太史公曰`
2. **卷末论赞块**：block 叙事 **已收束**；P(n) 起 `太史公曰`；续段为史论/引文；**之后无同一传主 block 回归**
3. **误延展信号**（gate 报错）：
   - 同一 owner 的 block 被 **多段** 论赞 exclude 打断
   - 论赞区间内段首似 **明年/其年/春…/秦王…攻立** 等编年续写
   - 论赞块结束后 **又划回** 同一传主 block

**006 范例**：P76 收束 → P77 太史公曰 → P78–92 论赞 → P93 世系链（非叙事回归）。

---

## 6. v2_blocks_gate 检查项

| 代码 | 检查 |
|------|------|
| `COVERAGE` | P1..PN 每段有 block 或 exclude |
| `EXCLUDE_V2` | exclude_reason 仅 6 类白名单（含共段总述、世系链） |
| `EXCLUDE_LEGACY` | 出现世系链/过渡叙事等 → 失败 |
| `SANDWICH` | 夹心 exclude |
| `BOUNDARY_PHRASE` | open_phrase 非原文子串 |
| `PROTAGONIST` | block.name ∈ Step1a |
| `OVERLAP` | block 与 exclude 不重叠、block 互不重叠 |
| `MULTI_OWNER_FORBIDDEN` | 出现 multi_owner_segments |
| `LUNZAN_OVERREACH` | 论赞/太史公曰 盲延、夹叙多段、区间内似编年续写 |
| `LUNZAN_RESUME_BLOCK` | 论赞块后回归同一传主 block |
| `LUNZAN_BOUNDARY` | 论赞续段前无 block 收束或太史公曰（警告） |

---

## 7. 边界专审（Step1b-D）

gate 失败且含 `BOUNDARY_*` / `SANDWICH` 时：

1. 只读失败段 ±3 段原文
2. 修正有关 block 的 from/to 或删除非法 exclude
3. 更新 boundary_evidence
4. 重跑 gate + expand

**不要**改为逐段 LLM 填 1..N 表。

---

## 8. v1 反模式（禁止复现）

| v1 错误 | 本版处理 |
|---------|----------|
| P15 怀沙赋 → 过渡叙事 exclude | 归屈原 block |
| P16 起误归贾谊 | 边界在 P22/23，专审 |
| P40 五帝总述 exclude | **共段总述** exclude（非 multi_owner） |
| 块内世系 exclude 挖洞 | 夹心 gate 拦截 |
| Step3 自证通过 | gate + check_format 硬门 |

---

## 9. 命令速查

```bash
export HIST_ANNOTATE_TRACK=v2

# 硬门
python3 historiography-annotate-v2/scripts/v2_blocks_gate.py --work 01史记 --vol 001

# 展开
python3 historiography-annotate-v2/scripts/v2_expand_to_skeleton.py --work 01史记 --vol 001

# single 机械
python3 historiography-annotate-v2/scripts/v2_expand_to_skeleton.py --work 01史记 --vol 007 --mechanical
```
