#!/usr/bin/env bash
# 三国朝代知识补全 · Step 1 研究报告（结束后自动更新遗漏审阅提示词）
set -euo pipefail
export HISTOGRAPH_ROOT="/Users/rachelcheng/Desktop/padanhis/pandahis/pandahis"
SCRIPT="$HISTOGRAPH_ROOT/tools/openclaw-historiography/historiography-dynasty-knowledge/scripts/dynasty_supplement.py"
LOG_DIR="$HISTOGRAPH_ROOT/data/05工作流中间产物/朝代知识补全"
DYN="三国"

echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) START research ====="
python3 -u "$SCRIPT" --dynasty "$DYN" --step research
echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) DONE  research ====="
