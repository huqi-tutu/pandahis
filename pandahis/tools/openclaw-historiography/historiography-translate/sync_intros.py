#!/usr/bin/env python3
"""将已补引入的五帝译文同步到线上数据库。

用法:
  python3 sync_intros.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lib"))

from lib.remote_sync import sync_output_entry

TRANS_DIR = Path(
    __file__).resolve().parent.parent.parent.parent / "data/04史料翻译"

ENTRIES = [
    ("GLBL_00149", "黄帝"),
    ("GLBL_00144", "颛顼"),
    ("GLBL_00057", "帝喾"),
]

def main():
    print("=" * 50)
    print("五帝史略 — 前置引入 同步线上数据库")
    print("=" * 50)

    for eid, ename in ENTRIES:
        print(f"\n▶ {ename} ({eid}) ...", end=" ", flush=True)
        try:
            ok, msg = sync_output_entry(eid, TRANS_DIR, ename)
            if ok:
                print(f"✅ {msg}")
            else:
                print(f"❌ {msg}")
        except Exception as e:
            print(f"❌ {e}")

    print(f"\n{'=' * 50}")
    print("完成。")
    print(f"{'=' * 50}")

if __name__ == "__main__":
    main()
