#!/usr/bin/env python3
"""五帝时期评述/见证批量补全（跳过已完成的五位帝王）。"""

from __future__ import annotations

import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SCRIPT_DIR.parent.parent))

import cw_lib as cw  # noqa: E402
from verify_cw import verify_file  # noqa: E402

DONE_IDS = frozenset(
    {
        "GLBL_00056",
        "GLBL_00057",
        "GLBL_00129",
        "GLBL_00144",
        "GLBL_00149",
    }
)


def main() -> int:
    cw.validate_histograph_root()
    paths = cw.histograph_paths()
    mid = paths["commentary"].parent / "05工作流中间产物" / "评述见证补全"
    mid.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    summary_path = mid / f"五帝_batch_summary_{stamp}.json"

    entries = cw.list_entries_by_dynasty("五帝")
    todo = [e for e in entries if str(e.get("史略ID") or "").strip() not in DONE_IDS]
    print(f"总 {len(entries)}，跳过帝王 {len(DONE_IDS)}，待处理 {len(todo)} × 2", flush=True)

    results: list[dict] = []
    for i, e in enumerate(todo, 1):
        eid = str(e.get("史略ID") or "").strip()
        name = str(e.get("史略名称") or "").strip()
        for mode in ("commentary", "witness"):
            label = "评述" if mode == "commentary" else "见证"
            out = cw.output_path(mode, e, paths)
            if out.is_file():
                try:
                    doc = json.loads(out.read_text(encoding="utf-8"))
                    if doc.get("status") in ("done", "已处理·无可用"):
                        issues = verify_file(out, mode=mode, strict=True)
                        if not any(x["level"] == "CRITICAL" for x in issues):
                            print(f"[{i}/{len(todo)}] ⏭ {label} {eid} {name}", flush=True)
                            results.append(
                                {"id": eid, "name": name, "mode": mode, "status": "skip"}
                            )
                            continue
                except Exception:
                    pass

            print(f"[{i}/{len(todo)}] → {label} {eid} {name} …", flush=True)
            try:
                r = cw.compose_one(mode, entry_id=eid, revise=True)
                status = r.get("status")
                if not status and out.is_file():
                    status = json.loads(out.read_text(encoding="utf-8")).get("status")
                n = r.get("entry_count")
                if n is None and out.is_file():
                    n = json.loads(out.read_text(encoding="utf-8")).get("entry_count")
                print(f"    ✅ {label} {eid} status={status} entries={n}", flush=True)
                results.append(
                    {
                        "id": eid,
                        "name": name,
                        "mode": mode,
                        "status": "ok",
                        "doc_status": status,
                        "entry_count": n,
                    }
                )
            except Exception as ex:
                print(f"    ❌ {label} {eid}: {ex}", flush=True)
                traceback.print_exc()
                results.append(
                    {
                        "id": eid,
                        "name": name,
                        "mode": mode,
                        "status": "error",
                        "error": str(ex),
                    }
                )

    err = [x for x in results if x["status"] == "error"]
    ok = [x for x in results if x["status"] in ("ok", "skip")]
    print(f"\n=== DONE ok/skip={len(ok)} err={len(err)} ===", flush=True)
    for x in err:
        print("ERR", x["mode"], x["id"], x.get("error"), flush=True)
    summary_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"summary → {summary_path}", flush=True)
    return 1 if err else 0


if __name__ == "__main__":
    raise SystemExit(main())
