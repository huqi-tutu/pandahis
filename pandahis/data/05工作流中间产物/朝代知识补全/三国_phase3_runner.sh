#!/usr/bin/env bash
# 三国朝代知识补全 · 详情阶段（compose → gate → 线上详情同步）
set -euo pipefail

export HISTOGRAPH_ROOT="/Users/rachelcheng/Desktop/padanhis/pandahis/pandahis"
SCRIPT="$HISTOGRAPH_ROOT/tools/openclaw-historiography/historiography-dynasty-knowledge/scripts/dynasty_supplement.py"
LOG_DIR="$HISTOGRAPH_ROOT/data/05工作流中间产物/朝代知识补全"
DYN="三国"
OUT="$LOG_DIR/三国_phase3_runner.out"

exec > >(tee -a "$OUT") 2>&1

echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) COMPOSE PHASE START ====="
echo "范围：81 条详情 compose-pending（前台逐条，约 2–4 小时）"

python3 - <<'PY'
import json
from pathlib import Path

root = Path("/Users/rachelcheng/Desktop/padanhis/pandahis/pandahis")
approval_path = root / "data/05工作流中间产物/朝代知识补全/三国_人审批准.json"
approval = json.loads(approval_path.read_text(encoding="utf-8"))
if approval.get("phase") != "entries":
    raise SystemExit(f"人审批准 phase 须为 entries，当前={approval.get('phase')}")
print(f"✅ 人审批准 entries: {sum(len(v) for v in approval.get('items', {}).values())} 条")
PY

echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) START compose-pending ====="
python3 -u "$SCRIPT" --dynasty "$DYN" --step compose-pending
echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) DONE  compose-pending ====="

echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) START gate ====="
python3 -u "$SCRIPT" --dynasty "$DYN" --step gate
echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) DONE  gate ====="

echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) START gate-renwu ====="
python3 -u "$SCRIPT" --dynasty "$DYN" --step gate-renwu
echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) DONE  gate-renwu ====="

echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) START sync details online ====="
python3 -u "$HISTOGRAPH_ROOT/scripts/sync_online_index_to_db.py" --skip-build
echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) DONE  sync details online ====="

echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) COMPOSE PHASE COMPLETE ====="
