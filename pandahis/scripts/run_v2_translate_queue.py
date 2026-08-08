#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""逐条运行 V2 顺译 skill（translate.py run-one）；西汉 excluded。"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
WORK = DATA / "05工作流中间产物"
DEFAULT_QUEUE = WORK / "v2_translate_queue.json"
DEFAULT_CHECKPOINT = WORK / "v2_translate_checkpoint.json"
COMPOSE_CHECKPOINT = WORK / "v2_compose_checkpoint.json"
TRANSLATE = ROOT / "tools" / "openclaw-historiography" / "historiography-translate"
V2_INDEX = DATA / "10新标注条目" / "史略索引_史记汉书.json"
OUT_11 = DATA / "11新标注条目翻译"
TRANSLATE_WORK = WORK / "翻译"

sys.path.insert(0, str(ROOT / "scripts"))
from translate_queue_helpers import (  # noqa: E402
    is_translate_verify_done,
    pick_retry_mode,
)
from v2_detail_routing import (  # noqa: E402
    has_06,
    has_11,
    is_valid_v2_11_doc,
)

SKIP_11_FILES = frozenset({"翻译复用清单.json"})
T11 = OUT_11


def load_checkpoint(checkpoint_path: Path) -> dict:
    if checkpoint_path.is_file():
        return json.loads(checkpoint_path.read_text(encoding="utf-8"))
    return {"done": [], "failed": []}


def save_checkpoint(state: dict, checkpoint_path: Path) -> None:
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    checkpoint_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def prune_checkpoint(state: dict) -> set[str]:
    """移除误标 done（未通过 Skill verify_output）。"""
    done = {
        eid
        for eid in (state.get("done") or [])
        if is_translate_verify_done(eid)
    }
    state["done"] = sorted(done)
    return done


