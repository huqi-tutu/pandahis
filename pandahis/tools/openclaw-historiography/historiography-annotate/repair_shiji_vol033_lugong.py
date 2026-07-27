#!/usr/bin/env python3
"""已废弃：请使用 repair_shiji_jiashi_batch.py 033（统一世家专则）。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    script = Path(__file__).resolve().parent / "repair_shiji_jiashi_batch.py"
    raise SystemExit(
        subprocess.call(
            [sys.executable, str(script), "033"],
            env={**dict(__import__("os").environ), "HIST_REPAIR": "1"},
        )
    )
