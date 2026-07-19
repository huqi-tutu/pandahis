#!/usr/bin/env bash
set -uo pipefail

SCRIPT="/Users/rachelcheng/Desktop/padanhis/pandahis/pandahis/tools/openclaw-historiography/historiography-dynasty-knowledge/scripts/dynasty_supplement.py"
LOG="/Users/rachelcheng/Desktop/padanhis/pandahis/pandahis/data/05工作流中间产物/朝代知识补全/logs/batch_pilot5_full_v3.log"
IDS=(GLBL_00561 GLBL_00562 GLBL_00567 GLBL_00574 GLBL_00575)

exec >>"$LOG" 2>&1
echo "======== BATCH START $(date '+%F %T') ========"

run_step() {
  local step=$1 id=$2
  shift 2
  echo ""
  echo "-------- $id $step $(date '+%F %T') --------"
  if ! python3 "$SCRIPT" --dynasty 五帝 --step "$step" --entry-id "$id" "$@"; then
    echo "WARN $id $step exit $?"
  fi
}

for id in "${IDS[@]}"; do
  run_step anchor-research "$id"
done

for id in "${IDS[@]}"; do
  run_step bibliography-plan "$id" --force-bibliography
  run_step fetch-snippets "$id"
  run_step verify-bibliography "$id"
done

for id in "${IDS[@]}"; do
  run_step compose-detail "$id" --force-bibliography
  run_step verify-detail "$id"
  run_step review-detail "$id"
done

echo ""
echo "======== ALL DONE $(date '+%F %T') ========"
