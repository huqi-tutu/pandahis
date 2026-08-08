#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按 V2 详情策略重建顺译 / compose 队列。"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "data" / "05工作流中间产物"
sys.path.insert(0, str(ROOT / "scripts"))

from v2_detail_routing import build_queues  # noqa: E402

OUT = {
    "policy": WORK / "v2_detail_policy.json",
    "translate": WORK / "v2_translate_queue.json",
    "compose": WORK / "v2_compose_queue.json",
    "report": WORK / "v2_detail_queues_report.json",
}


def main() -> int:
    data = build_queues()
    data["generated_at"] = datetime.now(timezone.utc).isoformat()
    for key, path in OUT.items():
        if key == "report":
            continue
        payload = data["policy"] if key == "policy" else data[key]
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # 废弃 promote 队列（若存在则写空并标注）
    deprecated = WORK / "v2_promote_04_queue.json"
    deprecated.write_text(
        json.dumps(
            {
                "deprecated": True,
                "reason": "V1 04 顺译不复用，须 translate skill 重译至 11",
                "entries": [],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    report = {
        "generated_at": data["generated_at"],
        "counts": data["counts"],
        "skipped": data["skipped"],
        "files": {k: str(v) for k, v in OUT.items()},
        "deprecated_promote_queue": str(deprecated),
    }
    OUT["report"].write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
