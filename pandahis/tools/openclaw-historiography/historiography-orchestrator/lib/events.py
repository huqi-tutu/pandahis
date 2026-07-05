"""追加式审计日志 events.jsonl"""

from __future__ import annotations

import json
from typing import Any, Dict

from lib.config import paths
from lib.db import utc_now


def log(event: str, **fields: Any) -> None:
    fp = paths()["events"]
    fp.parent.mkdir(parents=True, exist_ok=True)
    row: Dict[str, Any] = {"ts": utc_now(), "event": event, **fields}
    with open(fp, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
