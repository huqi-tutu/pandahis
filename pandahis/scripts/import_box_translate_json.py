#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将史略详情全量同步到 histomap.historical_box_detail。

数据源（合并 upsert，翻译优先保留史料原文）：
  - data/04史料翻译/史略翻译_汇总.json
  - data/06朝代知识补全/详情/朝代知识详情_汇总.json

字段映射：
  史略ID   -> box_id
  翻译详情 -> translate_detail
  史料原文 -> source_original_json（仅翻译流水线产出）

单条同步请用翻译编排器：
  python3 translate.py sync --id GLBL_00149
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JSON = ROOT / "data" / "04史料翻译" / "史略翻译_汇总.json"
DEFAULT_DYNASTY_JSON = (
    ROOT / "data" / "06朝代知识补全" / "详情" / "朝代知识详情_汇总.json"
)
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
    parser.add_argument(
        "--dynasty-json",
        type=Path,
        default=DEFAULT_DYNASTY_JSON,
        help="朝代知识补全详情汇总（免翻译条目）",
    )
    parser.add_argument(
        "--translate-only",
        action="store_true",
        help="仅同步翻译汇总，不包含朝代知识补全",
    )
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
    from lib.remote_sync import sync_all_box_details  # noqa: E402

    dynasty_json = None if args.translate_only else args.dynasty_json
    ok, msg = sync_all_box_details(
        translate_json=args.json,
        dynasty_detail_json=dynasty_json,
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
