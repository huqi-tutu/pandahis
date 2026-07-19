#!/usr/bin/env bash
# 五条试点完整流程 v4（coverage_claims + Kimi 不阻断）
set -euo pipefail
cd "$(dirname "$0")"
DYNASTY="五帝"
LOG="../../../../data/05工作流中间产物/朝代知识补全/logs/batch_pilot5_full_v4.log"
mkdir -p "$(dirname "$LOG")"
exec > >(tee -a "$LOG") 2>&1

IDS=(GLBL_00561 GLBL_00562 GLBL_00567 GLBL_00574 GLBL_00575)
QA_DIR="../../../../data/05工作流中间产物/朝代知识补全/logs/qa_state"

echo "========== batch pilot5 full v4 $(date -u +%Y-%m-%dT%H:%M:%SZ) =========="

for id in "${IDS[@]}"; do
  qa="$QA_DIR/${id}.json"
  if [[ -f "$qa" ]]; then
    python3 - <<PY
import json
from pathlib import Path
p = Path("$qa")
s = json.loads(p.read_text(encoding="utf-8"))
s["compose_attempts"] = 0
s["patch_attempts"] = 0
s["status"] = "pending"
p.write_text(json.dumps(s, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"  reset qa_state {p.name}")
PY
  else
    echo "{\"史略ID\":\"$id\",\"compose_attempts\":0,\"patch_attempts\":0,\"status\":\"pending\"}" > "$qa"
    echo "  created qa_state $id"
  fi
done

run_step() {
  local step="$1" id="$2"
  echo ""
  echo ">>> [$id] $step $(date -u +%H:%M:%S)"
  python3 dynasty_supplement.py --dynasty "$DYNASTY" --step "$step" --entry-id "$id"
}

for id in "${IDS[@]}"; do
  echo ""
  echo "============================== $id =============================="
  run_step anchor-research "$id"
  echo ">>> [$id] bibliography-plan --force-bibliography"
  python3 dynasty_supplement.py --dynasty "$DYNASTY" --step bibliography-plan --entry-id "$id" --force-bibliography
  run_step fetch-snippets "$id"
  run_step verify-bibliography "$id" || true
  python3 dynasty_supplement.py --dynasty "$DYNASTY" --step compose-detail --entry-id "$id" --force-bibliography || true
  python3 dynasty_supplement.py --dynasty "$DYNASTY" --step qa-detail --entry-id "$id" || true
done

echo ""
echo ">>> review-warns-summary"
python3 dynasty_supplement.py --dynasty "$DYNASTY" --step review-warns-summary
echo "========== DONE $(date -u +%Y-%m-%dT%H:%M:%SZ) =========="
