#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建 V2 西汉君王顺译队列（独立于全局 v2_translate_queue）。"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "data" / "05工作流中间产物"
sys.path.insert(0, str(ROOT / "scripts"))

from v2_detail_routing import (  # noqa: E402
    has_detail,
    load_v2,
    queue_row,
    sort_rows,
    translate_eligible,
)

OUT_QUEUE = WORK / "v2_xihan_junwang_translate_queue.json"
OUT_REPORT = WORK / "v2_xihan_junwang_translate_report.json"

DYNASTY = "西汉"
CATEGORY = "君王"


def build_queue() -> dict:
    rows: list[dict] = []
    skipped: dict[str, int] = {}

    for entry in load_v2():
        if str(entry.get("二级朝代坐标") or "") != DYNASTY:
            continue
        if str(entry.get("史略分类") or "") != CATEGORY:
            continue
        eid = str(entry.get("史略ID") or "").strip()
        if not eid:
            continue
        if has_detail(eid):
            skipped["skip_done"] = skipped.get("skip_done", 0) + 1
            continue
        if translate_eligible(entry):
            rows.append(queue_row(entry, "translate"))
        else:
            rows.append(queue_row(entry, "compose"))

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": {"dynasty": DYNASTY, "category": CATEGORY},
        "policy": {
            "path": "translate skill → 11新标注条目翻译",
            "v1_04_policy": "04史料翻译仅留档，禁止 promote 至 11",
            "note": "西汉君王批次；不满足顺译条件的条目标记为 compose 供后续处理",
        },
        "entries": sort_rows(rows),
        "counts": {
            "translate": sum(1 for r in rows if r.get("路径") == "translate"),
            "compose": sum(1 for r in rows if r.get("路径") == "compose"),
            "skipped": skipped,
        },
    }


def main() -> int:
    data = build_queue()
    OUT_QUEUE.write_text(
        json.dumps(data["entries"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    OUT_REPORT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(data["counts"], ensure_ascii=False, indent=2))
    print(f"队列 → {OUT_QUEUE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
