#!/usr/bin/env python3
"""方案 A：《汉书》042–119 全量重置（skeleton + protagonists + blocks + jobs）后按新工作流重跑。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ORCH = Path(__file__).resolve().parents[1]
WORK = "02汉书"
VOL_FROM, VOL_TO = 42, 119


def main() -> int:
    vols = [f"{v:03d}" for v in range(VOL_FROM, VOL_TO + 1)]
    cmd = [
        sys.executable,
        str(ORCH / "scripts" / "reset_volumes.py"),
        "--work",
        WORK,
        "--purge-intermediates",
        *sum([["--vol", v] for v in vols], []),
    ]
    print(f"方案 A：重置 {WORK} 卷 {VOL_FROM:03d}–{VOL_TO:03d}（共 {len(vols)} 卷）")
    print("  · 删除 skeleton / protagonists / blocks")
    print("  · progress + jobs → pending")
    proc = subprocess.run(cmd, cwd=str(ORCH))
    if proc.returncode != 0:
        return proc.returncode
    print(f"\n✅ 方案 A 重置完成。下一步:")
    print(f"   python hist.py resume --work {WORK}")
    print(f"   python scripts/overnight_run_hanshu.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
