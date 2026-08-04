#!/usr/bin/env python3
"""
朝代史略流水线编排器

Phase 1: status — 按朝代展示 S1–P2 进度，写入 progress.json / progress.md
Phase 2: gate / run — 串行门禁 + 步骤执行

用法:
  python3 scripts/dynasty_pipeline.py status
  python3 scripts/dynasty_pipeline.py status --dynasty 春秋
  python3 scripts/dynasty_pipeline.py gate --dynasty 战国 --step S3
  python3 scripts/dynasty_pipeline.py run --dynasty 春秋 --next
  python3 scripts/dynasty_pipeline.py run --dynasty 秦 --through S5
  python3 scripts/dynasty_pipeline.py run --dynasty 西周 --parallel
  python3 scripts/dynasty_pipeline.py run --dynasty 春秋 --step S3 --background
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import pipeline_lib as pl  # noqa: E402


def cmd_status(args: argparse.Namespace) -> int:
    dynasties = (args.dynasty,) if args.dynasty else pl.DEFAULT_DYNASTIES
    report = pl.compute_all_progress(dynasties)
    path = pl.save_progress(report) if not args.no_save else None

    print("=" * 72)
    print("朝代史略流水线进度")
    print("=" * 72)
    print(f"更新: {report['updated_at']}")
    if path:
        print(f"快照: {path}")
        print(f"Markdown: {pl.PROGRESS_MD}")
    print()

    header = (
        f"{'朝代':<6} {'ext':>4}  {'S6':<8} {'P1 CW':<16} {'P2关系':<14} "
        f"{'K补全':<8} {'K3fill':<12} {'K5merge':<12} 当前"
    )
    print(header)
    print("-" * 90)

    def icon(status: str) -> str:
        return {"done": "✅", "blocked": "❌", "locked": "🔒", "running": "⏳", "pending": "⬜"}.get(status, "?")

    for name in dynasties:
        m = report["dynasties"][name]

        def c(step: str, width: int = 12) -> str:
            s = m[step]
            return f"{icon(s['status'])}{s['count']}".ljust(width)

        k_sum = "—"
        if m.get("knowledge_active"):
            k_sum = f"{m.get('knowledge_filled', 0)}/{m.get('knowledge_expected', 0)}"

        print(
            f"{name:<6} {m.get('global_count', m['total']):>4}  "
            f"{c('S6', 8)} {c('P1', 16)} {c('P2', 14)} "
            f"{k_sum:<8} {c('K3')} {c('K5')} {m.get('current_step')}"
        )

    print()
    print("说明: F1 须 extract(S1–P2) 与知识补全(K1–K6) 双线均完成。")
    print()
    for name in dynasties:
        blockers = report["dynasties"][name].get("blockers") or []
        if blockers:
            print(f"【{name}】阻塞: {'; '.join(blockers[:4])}{'…' if len(blockers)>4 else ''}")
    return 0


def cmd_gate(args: argparse.Namespace) -> int:
    report = pl.compute_all_progress((args.dynasty,))
    ok, blockers = pl.gate_check(args.dynasty, args.step, report)
    m = report["dynasties"][args.dynasty][args.step]
    label = pl.STEP_LABELS.get(args.step, args.step)
    if ok:
        print(f"✅ {args.dynasty} {args.step}({label}) 通过 — {m['count']}")
        return 0
    print(f"❌ {args.dynasty} {args.step}({label}) 未通过")
    for b in blockers or m.get("blockers", []):
        print(f"  - {b}")
    return 1


def cmd_run(args: argparse.Namespace) -> int:
    kwargs = {"dry_run": args.dry_run, "background": args.background, "force": args.force}
    if args.parallel:
        code = pl.run_parallel(args.dynasty, **kwargs)
    elif args.next:
        code = pl.run_next(args.dynasty, **kwargs)
    elif args.through:
        code = pl.run_through(args.dynasty, args.through, **kwargs)
    elif args.step:
        code = pl.run_step(args.dynasty, args.step, **kwargs)
    else:
        print("请指定 --next / --through / --step / --parallel")
        return 1
    pl.save_progress(pl.compute_all_progress())
    return code


def main() -> int:
    parser = argparse.ArgumentParser(description="朝代史略流水线编排器")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_status = sub.add_parser("status", help="展示各朝代进度并写入 progress.json")
    p_status.add_argument("--dynasty", default=None)
    p_status.add_argument("--no-save", action="store_true", help="不写 progress.json")

    p_gate = sub.add_parser("gate", help="检查某步是否通过")
    p_gate.add_argument("--dynasty", required=True)
    p_gate.add_argument("--step", required=True, choices=pl.ALL_STEPS)

    p_run = sub.add_parser("run", help="执行流水线步骤")
    p_run.add_argument("--dynasty", required=True)
    g = p_run.add_mutually_exclusive_group(required=True)
    g.add_argument("--next", action="store_true", help="运行下一个未完成串行步骤")
    g.add_argument("--through", metavar="Sx", help="串行执行直到指定步骤")
    g.add_argument("--step", choices=pl.ALL_STEPS, help="运行指定步骤")
    g.add_argument("--parallel", action="store_true", help="S6 后并行 P1+P2")
    p_run.add_argument("--dry-run", action="store_true")
    p_run.add_argument("--background", action="store_true", help="适合 LLM 长任务")
    p_run.add_argument("--force", action="store_true", help="跳过门禁（慎用）")

    args = parser.parse_args()
    if args.cmd == "status":
        return cmd_status(args)
    if args.cmd == "gate":
        return cmd_gate(args)
    return cmd_run(args)


if __name__ == "__main__":
    raise SystemExit(main())
