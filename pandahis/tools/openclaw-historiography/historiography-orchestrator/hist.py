#!/usr/bin/env python3
"""
史料标注著作级编排器（hist）

用法:
  python3 hist.py bootstrap --work 01A尚书
  python3 hist.py run-work --work 01A尚书 [--max-jobs N]
  python3 hist.py run-batch [--work 01史记] [--loop]
  python3 hist.py status [--work 01A尚书]
  python3 hist.py approve-gold --work 01A尚书
  python3 hist.py approve-work --work 01A尚书
  python3 hist.py reset-work --work 01A尚书
  python3 hist.py resume --work 01A尚书
  python3 hist.py audit-volumes --work 01A尚书
  python3 hist.py rebuild-audits --work 01史记 [--vol 001,002]
  python3 hist.py doctor
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ORCH_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ORCH_ROOT))

from lib import db  # noqa: E402
from lib.config import get_work_config, paths, queue_order  # noqa: E402
from lib.paragraph_index import bootstrap_indexes, list_volume_files  # noqa: E402
from lib import doctor  # noqa: E402
from lib import work_runner  # noqa: E402
from lib import batch_runner  # noqa: E402
from lib import audit_volumes  # noqa: E402


def cmd_bootstrap(work: str) -> int:
    vols = work_runner.bootstrap(work)
    print(f"✅ bootstrap 完成: {work}，{len(vols)} 卷")
    print(f"   段落索引: {paths()['paragraph_index']}")
    print(f"   状态库: {paths()['state_db']}")
    w = db.get_work(work)
    if w and w["status"] == "gold_review":
        print(f"   下一步: hist run-work --work {work}  （金标卷）")
        print(f"           然后 hist approve-gold --work {work}")
    else:
        print(f"   下一步: hist run-work --work {work}")
    return 0


def cmd_run_work(work: str, max_jobs: int | None, one_volume: bool) -> int:
    return work_runner.run_work(work, max_jobs=max_jobs, one_volume=one_volume)


def cmd_run_batch(
    work: str | None,
    max_jobs: int | None,
    loop: bool,
    sleep_sec: int,
) -> int:
    works = [work] if work else None
    print(batch_runner.format_batch_status(works), flush=True)
    return batch_runner.run_batch(
        works,
        max_jobs=max_jobs,
        loop=loop,
        sleep_sec=sleep_sec,
    )


def cmd_status(work: str | None) -> int:
    db.init_schema()
    if work:
        w = db.get_work(work)
        if not w:
            print(f"⚠️ 未 bootstrap: {work}")
            return 1
        pending = db.count_jobs(work, "pending")
        done = db.count_jobs(work, "done")
        failed = db.count_jobs(work, "failed")
        total = pending + done + failed
        print(f"\n📋 {work} ({w.get('title')})")
        print(f"   状态: {w['status']}")
        print(f"   金标: {'✓' if w.get('gold_approved') else '·'}  封板: {'✓' if w.get('work_approved') else '·'}")
        print(f"   jobs: done {done}/{total}  pending {pending}  failed {failed}")
        blocked = db.count_blocked_pending_jobs(work)
        if blocked:
            print(f"   门禁等待: {blocked} 个 pending（前序 step 未 done）")
        if w.get("current_vol"):
            print(f"   当前: 卷{w['current_vol']} Step{w.get('current_step')}")
        if w.get("blocked_reason"):
            print(f"   阻塞: {w['blocked_reason']}")
        if w["status"] == "awaiting_decision":
            print(f"   在终端 hist run-work --work {work} 将弹出选项")
        if w["status"] == "gold_review" and not w.get("gold_approved"):
            print(f"   金标待确认：hist run-work --work {work} 将弹出通过/暂停选项")
        if w["status"] == "work_review" and not w.get("work_approved"):
            print(f"   封板待确认：hist run-work --work {work} 将弹出封板/暂停选项")
        return 0

    print("\n📚 著作队列")
    for wid in queue_order():
        w = db.get_work(wid)
        if w:
            d = db.count_jobs(wid, "done")
            t = db.count_jobs(wid)
            print(f"   {wid:10s} {w['status']:14s} jobs {d}/{t}")
        else:
            print(f"   {wid:10s} (未 bootstrap)")
    return 0


def cmd_approve_gold(work: str) -> int:
    work_runner.approve_gold(work)
    return 0


def cmd_approve_work(work: str) -> int:
    work_runner.approve_work(work)
    return 0


def cmd_reset_work(work: str) -> int:
    work_runner.reset_work(work)
    return 0


def cmd_resume(work: str) -> int:
    work_runner.resume(work)
    return 0


def cmd_decide(work: str, vol: str, choice: str, continue_run: bool) -> int:
    return work_runner.decide(work, vol, choice, continue_run=continue_run)


def cmd_audit_volumes(work: str) -> int:
    return audit_volumes.run_audit(work)


def cmd_rebuild_audits(work: str, vols: list[str] | None) -> int:
    from lib.blocks_workflow import rebuild_audit_blocks

    logs = rebuild_audit_blocks(work, vols)
    for ln in logs:
        print(ln)
    audit_path = paths()["audit"] / f"{work}_标注审计.md"
    print(f"✅ 审计 MD: {audit_path}")
    return 0


def cmd_doctor() -> int:
    return doctor.run_doctor()


def cmd_index_preview(work: str, vol: str) -> int:
    from lib import gates

    idx = gates.load_paragraph_index(work, vol.zfill(3))
    print(f"{work} 卷{vol}: {idx['total']} 段  文件={idx['source_file']}")
    for p in idx["paragraphs"][:5]:
        t = p["text"][:60] + ("…" if len(p["text"]) > 60 else "")
        print(f"  [{p['id']:02d}] {t}")
    if idx["total"] > 5:
        print(f"  … 共 {idx['total']} 段")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="史料标注著作级编排 (hist)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("bootstrap", help="扫描卷、建段落索引、初始化队列")
    p.add_argument("--work", required=True)

    p = sub.add_parser("run-work", help="运行一本书（逐卷逐步）")
    p.add_argument("--work", required=True)
    p.add_argument(
        "--max-jobs",
        type=int,
        default=None,
        help="最多跑几个 job 后停（调试用；生产请用 --one-volume）",
    )
    p.add_argument(
        "--one-volume",
        action="store_true",
        help="仅跑一卷 Step1–4 后停止（禁止跨卷连跑；推荐生产默认）",
    )

    p = sub.add_parser("run-batch", help="按队列批量跑批（逐卷 LLM 不变）")
    p.add_argument("--work", default=None, help="仅跑一本书；默认跑 catalog 全书")
    p.add_argument("--max-jobs", type=int, default=None, help="每本书每轮最多 job 数（调试用）")
    p.add_argument(
        "--loop",
        action="store_true",
        help="遇暂停/失败时休眠后重试（配合 HIST_BATCH_AUTO）",
    )
    p.add_argument("--sleep", type=int, default=120, help="--loop 休眠秒数")

    p = sub.add_parser("status", help="查看进度")
    p.add_argument("--work", default=None)

    p = sub.add_parser("approve-gold", help="金标卷确认通过")
    p.add_argument("--work", required=True)

    p = sub.add_parser("approve-work", help="全书封板 + merge")
    p.add_argument("--work", required=True)

    p = sub.add_parser("reset-work", help="删除全书 skeleton、重置进度，从第一卷重标")
    p.add_argument("--work", required=True)

    p = sub.add_parser("resume", help="从 paused 恢复")
    p.add_argument("--work", required=True)

    p = sub.add_parser("decide", help="Step4 坐标冲突人工决策后继续")
    p.add_argument("--work", required=True)
    p.add_argument("--vol", required=True, help="卷号，如 068")
    p.add_argument(
        "--choice",
        required=True,
        choices=["emperor-ssot", "keep-current"],
        help="emperor-ssot=采用帝王表坐标; keep-current=保留当前",
    )
    p.add_argument(
        "--continue",
        dest="continue_run",
        action="store_true",
        help="决策后立即 run-work 一步",
    )

    p = sub.add_parser("index", help="预览段落索引")
    p.add_argument("--work", required=True)
    p.add_argument("--vol", required=True)

    sub.add_parser("doctor", help="检查 hist-worker 与 Gateway 是否可用")

    p = sub.add_parser("audit-volumes", help="扫描 skeleton Step4 字段缺失")
    p.add_argument("--work", required=True)

    p = sub.add_parser("rebuild-audits", help="从 skeleton 重建审计 MD（SSOT，去 LLM 废话）")
    p.add_argument("--work", required=True)
    p.add_argument("--vol", default=None, help="逗号分隔卷号，默认全部已有 skeleton")

    args = parser.parse_args()
    if args.cmd == "bootstrap":
        return cmd_bootstrap(args.work)
    if args.cmd == "run-work":
        return cmd_run_work(args.work, args.max_jobs, args.one_volume)
    if args.cmd == "run-batch":
        return cmd_run_batch(args.work, args.max_jobs, args.loop, args.sleep)
    if args.cmd == "status":
        return cmd_status(args.work)
    if args.cmd == "approve-gold":
        return cmd_approve_gold(args.work)
    if args.cmd == "approve-work":
        return cmd_approve_work(args.work)
    if args.cmd == "reset-work":
        return cmd_reset_work(args.work)
    if args.cmd == "resume":
        return cmd_resume(args.work)
    if args.cmd == "decide":
        return cmd_decide(args.work, args.vol, args.choice, args.continue_run)
    if args.cmd == "index":
        return cmd_index_preview(args.work, args.vol)
    if args.cmd == "doctor":
        return cmd_doctor()
    if args.cmd == "audit-volumes":
        return cmd_audit_volumes(args.work)
    if args.cmd == "rebuild-audits":
        vols = [v.strip() for v in args.vol.split(",")] if args.vol else None
        return cmd_rebuild_audits(args.work, vols)
    return 1


if __name__ == "__main__":
    sys.exit(main())
