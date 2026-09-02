#!/usr/bin/env bash
# 三国 compose 续跑：补 16 条失败详情 → gate → 线上同步
set -euo pipefail

export HISTOGRAPH_ROOT="/Users/rachelcheng/Desktop/padanhis/pandahis/pandahis"
SCRIPT="$HISTOGRAPH_ROOT/tools/openclaw-historiography/historiography-dynasty-knowledge/scripts/dynasty_supplement.py"
LOG_DIR="$HISTOGRAPH_ROOT/data/05工作流中间产物/朝代知识补全"
DYN="三国"
OUT="$LOG_DIR/三国_phase3_resume.out"

exec > >(tee -a "$OUT") 2>&1

echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) RESUME START ====="

python3 - <<'PY'
import json
from pathlib import Path

root = Path("/Users/rachelcheng/Desktop/padanhis/pandahis/pandahis")
details = root / "data/06朝代知识补全/详情"
fail_path = root / "data/05工作流中间产物/朝代知识补全/logs/compose_pending_failures.json"
failures = json.loads(fail_path.read_text(encoding="utf-8"))["failures"]
missing = []
for row in failures:
    eid = row["史略ID"]
    if not list(details.glob(f"{eid}_*.json")):
        missing.append(f"{eid} {row['史略名称']}")
print(f"待补详情: {len(missing)} 条")
for line in missing:
    print(f"  · {line}")
PY

echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) START compose-pending (resume) ====="
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

echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) RESUME COMPLETE ====="
