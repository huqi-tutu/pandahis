#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建 V2 西汉剩余（非君王）顺译队列。

君王 11 条已由 v2_xihan_junwang_* 单独跑完；本队列覆盖其余分类
（文臣/宗戚/武将/庶众/蕃祚/宦官），全部走 translate skill → 11。
"""

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

OUT_QUEUE = WORK / "v2_xihan_remaining_translate_queue.json"
OUT_REPORT = WORK / "v2_xihan_remaining_translate_report.json"

DYNASTY = "西汉"
SKIP_CATEGORIES = frozenset({"君王"})


def build_queue() -> dict:
    rows: list[dict] = []
    skipped: dict[str, int] = {}

    for entry in load_v2():
        if str(entry.get("二级朝代坐标") or "") != DYNASTY:
            continue
        cat = str(entry.get("史略分类") or "")
        if cat in SKIP_CATEGORIES:
            skipped["skip_junwang"] = skipped.get("skip_junwang", 0) + 1
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

    by_cat: dict[str, int] = {}
    for r in rows:
        if r.get("路径") != "translate":
            continue
        c = str(r.get("史略分类") or "")
        by_cat[c] = by_cat.get(c, 0) + 1

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": {
            "dynasty": DYNASTY,
            "exclude_categories": sorted(SKIP_CATEGORIES),
        },
        "policy": {
            "path": "translate skill → 11新标注条目翻译",
            "v1_04_policy": "04史料翻译仅留档，禁止 promote 至 11",
            "note": "西汉剩余批次（非君王）；不满足顺译条件的条目标记为 compose",
        },
        "entries": sort_rows(rows),
        "counts": {
            "translate": sum(1 for r in rows if r.get("路径") == "translate"),
            "compose": sum(1 for r in rows if r.get("路径") == "compose"),
            "translate_by_category": by_cat,
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
