#!/usr/bin/env bash
# 朝代知识补全 · 后台执行包装
# 用法：./run_supplement_bg.sh 五帝 fill-renwu
#       ./run_supplement_bg.sh 五帝 compose-pending
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DYNASTY="${1:?用法: $0 <朝代名> <step> [extra args...]}"
STEP="${2:?}"
shift 2

exec python3 "$SCRIPT_DIR/dynasty_supplement.py" \
  --dynasty "$DYNASTY" \
  --step "$STEP" \
  --background \
  "$@"
