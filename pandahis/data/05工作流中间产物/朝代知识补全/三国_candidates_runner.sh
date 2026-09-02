#!/usr/bin/env bash
# 三国朝代知识补全 · 候选生成（事略/典制/论著/人物）
set -euo pipefail
export HISTOGRAPH_ROOT="/Users/rachelcheng/Desktop/padanhis/pandahis/pandahis"
SCRIPT="$HISTOGRAPH_ROOT/tools/openclaw-historiography/historiography-dynasty-knowledge/scripts/dynasty_supplement.py"
LOG_DIR="$HISTOGRAPH_ROOT/data/05工作流中间产物/朝代知识补全"
DYN="三国"

for step in candidates-shilue candidates-dianzhi candidates-lunzhu candidates-renwu; do
  echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) START $step ====="
  python3 -u "$SCRIPT" --dynasty "$DYN" --step "$step"
  echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) DONE  $step ====="
done

echo "===== ALL CANDIDATE STEPS COMPLETE ====="
