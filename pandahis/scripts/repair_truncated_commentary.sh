#!/usr/bin/env bash
# 重生成句末截断的评述条目（#27 等）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CW="$ROOT/tools/openclaw-historiography/historiography-commentary-witness/scripts/cw.py"
IDS=(
  GLBL_00781
  GLBL_00011
  GLBL_00017
  GLBL_00063
  GLBL_00098
  GLBL_00110
  GLBL_00655
  GLBL_00699
  GLBL_00726
  GLBL_00751
  GLBL_00760
  GLBL_00786
)
for id in "${IDS[@]}"; do
  echo "=== commentary-one $id ==="
  python3 "$CW" commentary-one --id "$id" || echo "FAILED $id" >&2
done
echo "done"
