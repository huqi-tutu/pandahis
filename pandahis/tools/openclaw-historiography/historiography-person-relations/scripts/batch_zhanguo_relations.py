#!/usr/bin/env python3
"""战国人物关系批量补全（子进程隔离 + 单人超时 + 失败跳过）"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import relations_lib as rl  # noqa: E402

# 单人上限：5 类 × 3 轮 LLM，正常 ~2min；异常人物不应拖死整批
PER_PERSON_TIMEOUT_SEC = 600
SKIP_NAMES = frozenset()  # 不跳过；失败/超时记日志后继续
LOCK_FILE = Path(__file__).resolve().parent / ".batch_zhanguo.lock"


def append_log(log: Path, msg: str) -> None:
    with log.open("a", encoding="utf-8") as f:
        f.write(msg + "\n")
    print(msg, flush=True)


def compose_one_isolated(entry_id: str) -> tuple[bool, str]:
    """在子进程中补全单人；崩溃/超时不影响主进程。"""
    env = os.environ.copy()
    env.setdefault("HISTOGRAPH_ROOT", str(rl.histograph_paths()["root"]))
    cmd = [
        sys.executable,
        str(SCRIPT_DIR / "relations.py"),
        "compose-one",
        "--id",
        entry_id,
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(SCRIPT_DIR),
            env=env,
            capture_output=True,
            text=True,
            timeout=PER_PERSON_TIMEOUT_SEC,
        )
    except subprocess.TimeoutExpired:
        return False, f"超时（>{PER_PERSON_TIMEOUT_SEC}s）"
    except Exception as exc:
        return False, str(exc)

    if proc.returncode == 0:
        return True, "OK"
    detail = (proc.stderr or proc.stdout or "").strip().splitlines()
    return False, detail[-1] if detail else f"exit {proc.returncode}"


def main() -> int:
    rl.validate_histograph_root()
    if LOCK_FILE.exists():
        try:
            old_pid = int(LOCK_FILE.read_text(encoding="utf-8").strip())
            os.kill(old_pid, 0)
            print(f"已有批次在运行 (PID {old_pid})，退出", flush=True)
            return 1
        except (OSError, ValueError):
            LOCK_FILE.unlink(missing_ok=True)
    LOCK_FILE.write_text(str(os.getpid()), encoding="utf-8")
    try:
        return _run_batch()
    finally:
        LOCK_FILE.unlink(missing_ok=True)


def _run_batch() -> int:
    rl.validate_histograph_root()
    paths = rl.histograph_paths()
    persons = rl.list_dynasty_persons("战国")
    rel_dir = paths["person_relations"]
    log = paths["dynasty_knowledge_work"] / "战国_关系补全.log"
    log.parent.mkdir(parents=True, exist_ok=True)

    pending = [
        e
        for e in persons
        if not (rel_dir / f"{e['史略名称']}关系表.json").exists()
        and e["史略名称"] not in SKIP_NAMES
    ]
    append_log(log, f"--- batch start pending={len(pending)} (isolated subprocess) ---")

    ok_n, fail_n = 0, 0
    for e in pending:
        name = str(e.get("史略名称", "")).strip()
        eid = str(e.get("史略ID", "")).strip()
        success, detail = compose_one_isolated(eid)
        if success and (rel_dir / f"{name}关系表.json").exists():
            recs = json.loads((rel_dir / f"{name}关系表.json").read_text(encoding="utf-8"))
            append_log(log, f"OK {eid} {name} ({len(recs)}条)")
            ok_n += 1
        else:
            append_log(log, f"FAIL {eid} {name}: {detail}")
            fail_n += 1
        rl.write_dynasty_manifest("战国")

    mf = rl.write_dynasty_manifest("战国")
    completed = len(json.loads(mf.read_text(encoding="utf-8"))["completed"])
    append_log(
        log,
        f"--- batch done completed={completed}/{len(persons)} ok={ok_n} fail={fail_n} ---",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
