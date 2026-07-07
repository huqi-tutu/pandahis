#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将 data/04史料翻译/史略翻译_汇总.json 全量同步到 histomap.historical_box_detail。

字段映射：
  史略ID   -> box_id
  翻译详情 -> translate_detail
  史料原文 -> source_original_json

单条同步请用翻译编排器：
  python3 translate.py sync --id GLBL_00149
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JSON = ROOT / "data" / "04史料翻译" / "史略翻译_汇总.json"
TRANSLATE_DIR = ROOT / "tools" / "openclaw-historiography" / "historiography-translate"


def _load_env() -> None:
    env_file = ROOT / "tools" / "openclaw-historiography" / ".env"
    if not env_file.is_file():
        return
    import os

    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--mysql-host", default=None)
    parser.add_argument("--mysql-port", type=int, default=None)
    parser.add_argument("--mysql-user", default=None)
    parser.add_argument("--mysql-password", default=None)
    parser.add_argument("--mysql-db", default=None)
    args = parser.parse_args()

    _load_env()
    import os

    if args.mysql_host:
        os.environ["MYSQL_HOST"] = args.mysql_host
    if args.mysql_port:
        os.environ["MYSQL_PORT"] = str(args.mysql_port)
    if args.mysql_user:
        os.environ["MYSQL_USER"] = args.mysql_user
    if args.mysql_password:
        os.environ["MYSQL_PASSWORD"] = args.mysql_password
    if args.mysql_db:
        os.environ["MYSQL_DB"] = args.mysql_db

    sys.path.insert(0, str(TRANSLATE_DIR))
    from lib.remote_sync import sync_all_from_aggregate  # noqa: E402

    ok, msg = sync_all_from_aggregate(
        args.json,
        dry_run=args.dry_run,
        prune_orphans=True,
    )
    if ok:
        print(f"完成: {msg}")
        return 0
    print(f"失败: {msg}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
