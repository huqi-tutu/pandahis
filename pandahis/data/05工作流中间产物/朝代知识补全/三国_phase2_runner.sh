#!/usr/bin/env bash
# 三国朝代知识补全 · 索引阶段（fill + enrich + 线上索引同步，不含详情 compose）
set -euo pipefail

export HISTOGRAPH_ROOT="/Users/rachelcheng/Desktop/padanhis/pandahis/pandahis"
SCRIPT="$HISTOGRAPH_ROOT/tools/openclaw-historiography/historiography-dynasty-knowledge/scripts/dynasty_supplement.py"
LOG_DIR="$HISTOGRAPH_ROOT/data/05工作流中间产物/朝代知识补全"
DYN="三国"
OUT="$LOG_DIR/三国_phase2_runner.out"

exec > >(tee -a "$OUT") 2>&1

echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) INDEX-ONLY PHASE START ====="
echo "范围：fill 索引 + enrich 元数据 + 线上 historical_box（不含详情/翻译/见证/关系/评述）"

# 1) 人审批准（终稿 81 条，phase=candidates）
python3 - <<'PY'
import json
from datetime import datetime, timezone
from pathlib import Path

root = Path("/Users/rachelcheng/Desktop/padanhis/pandahis/pandahis")
cand_path = root / "data/05工作流中间产物/朝代知识补全/三国_候选清单.json"
approval_path = root / "data/05工作流中间产物/朝代知识补全/三国_人审批准.json"
doc = json.loads(cand_path.read_text(encoding="utf-8"))
items: dict[str, list[str]] = {}
for cat, rows in (doc.get("candidates") or {}).items():
    names = [
        str(r.get("名称", "")).strip()
        for r in rows
        if isinstance(r, dict) and str(r.get("名称", "")).strip()
    ]
    if names:
        items[cat] = names
approval = {
    "schema_version": 1,
    "朝代ID": "CD_HX_SANGUO",
    "朝代名称": "三国",
    "phase": "candidates",
    "approved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "approved_by": "user",
    "note": "终稿81条 fill 索引（用户确认启动补全）",
    "items": items,
}
approval_path.write_text(json.dumps(approval, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"✅ 人审批准 candidates: {sum(len(v) for v in items.values())} 条")
PY

# 2) fill 索引
for step in fill-shilue fill-dianzhi fill-lunzhu fill-renwu; do
  echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) START $step ====="
  python3 -u "$SCRIPT" --dynasty "$DYN" --step "$step"
  echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) DONE  $step ====="
done

# 3) enrich 索引元数据
echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) START enrich-all ====="
python3 -u "$SCRIPT" --dynasty "$DYN" --step enrich-all
echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) DONE  enrich-all ====="

# 4) 合并线上索引 + upsert historical_box（跳过详情）
echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) START sync index online ====="
python3 -u "$HISTOGRAPH_ROOT/scripts/sync_online_index_to_db.py" --skip-details
echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) DONE  sync index online ====="

echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) INDEX-ONLY PHASE COMPLETE ====="
