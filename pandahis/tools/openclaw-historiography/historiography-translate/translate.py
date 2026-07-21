#!/usr/bin/env python3
"""
全局史略翻译编排器（translate）

用法:
  python3 translate.py init [--index PATH]
  python3 translate.py recall --id GLBL_00001
  python3 translate.py run --from GLBL_00001 --max 1 [--priority P0] [--single-source-only]
  python3 translate.py run-one --id GLBL_00001 [--from-phase phase2] [--dry-run]
  python3 translate.py repair --id GLBL_00001 [--execute] [--dry-run]
  python3 translate.py repair-show --id GLBL_00001
  python3 translate.py verify --id GLBL_00001
  python3 translate.py aggregate
  python3 translate.py status
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from lib import db  # noqa: E402
from lib.config import default_index_path, load_dotenv  # noqa: E402
from lib import runner  # noqa: E402


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="全局史略翻译编排")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="从全局索引 bootstrap 任务")
    p.add_argument("--index", type=Path, default=None)
    p.add_argument("--force", action="store_true", help="重置为 pending（不删产出）")

    p = sub.add_parser("recall", help="召回原文预览")
    p.add_argument("--id", required=True, dest="entry_id")
    p.add_argument("--index", type=Path, default=None)

    p = sub.add_parser("run", help="批量跑 pending 任务")
    p.add_argument("--from", dest="from_id", default=None)
    p.add_argument("--max", type=int, default=1)
    p.add_argument("--priority", default=None)
    p.add_argument("--dynasty", default=None, help="按二级朝代/三级政权坐标筛选，如 五帝")
    p.add_argument("--retry-failed", action="store_true", help="先重置 failed 为 pending 再跑")
    p.add_argument("--single-source-only", action="store_true")
    p.add_argument("--index", type=Path, default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--recall-only", action="store_true")
    p.add_argument("--no-llm", action="store_true")

    p = sub.add_parser("run-one", help="跑单条")
    p.add_argument("--id", required=True, dest="entry_id")
    p.add_argument("--index", type=Path, default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--recall-only", action="store_true")
    p.add_argument("--no-llm", action="store_true")
    p.add_argument(
        "--from-phase",
        dest="from_phase",
        default=None,
        choices=("phase2",),
        help="从指定阶段续跑（需已有中间产物）",
    )

    p = sub.add_parser("verify", help="质检产出 JSON")
    p.add_argument("--id", required=True, dest="entry_id")
    p.add_argument("--index", type=Path, default=None)

    sub.add_parser("status", help="查看进度")

    sub.add_parser("aggregate", help="重建史略翻译_汇总.json")

    p = sub.add_parser("watch", help="检测翻译是否卡顿并诊断")
    p.add_argument("--id", required=True, dest="entry_id")
    p.add_argument("--index", type=Path, default=None)

    p = sub.add_parser("sync", help="同步翻译到线上 historical_box_detail")
    p.add_argument("--id", dest="entry_id", default=None, help="同步单条产出")
    p.add_argument("--all", dest="sync_all", action="store_true", help="从汇总 JSON 全量同步")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--index", type=Path, default=None)

    p = sub.add_parser("retry", help="将 failed 任务重置为 pending（无成稿者）")
    p.add_argument("--dynasty", default=None)
    p.add_argument("--priority", default=None)
    p.add_argument("--index", type=Path, default=None)

    p = sub.add_parser("refine", help="局部更新已产出译稿（不全量重写）")
    p.add_argument("--id", required=True, dest="entry_id")
    p.add_argument(
        "--scope",
        default="full",
        choices=("intro", "mother", "tail", "full", "attribution"),
        help="attribution=规则清洗；其余 scope 走 LLM",
    )
    p.add_argument("--instructions", default="", help="用户修改意见")
    p.add_argument("--index", type=Path, default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-llm", action="store_true", help="仅 attribution scope 可用")

    p = sub.add_parser("repair-show", help="查看修复工单（质检失败产物）")
    p.add_argument("--id", required=True, dest="entry_id")

    p = sub.add_parser("repair", help="按工单定向修复（非盲重跑）")
    p.add_argument("--id", required=True, dest="entry_id")
    p.add_argument("--index", type=Path, default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--execute", action="store_true", help="执行修复（默认仅展示工单）")

    args = parser.parse_args()
    index = args.index if hasattr(args, "index") else None

    if args.cmd == "init":
        db.init_schema()
        return 0 if runner.bootstrap(index_path=index or default_index_path(), force=args.force) else 1

    if args.cmd == "recall":
        runner.cmd_recall(args.entry_id, index_path=index)
        return 0

    if args.cmd == "run":
        return runner.run_batch(
            max_jobs=args.max,
            from_id=args.from_id,
            priority=args.priority,
            dynasty=args.dynasty,
            retry_failed=args.retry_failed,
            single_source_only=args.single_source_only,
            index_path=index,
            dry_run=args.dry_run,
            recall_only=args.recall_only,
            use_llm=not args.no_llm,
        )

    if args.cmd == "run-one":
        return runner.run_one(
            args.entry_id,
            index_path=index,
            dry_run=args.dry_run,
            recall_only=args.recall_only,
            use_llm=not args.no_llm,
            from_phase=getattr(args, "from_phase", None),
        )

    if args.cmd == "verify":
        return runner.verify_cmd(args.entry_id, index_path=index)

    if args.cmd == "status":
        return runner.print_status()

    if args.cmd == "aggregate":
        return runner.aggregate_cmd()

    if args.cmd == "watch":
        index = args.index if hasattr(args, "index") else None
        return runner.watch_cmd(args.entry_id, index_path=index)

    if args.cmd == "sync":
        index = args.index if hasattr(args, "index") else None
        return runner.sync_cmd(
            args.entry_id,
            all_from_aggregate=args.sync_all,
            dry_run=args.dry_run,
            index_path=index,
        )

    if args.cmd == "retry":
        index = args.index if hasattr(args, "index") else None
        return runner.retry_failed_cmd(
            dynasty=args.dynasty,
            priority=args.priority,
            index_path=index,
        )

    if args.cmd == "refine":
        from lib.refine import refine_entry

        index = args.index if hasattr(args, "index") else None
        ok, msg = refine_entry(
            args.entry_id,
            scope=args.scope,
            instructions=args.instructions,
            index_path=index,
            dry_run=args.dry_run,
            use_llm=not args.no_llm,
        )
        print(msg)
        return 0 if ok else 1

    if args.cmd == "repair-show":
        from lib.config import paths
        from lib.repair_executor import print_repair_status

        return print_repair_status(paths()["translate_work"], args.entry_id)

    if args.cmd == "repair":
        from lib.config import paths
        from lib.repair_executor import execute_repair, print_repair_status

        index = args.index if hasattr(args, "index") else None
        if not args.execute:
            return print_repair_status(paths()["translate_work"], args.entry_id)
        ok, msg = execute_repair(
            args.entry_id,
            work_dir=paths()["translate_work"],
            out_dir=paths()["translate_output"],
            index_path=index,
            dry_run=args.dry_run,
        )
        print(msg)
        return 0 if ok else 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
