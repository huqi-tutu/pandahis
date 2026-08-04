#!/usr/bin/env python3
"""战国 121 位人物关系 JSON → MySQL box_graph_* 批量入库。"""

from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import relations_lib as rl  # noqa: E402

DYNASTY = "战国"


def _default_mysql() -> dict:
    return {
        "host": os.environ.get("MYSQL_HOST", "49.235.165.220"),
        "port": int(os.environ.get("MYSQL_PORT", "3306")),
        "user": os.environ.get("MYSQL_USER", "histomap_admin"),
        "password": os.environ.get("MYSQL_PASSWORD", "pandahis#666"),
        "db": os.environ.get("MYSQL_DB", "histomap"),
    }


def main() -> int:
    rl.validate_histograph_root()
    paths = rl.histograph_paths()
    mysql = _default_mysql()
    persons = rl.list_dynasty_persons(DYNASTY)
    log = paths["dynasty_knowledge_work"] / "战国_关系入库.log"
    log.parent.mkdir(parents=True, exist_ok=True)

    ok_n, fail_n = 0, 0
    failures: list[dict] = []

    with log.open("a", encoding="utf-8") as lf:
        lf.write(f"\n--- import start {datetime.now(timezone.utc).isoformat()} count={len(persons)} ---\n")

        for e in persons:
            eid = str(e.get("史略ID", "")).strip()
            name = str(e.get("史略名称", "")).strip()
            fp = rl.output_path(paths, name)
            try:
                if not fp.is_file():
                    raise FileNotFoundError(f"缺少关系表: {fp.name}")
                verify_ok, verify_out = rl.run_verify(fp, strict=True)
                if not verify_ok:
                    raise RuntimeError(f"verify 未通过:\n{verify_out}")
                rl.import_json_file(fp, entry_id=eid, mysql=mysql)
                msg = f"OK {eid} {name}"
                print(msg, flush=True)
                lf.write(msg + "\n")
                ok_n += 1
            except Exception as exc:
                msg = f"FAIL {eid} {name}: {exc}"
                print(msg, file=sys.stderr, flush=True)
                lf.write(msg + "\n")
                lf.write(traceback.format_exc() + "\n")
                failures.append({"glbl": eid, "name": name, "error": str(exc)})
                fail_n += 1

        summary = f"--- import done ok={ok_n} fail={fail_n} total={len(persons)} ---\n"
        lf.write(summary)
        print(summary, flush=True)

    if failures:
        fail_path = paths["person_relations_work"] / "战国_关系入库_failures.json"
        fail_path.parent.mkdir(parents=True, exist_ok=True)
        fail_path.write_text(
            json.dumps({"dynasty": DYNASTY, "failures": failures}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"failures: {fail_path}", flush=True)

    return 1 if fail_n else 0


if __name__ == "__main__":
    raise SystemExit(main())
