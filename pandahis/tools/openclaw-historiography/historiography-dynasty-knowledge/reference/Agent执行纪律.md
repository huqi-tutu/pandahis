# 朝代知识补全 · Agent 执行纪律

> **Cursor / Claude agent 专用**。脚本 SSOT 见 `执行纪律.md`；本文规定 agent **何时停、何时后台跑**。

---

## 一、两道人工闸门（强制）

| 闸门 | 时机 | agent 必须 |
|------|------|------------|
| **候选确认** | `candidates-*` / `candidates-renwu` 完成后 | 运行 `export-review`，把确认表交给用户，**停止** |
| **详情确认** | `fill-*` 产出索引后、写详情前 | 运行 `export-review --review-phase entries`，**停止** |

**禁止**在用户未明确批准前：

- 执行任何 `fill-*` / `fill-renwu`
- 执行 `compose-detail` / `compose-pending`
- 使用 `--compose-after-fill`（默认已关闭）

已产出的历史数据（如五帝人物）不回滚；**新批次必须遵守**。

---

## 二、推荐交互流程

```text
1. candidates-renwu          （可前台，较快）
2. export-review             → 展示 人审确认表.md，等待用户
3. 用户确认 → 写入 人审批准.json（phase=candidates）
4. fill-renwu --background   → 只产出索引，不写详情
5. export-review --review-phase entries → 再次等待用户
6. 用户确认 → 更新 人审批准.json（phase=entries）
7. compose-pending --background
8. gate / enrich             （可后台）
```

---

## 三、后台执行（禁止占用对话窗口）

耗时步骤**必须**加 `--background` 或调用 `run_supplement_bg.sh`：

| 步骤 | 典型耗时 | 执行方式 |
|------|----------|----------|
| `fill-*` / `fill-renwu` | 数分钟～数十分钟 | `--background` |
| `compose-pending` | 每条 1～3 分钟 | `--background` |
| `enrich` / `enrich-renwu` | 数分钟 | `--background` |

```bash
# 方式 A：脚本参数
python3 dynasty_supplement.py --dynasty 五帝 --step fill-renwu --background

# 方式 B：包装脚本
./run_supplement_bg.sh 五帝 compose-pending
```

后台启动后 agent **立即返回**，告知用户：

- PID / 日志路径（`data/05工作流中间产物/朝代知识补全/logs/`）
- 可用 `tail -f <log>` 查看进度
- **不要**在对话中 `block_until` 等待整批完成

---

## 四、批准文件格式

路径：`data/05工作流中间产物/朝代知识补全/{朝代}_人审批准.json`

```json
{
  "schema_version": 1,
  "朝代ID": "CD_HX_WUDI",
  "朝代名称": "五帝",
  "phase": "candidates",
  "approved_at": "2026-07-12T10:00:00Z",
  "approved_by": "user",
  "items": {
    "宗戚": ["嫘祖", "丹朱"],
    "文臣": ["皋陶", "伯益"]
  }
}
```

- `phase=candidates` → 控制 `fill-*` 范围
- `phase=entries` → 控制 `compose-pending` 范围（`items` 键为史略分类，值为 `史略名称`）

模板由 `export-review` 自动生成：`{朝代}_人审批准.template.json`

---

## 五、违规示例（本次五帝人物补全）

| 违规 | 正确做法 |
|------|----------|
| candidates-renwu 后直接 fill-renwu + compose | 先 export-review，等用户批 |
| fill 默认连带 compose-detail | 默认分离；详情须二次确认 |
| 前台阻塞跑 12 条详情 ~25 分钟 | `compose-pending --background` |
| 增量补漏只跑 fill + compose，跳过 enrich | **必须**在 compose 后跑 `enrich-all`（见 §六） |

---

## 六、增量补漏（用户点名清单）

用户指定「某朝再补哪些史略」时，**字段须与首跑批次同等完整**，不得只产出索引/详情。

```text
seed_incremental_candidates.py（或手改候选 + 人审批准 phase=candidates）
  → fill-* / fill-renwu（跳过已有名称，只写新 GLBL）
  → 人审批准 phase=entries
  → compose-pending / compose-detail
  → enrich-all          ← 强制：优先级 + 峰值年 + 人物标签
  → gate（可选）
  → append + 线上 upsert
```

| 步骤 | 产出字段 | 人物七类 | 事略/典制/论著 |
|------|----------|----------|----------------|
| `fill-*` | 索引骨架 | 不含标签/优先级 | 不含优先级 |
| `compose-detail` | `翻译详情` | ✓ | ✓ |
| `enrich` | `优先级`、`峰值年` | ✓ | ✓ |
| `enrich-renwu` / `enrich-all` 后半 | `人物标签` 等 | **✓ 必填** | — |

**说明**：`fill` 阶段 prompt 刻意不写人物标签（SSOT：`person_tag.py` 专责）。漏跑 `enrich-renwu` 即表现为**人物条无标签**。

```bash
python3 dynasty_supplement.py --dynasty 五帝 --step enrich-all
```
