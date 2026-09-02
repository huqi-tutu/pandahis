#!/usr/bin/env bash
# 三国 compose 进度快照（每 60s 写一次，供 agent/用户查看）
set -euo pipefail

ROOT="/Users/rachelcheng/Desktop/padanhis/pandahis/pandahis"
LOG_DIR="$ROOT/data/05工作流中间产物/朝代知识补全"
LOG="$LOG_DIR/三国_phase3_runner.out"
RESUME_LOG="$LOG_DIR/三国_phase3_resume.out"
if [[ -f "$RESUME_LOG" ]] && [[ "$RESUME_LOG" -nt "$LOG" ]]; then
  LOG="$RESUME_LOG"
fi
OUT="$LOG_DIR/三国_compose_status.txt"
DETAILS="$ROOT/data/06朝代知识补全/详情"

while true; do {
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  running="no"
  if pgrep -f "dynasty_supplement.py --dynasty 三国" >/dev/null 2>&1; then
    running="yes"
  elif pgrep -f "三国_phase3" >/dev/null 2>&1; then
    running="yes"
  fi

  done_cnt="$(find "$DETAILS" -maxdepth 1 \( -name 'GLBL_017*.json' -o -name 'GLBL_018*.json' \) 2>/dev/null | wc -l | tr -d ' ')"
  progress="$(grep -E '^\s+\[[0-9]+/81\]' "$LOG" 2>/dev/null | tail -1 | sed 's/^[[:space:]]*//' || true)"
  last_ok="$(grep -E '✅ 详情|✅ compose-detail|落盘' "$LOG" 2>/dev/null | tail -1 | sed 's/^[[:space:]]*//' || true)"
  last_err="$(grep -E '❌|失败|Error|Traceback' "$LOG" 2>/dev/null | tail -1 | sed 's/^[[:space:]]*//' || true)"
  phase="$(grep -E '^(=====|✅ compose-pending|⚠️ compose-pending|START qa-detail|START gate|COMPOSE PHASE COMPLETE)' "$LOG" 2>/dev/null | tail -1 || true)"

  {
    echo "更新时间(UTC): $ts"
    echo "进程运行中: $running"
    echo "已落盘详情: $done_cnt / 81"
    echo "当前进度行: ${progress:-（尚无 [N/81] 行，可能在 anchor/bibliography）}"
    echo "最近成功: ${last_ok:-—}"
    echo "最近错误: ${last_err:-—}"
    echo "流水线阶段: ${phase:-—}"
    echo "---"
    echo "日志末尾:"
    tail -5 "$LOG" 2>/dev/null || echo "(无日志)"
  } > "$OUT"

  if grep -q "COMPOSE PHASE COMPLETE\|RESUME COMPLETE" "$LOG" 2>/dev/null; then
    echo "[$ts] 全流程结束，watcher 退出" >> "$OUT"
    break
  fi
  if [[ "$running" == "no" ]] && grep -qE "compose-pending 完成|compose-pending 部分完成|DONE  compose-pending" "$LOG" 2>/dev/null; then
    # 仅 compose 结束、后续 gate 还在跑时继续监控
    if ! pgrep -f "三国_phase3" >/dev/null 2>&1; then
      echo "[$ts] compose-pending 已结束，watcher 退出" >> "$OUT"
      break
    fi
  fi

  sleep 60
}; done
