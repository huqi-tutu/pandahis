#!/usr/bin/env python3
"""实时监控春秋批跑日志，突出语义覆盖与新规则相关事件。"""

from __future__ import annotations

import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

TZ = timezone(timedelta(hours=8))
ROOT = Path(os.environ.get("HISTOGRAPH_ROOT", Path(__file__).resolve().parents[3]))
LOG = ROOT / "data" / "05工作流中间产物" / "翻译" / "logs" / "春秋_translate_batch.log"
OUT = LOG.parent / "春秋_batch_watch.log"

ENTRY_RE = re.compile(r"^\[(\d+)/(\d+)\] → (GLBL_\d+) (.+) …")
DONE_RE = re.compile(r"^✅ (GLBL_\d+) 完成 (\d+) 字")
FAIL_RE = re.compile(r"^❌ 翻译未通过")
PHASE_FAIL_RE = re.compile(r"^⚠️ Phase\d+ 未通过: (.+)")
COVERAGE_OK_RE = re.compile(r"ℹ️ 母本语义覆盖: (.+)")
COVERAGE_SKIP_RE = re.compile(r"ℹ️ 语义覆盖：(.+)")
COVERAGE_FAIL_RE = re.compile(r"母本语义覆盖不足")
COVERAGE_BATCH_RE = re.compile(
    r"ℹ️ 语义覆盖复核 \[(?P<cur>\d+)/(?P<total>\d+)\].*"
    r"conveyed=(?P<conveyed>\d+).*unclear=(?P<unclear>\d+)"
)
COVERAGE_START_RE = re.compile(r"ℹ️ 语义覆盖复核开始: (?P<n>\d+) 单元 → (?P<b>\d+) 批")
PHASE1_MERGE_RE = re.compile(r"^📦 Phase1 分批顺译 (GLBL_\d+)")


def _ts() -> str:
    return datetime.now(TZ).strftime("%H:%M:%S")


def _emit(line: str, fout) -> None:
    fout.write(line + "\n")
    fout.flush()


def _format_event(raw: str) -> str | None:
    s = raw.rstrip()
    if not s or s.startswith("第 ") and "批（" in s:
        return None
    m = ENTRY_RE.match(s)
    if m:
        idx, total, _gid, name = m.groups()
        return f"[{_ts()}] ▶ 开始 [{idx}/{total}] {name}"
    m = DONE_RE.match(s)
    if m:
        gid, wc = m.groups()
        return f"[{_ts()}] ✅ 完成 {gid} ({wc}字)"
    if FAIL_RE.match(s):
        return f"[{_ts()}] ❌ 本条未通过（见下方原因）"
    m = PHASE_FAIL_RE.match(s)
    if m:
        return f"[{_ts()}]    └ Phase 失败: {m.group(1)[:120]}"
    m = COVERAGE_OK_RE.search(s)
    if m:
        return f"[{_ts()}] 🟢 语义覆盖通过: {m.group(1)}"
    m = COVERAGE_SKIP_RE.search(s)
    if m:
        return f"[{_ts()}] 📋 语义覆盖缓存: {m.group(1)}"
    if COVERAGE_FAIL_RE.search(s) or "母本语义覆盖" in s and "不足" in s:
        return f"[{_ts()}] 🔴 语义覆盖拦截: {s.strip()[:160]}"
    m = COVERAGE_START_RE.search(s)
    if m:
        return f"[{_ts()}] 🔍 语义覆盖开始: {m.group('n')} 单元 / {m.group('b')} 批"
    m = COVERAGE_BATCH_RE.search(s)
    if m:
        return (
            f"[{_ts()}] 🔍 语义覆盖 [{m.group('cur')}/{m.group('total')}] "
            f"conveyed={m.group('conveyed')} unclear={m.group('unclear')}"
        )
    if "语义覆盖账本已更新" in s:
        return f"[{_ts()}] 📒 {s.strip()}"
    if "语义覆盖复核完成" in s:
        return f"[{_ts()}] 🏁 {s.strip()}"
    m = PHASE1_MERGE_RE.match(s)
    if m:
        return f"[{_ts()}] 📦 Phase1 分批 {m.group(1)}（分批阶段不验覆盖）"
    if s.strip().startswith("Phase1:") or s.strip().startswith("Phase2:"):
        return f"[{_ts()}]    └ {s.strip()[:140]}"
    if "母本覆盖不足" in s or "必现词" in s and "阻断" in s:
        return f"[{_ts()}] ⚠️  {s.strip()[:140]}"
    return None


def main() -> int:
    if not LOG.is_file():
        print(f"日志不存在: {LOG}", file=sys.stderr)
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    start_pos = LOG.stat().st_size
    _emit(f"=== 监控启动 {_ts()} | 自字节 {start_pos} 起 ===", OUT.open("a", encoding="utf-8"))

    with LOG.open("r", encoding="utf-8", errors="replace") as fin, OUT.open(
        "a", encoding="utf-8"
    ) as fout:
        fin.seek(start_pos)
        while True:
            line = fin.readline()
            if line:
                event = _format_event(line)
                if event:
                    _emit(event, fout)
            else:
                time.sleep(1.0)
                try:
                    if fin.tell() > LOG.stat().st_size:
                        fin.seek(0)
                except OSError:
                    pass


if __name__ == "__main__":
    raise SystemExit(main())
