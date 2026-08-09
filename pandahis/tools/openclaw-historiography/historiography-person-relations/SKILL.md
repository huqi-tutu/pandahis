---
name: historiography-person-relations
description: >
  人物史略关系数据补全与存量修复（家庭/同僚/敌对/师徒/好友）。按 GLBL 或朝代逐人产出 JSON 至 data/07人物关系/。
  与 historiography-dynasty-knowledge、historiography-translate 独立。激活词：人物关系、关系补全、关系表、07人物关系、关系修复。
origin: ECC
---

# 人物关系补全 / 存量修复工作流

## 与相邻模块的关系

| 模块 | 职责 | 产出 |
|------|------|------|
| **historiography-annotate-v2** | 卷级人物标注 | 10 索引 |
| **historiography-dynasty-knowledge** | 朝代知识 + 人物详情 | 06 详情 |
| **historiography-translate** | 史略译文 | **11 新标注条目翻译**（v2 SSOT；不再用 04） |
| **historiography-person-relations**（本 skill） | **人物关系图谱** | **07 人物关系** → `box_graph_*` |

**禁止**为非人物类史略（事略 / 典制 / 论著 / 蕃祚）建关系表。

## When to Activate

- 用户要求补全**特定人物**或**某朝代人物**的关系数据
- 用户要求**存量关系修复**（数据补全 + 新 schema 呈现）
- 用户提到「人物关系」「关系表」「07人物关系」「关系图谱 JSON」

## 规范 SSOT（必读顺序）

| 顺序 | 文档 | 用途 |
|------|------|------|
| 1 | [`../../../关系数据整理提示词.md`](../../../关系数据整理提示词.md) | **关系 taxonomy 唯一权威**（五类一级、二级枢纽、边标题、停止规则） |
| 2 | [`reference/schema.md`](reference/schema.md) | JSON 字段、二级分类枢纽、`所属*关系` 链式写法 |
| 3 | [`reference/execution-discipline.md`](reference/execution-discipline.md) | ECC 执行纪律（证据约束、逐人、verify 门禁） |
| 4 | [`../../../data/07人物关系/周文王关系表.json`](../../../data/07人物关系/周文王关系表.json) | **新 schema 样例**（二级枢纽 + 边标题规则） |

动笔前 **必须先读 SSOT #1**；禁止只读本 SKILL 摘要。

## 路径（相对 `HISTOGRAPH_ROOT` = `pandahis/pandahis`）

| 用途 | 路径 |
|------|------|
| **正式产出** | `data/07人物关系/` |
| 单人物文件 | `data/07人物关系/{关联史略名称}关系表.json` |
| 人物索引 / GLBL | 线上索引 / `03` 索引（`paths_config.global_index`） |
| **Grounding（唯一事实源）** | `data/11新标注条目翻译/`、`data/06朝代知识补全/详情/`（可选）、索引原文字句 |
| 校验脚本 | `scripts/verify_relations.py` |
| 导入脚本 | `scripts/import_relations_lib.py` |

## 节点资格（强制）

叶子节点（非二级枢纽）**只收具体人物**；不得写国家/政权/民族/职衔空名。细则以 SSOT #1「敌对 · 节点资格」为准。

| 可写 | 不可写 |
|------|--------|
| 具名人物；家族/氏姓（如鲍氏、高氏） | 秦国/齐国等政权；犬戎/淮夷等族；东周君/中山国君等空名；战役名 |

存量清洗优先：

1. **硬规则**只删高置信项（已知国/族表、`××国君`/`××周君`、`…之戎`/`诸部` 等）；**禁止**用「尾字戎/夷/狄/国」泛匹配（会误杀伯夷、简狄、孔安国、芈戎）。
2. **其余可疑标题**（敌对中带氏/族/国/职衔空名等形态）→ 分批问 LLM：**只判断是否为国家/政权/少数民族/职衔空名**；家族氏姓（鲍氏、高氏）判保留。不必塞全套 taxonomy。
3. 脚本：`scripts/audit_non_person_nodes.py`（`--scan` / `--apply-hard` / `--llm-audit` / `--apply-llm`）。

## 存量修复原则（强制）

每条存量修复 = **证据驱动的数据补全** + **新 schema 呈现改造**。

