#!/usr/bin/env python3
"""
评述 / 见证补全编排器（固定 DeepSeek v4 Pro）

用法:
  python3 cw.py test-llm
  python3 cw.py commentary-one --id GLBL_00129 [--dry-run]
  python3 cw.py witness-one --name 舜
  python3 cw.py commentary --dynasty 五帝 --max 3
  python3 cw.py witness --dynasty 五帝 --max 3
  python3 cw.py verify-commentary --id GLBL_00129
  python3 cw.py verify-witness --file path/to.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import cw_lib as cw  # noqa: E402
from verify_cw import verify_file  # noqa: E402


def _resolve_path(mode: str, args: argparse.Namespace) -> Path:
    if getattr(args, "file", None):
        return Path(args.file)
    entry = cw.find_entry(entry_id=args.entry_id, name=args.name, index_path=args.index)
    return cw.output_path(mode, entry)  # type: ignore[arg-type]


def main() -> int:
    parser = argparse.ArgumentParser(description="评述/见证补全（DeepSeek v4 Pro）")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("test-llm", help="测试 DeepSeek v4 Pro 连通")

    for mode_cmd, help_one in (
        ("commentary-one", "补全单条史略评述"),
        ("witness-one", "补全单条史略见证文物"),
    ):
        p = sub.add_parser(mode_cmd, help=help_one)
        p.add_argument("--id", dest="entry_id", default=None)
        p.add_argument("--name", default=None)
        p.add_argument("--index", type=Path, default=None)
        p.add_argument("--dry-run", action="store_true")
        p.add_argument("--no-revise", action="store_true")

    for mode_cmd, help_batch in (
        ("commentary", "按朝代批量评述（逐条串行）"),
        ("witness", "按朝代批量见证（逐条串行）"),
    ):
        p = sub.add_parser(mode_cmd, help=help_batch)
        p.add_argument("--dynasty", required=True)
        p.add_argument("--max", type=int, default=1)
        p.add_argument("--index", type=Path, default=None)
        p.add_argument("--dry-run", action="store_true")

    for vcmd, mode in (
        ("verify-commentary", "commentary"),
        ("verify-witness", "witness"),
    ):
        p = sub.add_parser(vcmd, help=f"校验 {mode} JSON")
        p.add_argument("--id", dest="entry_id", default=None)
        p.add_argument("--name", default=None)
        p.add_argument("--file", type=Path, default=None)
        p.add_argument("--index", type=Path, default=None)
        p.add_argument("--strict", action="store_true", default=True)
        p.add_argument("--no-strict", action="store_true")

    args = parser.parse_args()

    if args.cmd == "test-llm":
        label = cw.ensure_deepseek_v4_pro()
        reply = cw.call_llm("只回复：ok", session_prefix="cw-ping-")
        print(f"✅ {label}")
        print(reply[:200])
        return 0

    if args.cmd in ("commentary-one", "witness-one"):
        mode = "commentary" if args.cmd.startswith("commentary") else "witness"
        if not args.entry_id and not args.name:
            print("须提供 --id 或 --name", file=sys.stderr)
            return 2
        result = cw.compose_one(
            mode,  # type: ignore[arg-type]
            entry_id=args.entry_id,
            name=args.name,
            index_path=args.index,
            dry_run=args.dry_run,
            revise=not args.no_revise,
        )
        if args.dry_run:
            print(result["prompt"])
            return 0
        print(json.dumps({k: v for k, v in result.items() if k != "issues"}, ensure_ascii=False, indent=2))
        warns = [i for i in result.get("issues") or [] if i["level"] != "CRITICAL"]
        for w in warns:
            print(f"WARN: {w['msg']}", file=sys.stderr)
        return 0

    if args.cmd in ("commentary", "witness"):
        mode = "commentary" if args.cmd == "commentary" else "witness"
        results = cw.compose_dynasty(
            mode,  # type: ignore[arg-type]
            args.dynasty,
            max_n=args.max,
            index_path=args.index,
            dry_run=args.dry_run,
        )
        if args.dry_run and results:
            print(results[0].get("prompt", ""))
            return 0
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0

    if args.cmd in ("verify-commentary", "verify-witness"):
        mode = "commentary" if "commentary" in args.cmd else "witness"
        path = _resolve_path(mode, args)
        if not path.is_file():
            print(f"文件不存在: {path}", file=sys.stderr)
            return 2
        issues = verify_file(path, mode=mode, strict=not args.no_strict)  # type: ignore[arg-type]
        for it in issues:
            print(f"{it['level']}: {it['msg']}")
        critical = [i for i in issues if i["level"] == "CRITICAL"]
        if critical:
            print(f"\n⛔ {len(critical)} CRITICAL")
            return 1
        print(f"\n✅ verify OK（{path.name}）")
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
