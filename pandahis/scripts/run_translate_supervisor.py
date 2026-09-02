#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""单条目顺译 supervisor：纯读决策 + 子进程 translate，直到 verify 通过或达上限。"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
WORK = DATA / "05工作流中间产物" / "翻译"
TRANSLATE = ROOT / "tools" / "openclaw-historiography" / "historiography-translate"
V2_INDEX = DATA / "10新标注条目" / "史略索引_史记汉书.json"
OUT_11 = DATA / "11新标注条目翻译"

sys.path.insert(0, str(ROOT / "scripts"))
from translate_queue_helpers import (  # noqa: E402
    build_translate_run,
    is_api_transient_error,
    is_translate_verify_done,
)
from run_v2_translate_queue import _build_cmd, _read_log_tail  # noqa: E402


def _log_line(log: Path, message: str) -> None:
    log.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat()
    with log.open("a", encoding="utf-8") as fh:
        fh.write(f"[{stamp}] {message}\n")
        fh.flush()
    print(message, flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="单条目顺译无人值守 supervisor")
    parser.add_argument("--id", required=True, help="史略 ID，如 GLBL_00084")
    parser.add_argument("--name", default="", help="史略名称（可选，加速纯读判定）")
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=int(__import__("os").environ.get("TRANSLATE_SUPERVISOR_MAX_ROUNDS", "8")),
    )
    parser.add_argument(
        "--entry-retries",
        type=int,
        default=int(__import__("os").environ.get("TRANSLATE_QUEUE_ENTRY_RETRIES", "3")),
    )
    parser.add_argument(
        "--api-backoff-sec",
        type=int,
        default=int(__import__("os").environ.get("TRANSLATE_QUEUE_API_BACKOFF_SEC", "60")),
    )
    parser.add_argument(
        "--idle-sleep-sec",
        type=int,
        default=15,
        help="一轮结束后若仍未完成，等待秒数再决策下一轮",
    )
    args = parser.parse_args()

    eid = args.id.strip()
    name = args.name.strip()
    log = WORK / f"{eid}_supervisor.out"

    if is_translate_verify_done(eid, entry_name=name or None):
        _log_line(log, f"✅ {eid} 已通过 verify，supervisor 退出")
        return 0

    consecutive_infra = 0
    for round_n in range(1, args.max_rounds + 1):
        if is_translate_verify_done(eid, entry_name=name or None):
            _log_line(log, f"✅ {eid} 第 {round_n} 轮前检测到已完成")
            return 0

        spec = build_translate_run(eid, entry_name=name or None)
        _log_line(
            log,
            f"▶️ 第 {round_n}/{args.max_rounds} 轮 mode={spec.label()} — {spec.reason}",
        )

        last_rc = 1
        for attempt in range(1, max(1, args.entry_retries) + 1):
            cmd = _build_cmd(spec, eid)
            _log_line(log, f"   attempt {attempt}: {' '.join(cmd)}")
            with log.open("a", encoding="utf-8") as fh:
                fh.write(
                    f"\n===== {datetime.now(timezone.utc).isoformat()} "
                    f"supervisor round={round_n} attempt={attempt} =====\n"
                )
                fh.flush()
                proc = subprocess.run(
                    cmd,
                    cwd=str(TRANSLATE),
                    stdout=fh,
                    stderr=subprocess.STDOUT,
                )
            last_rc = proc.returncode

            if is_translate_verify_done(eid, entry_name=name or None):
                _log_line(log, f"✅ {eid} verify 通过（round={round_n} attempt={attempt}）")
                return 0

            tail = _read_log_tail(log)
            if attempt < args.entry_retries and is_api_transient_error(tail):
                wait = args.api_backoff_sec * attempt
                _log_line(log, f"   ⏳ API transient，{wait}s 后重试…")
                time.sleep(wait)
                spec = build_translate_run(eid, entry_name=name or None)
                continue
            break

        tail = _read_log_tail(log)
        if last_rc != 0 and is_api_transient_error(tail):
            consecutive_infra += 1
            if consecutive_infra >= 3:
                _log_line(
                    log,
                    f"❌ {eid} 连续 {consecutive_infra} 轮 API/网络故障，"
                    "网关疑似长时间不可用，supervisor 提前放弃（不再空转）",
                )
                return 1
        else:
            consecutive_infra = 0

        if last_rc == 0:
            _log_line(log, f"   子进程 exit=0 但 verify 未通过，{args.idle_sleep_sec}s 后再决策")
        else:
            _log_line(log, f"   子进程 exit={last_rc}，{args.idle_sleep_sec}s 后再决策")

        time.sleep(args.idle_sleep_sec)

    _log_line(log, f"❌ {eid} 达 max_rounds={args.max_rounds}，supervisor 放弃")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
