#!/usr/bin/env python3
"""批量处理待补全清单条目，产出至 _patch_output/ 待审。"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.config import load_dotenv, paths  # noqa: E402
from lib.patch_paragraphs import (  # noqa: E402
    DEFAULT_MANIFEST,
    promote_source_only,
    patch_paragraphs,
)

SOURCE_ONLY_IDS = frozenset({"GLBL_00730"})  # 赵简子：仅补史料原文


def main() -> int:
    load_dotenv()
    manifest = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
    entries = manifest.get("entries") or []
    out_dir = paths()["root"] / "data" / "11新标注条目翻译" / "待补全段落翻译" / "_patch_output"
    out_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "total": len(entries),
        "ok": [],
        "fail": [],
    }

    for i, entry in enumerate(entries, 1):
        eid = entry["id"]
        name = entry["name"]
        print(f"[{i}/{len(entries)}] {eid} {name} side={entry['side']}", flush=True)

        if eid in SOURCE_ONLY_IDS:
            ok, msg = promote_source_only(eid)
        else:
            ok, msg = patch_paragraphs(eid)

        row = {"id": eid, "name": name, "message": msg}
        if ok:
            report["ok"].append(row)
            print(f"  OK: {msg}", flush=True)
        else:
            report["fail"].append(row)
            print(f"  FAIL: {msg}", flush=True)

    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    report["ok_count"] = len(report["ok"])
    report["fail_count"] = len(report["fail"])
    report_path = out_dir / "batch_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n完成: {report['ok_count']} 成功, {report['fail_count']} 失败 → {report_path}")
    return 0 if not report["fail"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