1. **禁止**仅凭模型通识 / 对话记忆增补节点。
2. **必须**先读该人物 grounding（11 译文优先，其次 06 详情若有，再次索引原文字句）。
3. **必须**经 `relations.py compose-one`（DeepSeek v4 Pro）按新 taxonomy 成稿；可对照旧 07 表做 diff，但旧表不是事实源。
4. 有据则补全；无据则不写；旧表无据或超深度（曾孙/徒孙）须删除；**配偶支孙辈（四级）有据则保留/补全**。
5. 同谱系已修复关系表仅可作交叉核验，**不得**单独作为写入依据。
6. 应用互斥：家庭 > 同僚 > 好友；家庭亦排斥师徒；清洗重复挂载。
7. 应用**节点资格**：删国家/政权/民族/职衔空名；家族氏姓可留。

## 执行清单（每人必做）

```
Task Progress:
- [ ] 1. 确认目标为人物类史略（君王/宗戚/文臣/武将/宦官/庶众）
- [ ] 2. 读取 SSOT + schema
- [ ] 3. 读取该人物 11/06/索引 grounding（禁止跳过）
- [ ] 4. relations.py compose-one（DeepSeek v4 Pro 成稿）
- [ ] 5. 对照旧 07 表 diff：保留有据、补漏、删无据/超深度
- [ ] 6. verify_relations.py --strict
- [ ] 7. relations.py import-one（或 compose-one --sync）写入 box_graph_*
- [ ] 8. （批量）更新 {朝代}_关系补全_manifest.json
```

**端到端**：`compose-one --sync` = 成稿 + verify + 入库一步完成。

**禁止**一次 prompt 批量混写多人物；**禁止**跳过 grounding / verify / import；**禁止**只做 schema 重排而不核对证据。

## 单人物补全 / 修复

1. 解析输入：`GLBL_00149` / `黄帝` / 二者之一即可。
2. 确认人物六类之一。
3. 读 grounding（11 → 06 → 索引）。
4. `compose-one` 按新五类 + 二级枢纽产出。
5. verify → import。

## 朝代批量修复

1. `list_dynasty_persons(朝代)` 得清单。
2. **逐人串行**：每人走完整单人流程。
3. 更新 `data/07人物关系/{朝代}_关系补全_manifest.json`。

```bash
python3 relations.py compose --dynasty 五帝 --max 21 --sync \
  --mysql-host … --mysql-user … --mysql-password … --mysql-db histomap
```

## 命令

```bash
export HISTOGRAPH_ROOT=/path/to/pandahis/pandahis
cd tools/openclaw-historiography/historiography-person-relations/scripts

python3 relations.py test-llm
python3 relations.py compose-one --id GLBL_00149 --sync
python3 relations.py import-one --name 黄帝
python3 relations.py compose --dynasty 五帝 --max 21 --sync
python3 relations.py verify --name 黄帝
python3 verify_relations.py --strict "$HISTOGRAPH_ROOT/data/07人物关系/黄帝关系表.json"
```

**LLM 通道（强制）**：`HIST_LLM_PROVIDER=deepseek`、`DEEPSEEK_MODEL=deepseek-v4-flash`；**不会**走 Cursor 对话模型作事实源。

## 输出质量门禁

- `关系类别` ∈ {家庭, 同僚, 敌对, 师徒, 好友}
- 二级分类枢纽：`节点类型=二级分类`，`关系层级=一级`，`上级连接线标题=""`；**好友亦须有二级枢纽「好友」**
- 无人物/子树的二级枢纽不写；家庭边标题用单字白名单（父/母/妻/妾/妃/夫/子/女/兄/弟/姐/妹，或兄弟/姐妹）
- **每个二级枢纽下直接人物 ≤10**（超限只留最重要 10 人）
- 配偶支可至四级（孙辈）；禁止曾孙/徒孙
- 互斥：家庭排斥同僚/好友/师徒；同僚排斥好友
- **叶子节点为人**（或可保留的家族/氏姓）；无国家/政权/民族/「××国君」类空名
- **枢纽名不得落人物层**：`父母/配偶/臣子/外敌/…` 仅允许 `节点类型=二级分类`；`所属二级/三级关系` 必须是人名（或「不详」）
- `verify_relations.py --strict` 退出码 0
- 已 import 到对应 `box_id`

```bash
# 枢纽名伪人物清洗
python3 fix_hub_as_person_nodes.py          # dry-run
python3 fix_hub_as_person_nodes.py --apply
```

```bash
# 存量：非人物节点清洗（硬规则 + LLM 分批）
python3 audit_non_person_nodes.py --scan
python3 audit_non_person_nodes.py --apply-hard
python3 audit_non_person_nodes.py --llm-audit --batch-size 40
python3 audit_non_person_nodes.py --apply-llm
```

## 附加资源

- JSON 字段与边标签映射 → [reference/schema.md](reference/schema.md)
- ECC 执行纪律 → [reference/execution-discipline.md](reference/execution-discipline.md)
