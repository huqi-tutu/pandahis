#!/usr/bin/env bash
# 东汉朝代知识补全 · 仅史略索引基本信息（本阶段不做详情/翻译/见证/关系/评述）
set -euo pipefail

export HISTOGRAPH_ROOT="/Users/rachelcheng/Desktop/padanhis/pandahis/pandahis"
SCRIPT="$HISTOGRAPH_ROOT/tools/openclaw-historiography/historiography-dynasty-knowledge/scripts/dynasty_supplement.py"
LOG_DIR="$HISTOGRAPH_ROOT/data/05工作流中间产物/朝代知识补全"
DYN="东汉"
OUT="$LOG_DIR/东汉_phase2_runner.out"

exec > >(tee -a "$OUT") 2>&1

echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) INDEX-ONLY PHASE START ====="
echo "范围：fill 索引 + enrich 元数据 + 线上 historical_box（不含详情/翻译/见证/关系/评述）"

# 1) 校验人审批准（不自动覆盖；剔除与三国一期重复的 6 条人物）
python3 - <<'PY'
import json
from pathlib import Path

root = Path("/Users/rachelcheng/Desktop/padanhis/pandahis/pandahis")
approval_path = root / "data/05工作流中间产物/朝代知识补全/东汉_人审批准.json"
EXCLUDE_SANGUO_DUP = {"曹操", "孙坚", "孙策", "张鲁", "王粲", "荀攸"}
approval = json.loads(approval_path.read_text(encoding="utf-8"))
items = approval.get("items") or {}
changed = False
for cat, names in list(items.items()):
    if not isinstance(names, list):
        continue
    filtered = [n for n in names if str(n).strip() not in EXCLUDE_SANGUO_DUP]
    if filtered != names:
        items[cat] = filtered
        changed = True
if changed:
    approval["items"] = items
    approval_path.write_text(json.dumps(approval, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("✅ 已从人审批准剔除三国重复人物")
total = sum(len(v) for v in items.values())
print(f"✅ 人审批准 candidates: {total} 条（已排除三国重复 6 条）")
PY

# 2) fill 索引（已完成的名称会自动跳过）
for step in fill-shilue fill-dianzhi fill-lunzhu fill-renwu; do
  echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) START $step ====="
  python3 -u "$SCRIPT" --dynasty "$DYN" --step "$step"
  echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) DONE  $step ====="
done

# 3) enrich 索引元数据（峰值年/优先级/人物标签；非详情正文）
echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) START enrich-all ====="
python3 -u "$SCRIPT" --dynasty "$DYN" --step enrich-all
echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) DONE  enrich-all ====="

# 4) 合并进线上索引 JSON + upsert historical_box（跳过详情）
echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) START sync index online ====="
python3 -u "$HISTOGRAPH_ROOT/scripts/sync_online_index_to_db.py" --skip-details
echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) DONE  sync index online ====="

echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) INDEX-ONLY PHASE COMPLETE ====="
