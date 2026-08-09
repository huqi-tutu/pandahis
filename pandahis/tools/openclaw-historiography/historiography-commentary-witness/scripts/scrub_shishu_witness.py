#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""清除秦及以前见证中的史书/非诗词歌赋文学见证，并回写 MySQL。

规则：
  - 附加文学 / 传世文本：仅保留诗词歌赋；删除史记本纪等史书及杂剧演义论说等
  - 主名额中纯「传世史书文本」亦删除；出土简牍等实物保留
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SCRIPT_DIR.parent.parent))

import cw_lib as cw  # noqa: E402
import import_cw_lib as icw  # noqa: E402
from verify_cw import (  # noqa: E402
    is_allowed_literary_row,
    is_literary_extra,
    is_shishu_witness_row,
)

DEFAULT_DYNASTIES = ("五帝", "夏", "商", "西周", "春秋", "战国", "秦")
ONLINE = (
    Path(__file__).resolve().parents[4]
    / "data"
    / "12线上史略索引"
    / "史略索引_online.json"
)
# parents: scripts -> skill -> openclaw -> tools -> pandahis/pandahis
# Actually: .../pandahis/pandahis/tools/openclaw-historiography/historiography-commentary-witness/scripts
# parents[0]=scripts [1]=skill [2]=openclaw [3]=tools [4]=pandahis(pandahis)
MID = Path(__file__).resolve().parents[4] / "data" / "05工作流中间产物" / "评述见证补全"


def _should_drop(row: dict) -> tuple[bool, str]:
    if is_literary_extra(row):
        if is_shishu_witness_row(row):
            return True, "史书文学见证"
        if not is_allowed_literary_row(row):
            return True, "非诗词歌赋/文章文学见证"
        return False, ""
    if is_shishu_witness_row(row):
        return True, "主名额传世史书"
    return False, ""


def _renumber(entries: list[dict], entry: dict) -> list[dict]:
    eid = str(entry.get("史略ID") or "").strip()
    name = str(entry.get("史略名称") or "").strip()
    out: list[dict] = []
    for i, row in enumerate(entries, start=1):
        new_row = {**row}
        new_row["文物ID"] = f"{eid}_W{i:02d}"
        new_row["史略ID"] = eid
        new_row["史略名称"] = name
        out.append(new_row)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="清除史书类见证")
    parser.add_argument("--dynasties", nargs="+", default=list(DEFAULT_DYNASTIES))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-import", action="store_true")
    args = parser.parse_args()

    import os

    hist_root = Path(__file__).resolve().parents[4]
    os.environ["HISTOGRAPH_ROOT"] = str(hist_root)

    cw.validate_histograph_root()
    paths = cw.histograph_paths()
    index_path = hist_root / "data" / "12线上史略索引" / "史略索引_online.json"
    online = json.loads(index_path.read_text(encoding="utf-8"))
    if isinstance(online, dict):
        online = online.get("entries") or []

    allow = set(args.dynasties)
    report: list[dict] = []
    touched_ids: list[str] = []

    for e in online:
        dyn = str(e.get("二级朝代坐标") or "")
        if dyn not in allow:
            continue
        eid = str(e.get("史略ID") or "")
        fp = cw.output_path("witness", e, paths)  # type: ignore[arg-type]
        if not fp.is_file():
            hits = list(paths["witness"].glob(f"{eid}_*_见证.json"))
            if not hits:
                continue
            fp = hits[0]
        doc = json.loads(fp.read_text(encoding="utf-8"))
        entries = [r for r in (doc.get("entries") or []) if isinstance(r, dict)]
        kept: list[dict] = []
        dropped: list[dict] = []
        for row in entries:
            drop, reason = _should_drop(row)
            if drop:
                dropped.append(
                    {
                        "title": row.get("文物标题"),
                        "loc": row.get("现藏地点"),
                        "reason": reason,
                    }
                )
            else:
                kept.append(row)
        if not dropped:
            continue
        kept = _renumber(kept, e)
        status = "done" if kept else "已处理·无可用"
        new_doc = {
            **doc,
            "status": status,
            "entry_count": len(kept),
            "entries": kept,
            "processed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "_scrub_shishu_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "_scrub_dropped": len(dropped),
        }
        report.append(
            {
                "id": eid,
                "name": e.get("史略名称"),
                "dynasty": dyn,
                "before": len(entries),
                "after": len(kept),
                "dropped": dropped,
                "file": fp.name,
            }
        )
        touched_ids.append(eid)
        if not args.dry_run:
            fp.write_text(
                json.dumps(new_doc, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            cw.update_manifest("witness", e, new_doc, fp, paths=paths)

    MID.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = MID / f"scrub_shishu_witness_{stamp}.json"
    out.write_text(
        json.dumps(
            {
                "dry_run": args.dry_run,
                "dynasties": list(args.dynasties),
                "files_touched": len(report),
                "rows_dropped": sum(len(r["dropped"]) for r in report),
                "report": report,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"触及文件 {len(report)}，删除条目 {sum(len(r['dropped']) for r in report)}")
    by_dyn: dict[str, int] = {}
    for r in report:
        by_dyn[r["dynasty"]] = by_dyn.get(r["dynasty"], 0) + len(r["dropped"])
    for dyn in args.dynasties:
        if dyn in by_dyn:
            print(f"  {dyn}: 删 {by_dyn[dyn]} 条 / {sum(1 for r in report if r['dynasty']==dyn)} 文件")
    print(f"report → {out}")

    if args.dry_run or args.no_import or not touched_ids:
        return 0

    # MySQL：对触及 ID 重建见证行
    all_stmts: list[str] = []
    for eid in touched_ids:
        entry = cw.find_entry(entry_id=eid, index_path=index_path)
        fp = cw.output_path("witness", entry, paths)  # type: ignore[arg-type]
        if not fp.is_file():
            continue
        doc = icw.load_json(fp)
        all_stmts.extend(icw.build_relic_sql(doc))
    if all_stmts:
        # batch
        for i in range(0, len(all_stmts), 500):
            icw.execute_mysql(all_stmts[i : i + 500], **icw.default_mysql_kwargs())
        print(f"☁️ MySQL 已更新 {len(touched_ids)} 个史略的见证")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
