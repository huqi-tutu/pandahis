#!/usr/bin/env python3
"""商朝全部史略：评述 + 见证批量补全（跳过已 verify 通过的条目）。"""

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

DYNASTY = "商"


def _already_done(mode: str, entry: dict, paths: dict) -> bool:
    out = cw.output_path(mode, entry, paths)  # type: ignore[arg-type]
    if not out.is_file():
        return False
    try:
        doc = json.loads(out.read_text(encoding="utf-8"))
        if doc.get("status") not in ("done", "已处理·无可用"):
            return False
        issues = verify_file(out, mode=mode, strict=True)  # type: ignore[arg-type]
        return not any(x["level"] == "CRITICAL" for x in issues)
    except Exception:
        return False


def _import_all(ids: list[str]) -> int:
    import import_cw_lib as icw  # noqa: WPS433

    all_stmts: list[str] = []
    imported = 0
    for eid in ids:
        entry = cw.find_entry(entry_id=eid)
        for mode in ("commentary", "witness"):
            fp = cw.output_path(mode, entry)  # type: ignore[arg-type]
            if not fp.is_file():
                continue
            doc = icw.load_json(fp)
            stmts = (
                icw.build_critique_sql(doc)
                if mode == "commentary"
                else icw.build_relic_sql(doc)
            )
            if len(stmts) > 1:
                imported += 1
            all_stmts.extend(stmts)
    if not all_stmts:
        return 0
    icw.execute_mysql(all_stmts, **icw.default_mysql_kwargs())  # type: ignore[arg-type]
    return imported


def main() -> int:
    cw.validate_histograph_root()
    cw.ensure_deepseek_v4_pro()
    paths = cw.histograph_paths()
    mid = paths["commentary"].parent / "05工作流中间产物" / "评述见证补全"
    mid.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    summary_path = mid / f"商_batch_summary_{stamp}.json"
    log_path = mid / f"商_batch_run_{stamp}.log"

    entries = cw.list_entries_by_dynasty(DYNASTY)
    print(f"商朝史略 {len(entries)} 条 × 评述+见证", flush=True)

    results: list[dict] = []
    ok_ids: list[str] = []

    for mode in ("commentary", "witness"):
        label = "评述" if mode == "commentary" else "见证"
        for i, e in enumerate(entries, 1):
            eid = str(e.get("史略ID") or "").strip()
            name = str(e.get("史略名称") or "").strip()
            if _already_done(mode, e, paths):
                print(f"[{label} {i}/{len(entries)}] ⏭ {eid} {name}", flush=True)
                results.append({"id": eid, "name": name, "mode": mode, "status": "skip"})
                if eid not in ok_ids:
                    ok_ids.append(eid)
                continue

            print(f"[{label} {i}/{len(entries)}] → {eid} {name} …", flush=True)
            try:
                r = cw.compose_one(mode, entry_id=eid, revise=True)  # type: ignore[arg-type]
                print(
                    f"    ✅ {label} {eid} status={r.get('status')} entries={r.get('entry_count')}",
                    flush=True,
                )
                results.append(
                    {
                        "id": eid,
                        "name": name,
                        "mode": mode,
                        "status": "ok",
                        "doc_status": r.get("status"),
                        "entry_count": r.get("entry_count"),
                    }
                )
                if eid not in ok_ids:
                    ok_ids.append(eid)
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
    print(f"\n=== 生成 DONE ok/skip={len(ok)} err={len(err)} ===", flush=True)

    try:
        n = _import_all(sorted(set(ok_ids)))
        print(f"☁️ MySQL 导入完成（{n} 个 mode×条目 有数据行）", flush=True)
    except Exception as ex:
        print(f"⚠️ MySQL 导入失败: {ex}", flush=True)
        traceback.print_exc()

    from verify_cw import verify_dynasty_commentary  # noqa: WPS433

    dyn_issues = verify_dynasty_commentary(DYNASTY, commentary_dir=paths["commentary"])
    for it in dyn_issues:
        print(f"DYNASTY {it['level']}: {it['msg']}", flush=True)

    summary = {
        "stamp": stamp,
        "dynasty": DYNASTY,
        "total_entries": len(entries),
        "results": results,
        "dynasty_issues": dyn_issues,
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"summary → {summary_path}", flush=True)
    return 1 if err else 0


if __name__ == "__main__":
    raise SystemExit(main())
