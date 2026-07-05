#!/usr/bin/env bash
# 无人值守批量标注：逐卷 LLM（Step1/3/4），编排器自动循环。
# 用法见 historiography-orchestrator/SKILL.md「批量跑批」

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ORCH="$ROOT/historiography-orchestrator"
ENV_FILE="${HIST_ENV_FILE:-$ROOT/.env}"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

: "${HISTOGRAPH_ROOT:?请 export HISTOGRAPH_ROOT=... 或在 $ROOT/.env 配置}"

export HIST_BATCH_AUTO="${HIST_BATCH_AUTO:-1}"
export HIST_AUTO_COORD="${HIST_AUTO_COORD:-emperor-ssot}"

WORK="${1:-01史记}"
LOG_DIR="${HISTOGRAPH_ROOT}/data/05工作流中间产物/编排/logs"
mkdir -p "$LOG_DIR"
STAMP="$(date +%Y%m%d_%H%M%S)"
LOG="$LOG_DIR/batch_${WORK}_${STAMP}.log"

cd "$ORCH"
echo "▶ 批量 daemon 启动 work=$WORK log=$LOG"
echo "   HIST_BATCH_AUTO=$HIST_BATCH_AUTO  HIST_AUTO_COORD=$HIST_AUTO_COORD"
echo "   金标须先: python3 hist.py approve-gold --work $WORK"

exec python3 hist.py run-batch --work "$WORK" --loop --sleep "${HIST_BATCH_SLEEP:-120}" 2>&1 | tee "$LOG"
