# 《汉书》多层质检报告

- 生成时间：2026-07-05T03:24:30Z
- skeleton：92 卷 / 322 条

## 检查层说明

| 层级 | 工具 | 能发现什么 |
|------|------|------------|
| L0 | JSON | 文件损坏 |
| L1 | check_format | 硬门：字段、坐标、身份门、provenance |
| L2-coord | audit_hanshu_volumes | 坐标链、缺字段、年代倒置 |
| L2-precheck | audit_precheck | 段落归属孤儿、密度、三明治 exclude |
| L3-semantic | 启发式 | 简介占位、原文字句漂移、宗戚册封、segment 不一致 |
| L4-cross | 跨书 | 与史记同名人物分类差异 |

## 汇总

| 状态 | 卷数 |
|------|------|
| ✅ 通过 | 90 |
| ❌ 有问题 | 2 |
| ⏭ 表志 scope 外 | 27 |

| 层级 | ERROR | WARN |
|------|------:|------:|
| L2-precheck | 7 | 0 |
| L3-semantic | 0 | 311 |

- 简介占位条目：303 条（非硬门，影响展示质量）
- 跨书分类 WARN：0 条

## ❌ 失败卷明细

### 卷 051 — 02汉书_051_樊郦滕灌傅靳周传第十一_skeleton.json
- `L2-precheck` 段12: 合传共段多归属须正文涉及 [灌婴]，当前段未见其描写
- `L2-precheck` 段13: 合传共段多归属须正文涉及 [傅宽]，当前段未见其描写
- `L2-precheck` 段14: 合传共段多归属须正文涉及 [靳歙]，当前段未见其描写

### 卷 057 — 02汉书_057_文三王传第十七_skeleton.json
- `L2-precheck` 段2: 合传共段多归属须正文涉及 [刘揖]，当前段未见其描写
- `L2-precheck` 段4: 合传共段多归属须正文涉及 [梁孝王]，当前段未见其描写
- `L2-precheck` 段4: 合传共段多归属须正文涉及 [刘参]，当前段未见其描写
- `L2-precheck` 段5: 合传共段多归属须正文涉及 [刘揖]，当前段未见其描写

## 建议的进一步人工抽检

1. **合传块边界**：`python3 audit_hezhuan_alignment.py --work 02汉书`（WARN 多属合传总述，你已确认可接受）
2. **随机 10 卷深读**：对照段落索引 + 原文 txt，核对传主段界与分类理由
3. **跨书主补**：读 `data/03索引标注条目/合并预判/01至02跨著作主补预判表.md`
4. **简介批量补全**：303 条「简介=名称」需 Step4 LLM 写 20 字内简介

## 重跑命令

```bash
cd pandahis/pandahis/tools/openclaw-historiography/historiography-annotate
python3 batch_qc_hanshu.py
HIST_REPAIR=1 python3 check_format.py <skeleton.json> --phase final  # 单卷
```
