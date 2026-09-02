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
  python3 translate.py promote --id GLBL_00001 [--sync] [--version v7] [--note "..."]
  python3 translate.py sync --id GLBL_00001
  python3 translate.py patch-paragraphs --id GLBL_00730 --source-only
  # 产出默认写入 待补全段落翻译/_patch_output/，基稿不动，待人工确认后再 promote
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
    p.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="产出目录（V2 索引默认 11新标注条目翻译）",
    )
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--recall-only", action="store_true")
    p.add_argument("--no-llm", action="store_true")

    p = sub.add_parser("run-one", help="跑单条")
    p.add_argument("--id", required=True, dest="entry_id")
    p.add_argument("--index", type=Path, default=None)
    p.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="产出目录（V2 索引默认 11新标注条目翻译）",
    )
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--recall-only", action="store_true")
    p.add_argument("--no-llm", action="store_true")
    p.add_argument(
        "--from-phase",
        dest="from_phase",
        default=None,
        choices=("phase_b", "phase_c", "phase_d", "phase2", "assemble", "batch"),
        help="续跑：assemble=终稿装配；batch=分批成稿；phase_b/c/d（ABCD）；phase2 等同 phase_d",
    )

    p = sub.add_parser("verify", help="质检产出 JSON")
    p.add_argument("--id", required=True, dest="entry_id")
    p.add_argument("--index", type=Path, default=None)
    p.add_argument("--output-dir", type=Path, default=None)

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

    p = sub.add_parser("promote", help="人工确认后 promote 至 11/_versions（与 sync 分离）")
    p.add_argument("--id", required=True, dest="entry_id")
    p.add_argument("--index", type=Path, default=None)
    p.add_argument("--output-dir", type=Path, default=None)
    p.add_argument("--version", default=None, help="指定版本号，如 v7")
    p.add_argument("--note", default="", help="版本说明")
    p.add_argument("--sync", action="store_true", help="promote 后立即同步线上")
    p.add_argument("--dry-run", action="store_true")

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
    p.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="产出目录（V2 默认 11新标注条目翻译）",
    )
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--execute", action="store_true", help="执行修复（默认仅展示工单）")

    p = sub.add_parser("patch-paragraphs", help="V1 成稿补译 V2 缺失母本段并落盘到 11 复用目录")
    p.add_argument("--id", required=True, dest="entry_id")
    p.add_argument("--index", type=Path, default=None, help="V2 索引（默认 10新标注条目/史略索引_史记汉书.json）")
    p.add_argument("--base", type=Path, default=None, help="V1 基稿 JSON（默认 11/待补全段落翻译/）")
    p.add_argument("--out-dir", type=Path, default=None, help="产出目录（默认 待补全段落翻译/_patch_output/）")
    p.add_argument("--manifest", type=Path, default=None, help="待补全清单.json")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force", action="store_true", help="跳过去重门控，强制 Phase1 顺译")
    p.add_argument(
        "--boundary-paras",
        type=int,
        default=None,
        help="integrate 模式替换的 V1 边界段数（默认按 patch_mode 自动：append/prepend=0）",
    )
    p.add_argument("--source-only", action="store_true", help="仅补全史料原文，不改翻译详情（如赵简子）")

    p = sub.add_parser("patch-promote", help="人工确认后将 _patch_output 产出 promote 至 11 第一层并清理待补全")
    p.add_argument("--id", required=True, dest="entry_id")
    p.add_argument("--from", dest="patch_file", type=Path, default=None, help="指定产出 JSON（默认 _patch_output/）")
    p.add_argument("--note", default="", help="写入复用清单的备注")

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
            output_dir=getattr(args, "output_dir", None),
            dry_run=args.dry_run,
            recall_only=args.recall_only,
            use_llm=not args.no_llm,
            from_phase=getattr(args, "from_phase", None),
        )

    if args.cmd == "verify":
        return runner.verify_cmd(
            args.entry_id,
            index_path=index,
            output_dir=getattr(args, "output_dir", None),
        )

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

    if args.cmd == "promote":
        index = args.index if hasattr(args, "index") else None
        return runner.promote_cmd(
            args.entry_id,
            index_path=index,
            output_dir=getattr(args, "output_dir", None),
            version=getattr(args, "version", None),
            note=getattr(args, "note", "") or "",
            sync=getattr(args, "sync", False),
            dry_run=getattr(args, "dry_run", False),
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
        from lib.config import paths, resolve_output_dir
        from lib.repair_executor import execute_repair, print_repair_status

        index = args.index if hasattr(args, "index") else None
        out_dir = resolve_output_dir(
            index_path=index,
            output_dir=getattr(args, "output_dir", None),
        )
        if not args.execute:
            return print_repair_status(paths()["translate_work"], args.entry_id)
        ok, msg = execute_repair(
            args.entry_id,
            work_dir=paths()["translate_work"],
            out_dir=out_dir,
            index_path=index,
            dry_run=args.dry_run,
        )
        print(msg)
        return 0 if ok else 1

    if args.cmd == "patch-paragraphs":
        from lib.patch_paragraphs import patch_paragraphs, promote_source_only

        index = args.index if hasattr(args, "index") else None
        if args.source_only:
            ok, msg = promote_source_only(
                args.entry_id,
                base_file=args.base,
                output_dir=args.out_dir,
                index_path=index,
            )
        else:
            ok, msg = patch_paragraphs(
                args.entry_id,
                base_file=args.base,
                output_dir=args.out_dir,
                manifest_path=args.manifest,
                index_path=index,
                dry_run=args.dry_run,
                force=args.force,
                boundary_paras=args.boundary_paras,
            )
        print(msg)
        return 0 if ok else 1

    if args.cmd == "patch-promote":
        from lib.patch_paragraphs import promote_patched_entry

        ok, msg = promote_patched_entry(
            args.entry_id,
            patch_file=getattr(args, "patch_file", None),
            note=getattr(args, "note", "") or "",
        )
        print(msg)
        return 0 if ok else 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
