# 锚点研究纪律（anchor-research · LLM prompt SSOT）

> **本文全文**注入 `anchor-research` 的「规范纪律」块，**无截取**。  
> 完整 prompt 见 `logs/prompts/{史略ID}_anchor-research.txt`。

## 史料来源

- `coverage_claims` **仅**来自索引「主要史料出处」及该出处可核查的表述，不得编造
- 不得把维基百科、后世综述**直接**当作主张（维基留 compose 底稿层）

## coverage_claims（核心 · 须传达的主张）

- **5–8 条**，每条一句**自然语言**，描述成稿须让读者知道的信息
- 写**主张**（结果、程序、制度含义），**不写**正文必须出现的原词/关键词
- ✅ 「须说明黄帝在涿鹿之野击败并杀死蚩尤」  
- ❌ 「须出现『禽杀蚩尤』」  
- ❌ 「共主推举制」「任期考察制」等抽象制度造词
- 典制条目：写制度定义、运作程序、合法性；尧舜等**最多 1 条**例证主张
- 事略/人物：写事件结果、人物身份与影响，勿堆砌无关枚举

## legend_facts

- 传说、异说、后世附会单独列出
- 成稿须标注「传说/异说/后世叙述」，不可与主张混写为史实

## forbidden_inventions

- 原文与索引未载、且不应编造的内容：战斗过程、对话、心理、礼制操作步骤、虚构典籍

## 兼容字段（deprecated，新 anchor 勿用）

- `hard_facts` / `core_enumerations` / `checklist` 已由 `coverage_claims` 取代
- 旧 anchor 仍可读；`coverage-check` 会回退解析 checklist / hard_facts

## 与 compose / coverage-check 分工

| 阶段 | 职责 |
|------|------|
| anchor | 列出须传达的主张 + forbidden |
| compose | 白话叙事覆盖主张，勿复述 anchor 原句 |
| coverage-check | 语义判定主张是否 conveyed（非字面匹配） |
| review-detail | 幻觉/禁编/可读性；**不阻断**流水线，汇总至 `review_warns_汇总.md` |

## 史料丰度

- 五帝传说期默认 S0 或 S1；与条目实际史料匹配，不夸大
