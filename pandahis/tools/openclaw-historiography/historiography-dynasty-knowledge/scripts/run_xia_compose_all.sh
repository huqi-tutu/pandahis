#!/usr/bin/env bash
# 夏朝 · 全量 compose-detail + qa-detail（35 条 GLBL_00586–00620）
set -euo pipefail
cd "$(dirname "$0")"
DYNASTY="夏"
LOG="../../../../data/05工作流中间产物/朝代知识补全/logs/batch_xia_compose.log"
QA_DIR="../../../../data/05工作流中间产物/朝代知识补全/logs/qa_state"
mkdir -p "$(dirname "$LOG")" "$QA_DIR"
exec > >(tee -a "$LOG") 2>&1

IDS=(
  GLBL_00586 GLBL_00587 GLBL_00588 GLBL_00589 GLBL_00590 GLBL_00591 GLBL_00592 GLBL_00593
  GLBL_00594 GLBL_00595 GLBL_00596 GLBL_00597 GLBL_00598 GLBL_00599
  GLBL_00600 GLBL_00601
  GLBL_00602 GLBL_00603 GLBL_00604 GLBL_00605 GLBL_00606 GLBL_00607 GLBL_00608 GLBL_00609 GLBL_00610 GLBL_00611 GLBL_00612
  GLBL_00613 GLBL_00614 GLBL_00615
  GLBL_00616 GLBL_00617
  GLBL_00618 GLBL_00619 GLBL_00620
)

echo "========== 夏朝全量详情 $(date -u +%Y-%m-%dT%H:%M:%SZ) =========="
echo "条目数: ${#IDS[@]}"

reset_qa() {
  local id="$1"
  local qa="$QA_DIR/${id}.json"
  python3 - <<PY
import json
from pathlib import Path
p = Path("$qa")
s = {"史略ID": "$id", "compose_attempts": 0, "patch_attempts": 0, "status": "pending"}
if p.exists():
    s = json.loads(p.read_text(encoding="utf-8"))
    s["compose_attempts"] = 0
    s["patch_attempts"] = 0
    s["status"] = "pending"
p.write_text(json.dumps(s, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"  reset qa_state {p.name}")
PY
}

run_step() {
  local step="$1" id="$2"
  shift 2
  echo ""
  echo ">>> [$id] $step $(date -u +%H:%M:%S)"
  python3 dynasty_supplement.py --dynasty "$DYNASTY" --step "$step" --entry-id "$id" "$@"
}

for id in "${IDS[@]}"; do
  reset_qa "$id"
done

FAIL=0
OK=0
for id in "${IDS[@]}"; do
  echo ""
  echo "============================== $id =============================="
  if ! run_step anchor-research "$id"; then
    echo "!!! [$id] anchor-research 失败，跳过"
    FAIL=$((FAIL + 1))
    continue
  fi
  echo ">>> [$id] bibliography-plan --force-bibliography"
  python3 dynasty_supplement.py --dynasty "$DYNASTY" --step bibliography-plan --entry-id "$id" --force-bibliography || true
  run_step fetch-snippets "$id" || true
  run_step verify-bibliography "$id" || true
  COMPOSE_RC=0
  for compose_try in 1 2 3; do
    if python3 dynasty_supplement.py --dynasty "$DYNASTY" --step compose-detail --entry-id "$id" --force-bibliography; then
      COMPOSE_RC=0
      break
    fi
    COMPOSE_RC=1
    DETAIL_FILE=$(ls ../../../../data/06朝代知识补全/详情/"${id}"_*.json 2>/dev/null | head -1 || true)
    if [[ -n "$DETAIL_FILE" ]] && [[ "$compose_try" -lt 3 ]]; then
      echo ">>> [$id] compose 失败但可能有旧稿，重试 compose ($compose_try/3)…"
      continue
    fi
    if [[ "$compose_try" -lt 3 ]]; then
      echo ">>> [$id] compose 失败，重试 ($compose_try/3)…"
      continue
    fi
  done
  DETAIL_FILE=$(ls ../../../../data/06朝代知识补全/详情/"${id}"_*.json 2>/dev/null | head -1 || true)
  if [[ -z "$DETAIL_FILE" ]]; then
    echo "!!! [$id] compose-detail 失败且无成稿，跳过 qa"
    FAIL=$((FAIL + 1))
    continue
  fi
  if [[ "$COMPOSE_RC" -ne 0 ]]; then
    echo ">>> [$id] compose 收尾异常但成稿已落盘（${DETAIL_FILE##*/}），继续 qa-detail"
  fi
  python3 dynasty_supplement.py --dynasty "$DYNASTY" --step qa-detail --entry-id "$id" || true
  OK=$((OK + 1))
  echo ">>> [$id] 本条流程结束 OK=$OK FAIL=$FAIL"
done

echo ""
echo ">>> review-warns-summary"
python3 dynasty_supplement.py --dynasty "$DYNASTY" --step review-warns-summary || true
echo "========== DONE $(date -u +%Y-%m-%dT%H:%M:%SZ) OK=$OK FAIL=$FAIL =========="
