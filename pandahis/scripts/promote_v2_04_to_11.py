#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""已废弃：V1 04 顺译不复用。请用 run_v2_translate_queue.py 重译至 11。"""

from __future__ import annotations

import sys


def main() -> int:
    print(
        "❌ 已废弃：V1 04 顺译不复用至 11，请使用 run_v2_translate_queue.py 重译",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