def remove_invalid_11(eid: str) -> int:
    """删除 11 目录内无效/半成品 JSON，便于 phase2 重跑。"""
    removed = 0
    for fp in T11.glob(f"{eid}_*.json"):
        if fp.name in SKIP_11_FILES:
            continue
        try:
            doc = json.loads(fp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            fp.unlink(missing_ok=True)
            removed += 1
            continue
        if not is_valid_v2_11_doc(doc):
            fp.unlink(missing_ok=True)
            removed += 1
    return removed


def run_translate(eid: str, name: str, log: Path) -> tuple[bool, str, str]:
    mode = pick_retry_mode(eid, entry_name=name)
    remove_invalid_11(eid)

    base = [
        sys.executable,
        str(TRANSLATE / "translate.py"),
    ]
    if mode == "repair":
        cmd = base + [
            "repair",
            "--id",
            eid,
            "--execute",
            "--index",
            str(V2_INDEX),
            "--output-dir",
            str(OUT_11),
        ]
    elif mode == "phase2":
        cmd = base + [
            "run-one",
            "--id",
            eid,
            "--index",
            str(V2_INDEX),
            "--output-dir",
            str(OUT_11),
            "--from-phase",
            "phase2",
        ]
    else:
        cmd = base + [
            "run-one",
            "--id",
            eid,
            "--index",
            str(V2_INDEX),
            "--output-dir",
            str(OUT_11),
        ]

    with log.open("a", encoding="utf-8") as fh:
        fh.write(
            f"\n===== {datetime.now(timezone.utc).isoformat()} translate {eid} "
            f"({name}) mode={mode} =====\n"
        )
        fh.flush()
        proc = subprocess.run(cmd, cwd=str(TRANSLATE), stdout=fh, stderr=subprocess.STDOUT)

    if is_translate_verify_done(eid, entry_name=name):
        return True, "ok", mode
    return False, f"exit={proc.returncode}", mode


def translate_queue_satisfied(queue: list[dict]) -> bool:
    return all(
        is_translate_verify_done(r["史略ID"], entry_name=r.get("史略名称"))
        or has_06(r["史略ID"])
        for r in queue
    )


def unpause_and_run_compose() -> int:
    if not COMPOSE_CHECKPOINT.is_file():
        print("缺少 compose checkpoint，跳过", file=sys.stderr)
        return 1
    cp = json.loads(COMPOSE_CHECKPOINT.read_text(encoding="utf-8"))
    if cp.get("paused"):
        cp.pop("paused", None)
        cp.pop("pause_reason", None)
        cp.pop("paused_at", None)
        cp["unpaused_at"] = datetime.now(timezone.utc).isoformat()
        cp["unpause_note"] = "顺译队列已全部有效完成，自动解除暂停"
        COMPOSE_CHECKPOINT.write_text(
            json.dumps(cp, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print("✅ compose checkpoint 已解除 paused")

    log = WORK / "朝代知识补全" / "v2_compose_queue.log"
    compose_script = ROOT / "scripts" / "run_v2_compose_queue.py"
    with log.open("a", encoding="utf-8") as fh:
        fh.write(
            f"\n===== {datetime.now(timezone.utc).isoformat()} auto-start compose =====\n"
        )
        fh.flush()
        proc = subprocess.run(
            [sys.executable, str(compose_script)],
            cwd=str(ROOT),
            stdout=fh,
            stderr=subprocess.STDOUT,
        )
    return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--then-compose",
        action="store_true",
        help="顺译全部有效完成后自动解除 compose 暂停并运行 compose 队列",
    )
    parser.add_argument(
        "--prune-only",
        action="store_true",
        help="仅修正 checkpoint done 列表（去掉误标完成）",
    )
    parser.add_argument(
        "--queue",
        type=Path,
        default=DEFAULT_QUEUE,
        help="顺译队列 JSON（默认 v2_translate_queue.json）",
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=None,
        help="checkpoint JSON（默认同队列名前缀，如 v2_xihan_junwang_translate_checkpoint.json）",
    )
    args = parser.parse_args()

    queue_path = args.queue
    checkpoint_path = args.checkpoint or queue_path.with_name(
        queue_path.stem.replace("_queue", "_checkpoint") + ".json"
    )

    if not queue_path.is_file():
        print(f"缺少队列: {queue_path}", file=sys.stderr)
        return 1

    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    state = load_checkpoint(checkpoint_path)
    done = prune_checkpoint(state)
    failed_map = {x["史略ID"]: x for x in state.get("failed") or []}
    save_checkpoint(state, checkpoint_path)

    if args.prune_only:
        print(f"checkpoint done 已修正为 {len(done)} 条（仅保留 verify_output 通过）")
        return 0

    pending = [
        r
        for r in queue
        if r.get("路径", "translate") == "translate"
        and not is_translate_verify_done(
            r["史略ID"], entry_name=r.get("史略名称")
        )
        and not has_06(r["史略ID"])
    ]
    if args.limit:
        pending = pending[: args.limit]

    if not pending:
        print(f"无待顺译条目（队列 {len(queue)}，有效完成 {len(done)}）")
        if args.then-compose and translate_queue_satisfied(queue):
            return unpause_and_run_compose()
        return 0

    log = WORK / "朝代知识补全" / f"{queue_path.stem}.log"
    log.parent.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        print(f"待重跑 {len(pending)} 条：")
        for i, row in enumerate(pending[:20], 1):
            eid = row["史略ID"]
            print(
                f"  [{i}] {eid} {row.get('史略名称')} "
                f"mode={pick_retry_mode(eid, entry_name=row.get('史略名称'))}"
            )
        return 0

    ok_n = 0
    for i, row in enumerate(pending, 1):
        eid = row["史略ID"]
        name = row.get("史略名称") or ""
        print(f"[{i}/{len(pending)}] translate {eid} {name} (mode={pick_retry_mode(eid, entry_name=name)})")
        ok, msg, mode = run_translate(eid, name, log)
        if ok:
            done.add(eid)
            failed_map.pop(eid, None)
            ok_n += 1
            print(f"  ✅ {eid} ({mode})")
        else:
            failed_map[eid] = {
                "史略ID": eid,
                "史略名称": name,
                "error": msg,
                "mode": mode,
            }
            print(f"  ❌ {eid} — {msg} ({mode})")
        state["done"] = sorted(done)
        state["failed"] = list(failed_map.values())
        save_checkpoint(state, checkpoint_path)

    print(
        f"顺译完成 {ok_n}/{len(pending)} | 有效累计 {len(done)} | checkpoint → {checkpoint_path}"
    )

    if ok_n == len(pending) and args.then_compose and translate_queue_satisfied(queue):
        print("顺译队列已全部有效完成，启动 compose…")
        return unpause_and_run_compose()

    return 0 if ok_n == len(pending) else 1


if __name__ == "__main__":
    raise SystemExit(main())
