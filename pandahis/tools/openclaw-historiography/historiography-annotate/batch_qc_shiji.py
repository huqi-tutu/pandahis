#!/usr/bin/env python3
"""《史记》全卷批量质检：JSON 语法 + check_format + audit_precheck + 年份/坐标专项。

只读扫描，不修改 skeleton。产出 MD + JSON 报告。

用法:
  export HISTOGRAPH_ROOT=pandahis/pandahis   # 可选
  python3 batch_qc_shiji.py
  python3 batch_qc_shiji.py --vol-from 001 --vol-to 130
  python3 batch_qc_shiji.py --json-only
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SKILL = Path(__file__).resolve().parent
TOOL_ROOT = SKILL.parent
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))
if str(SKILL) not in sys.path:
    sys.path.insert(0, str(SKILL))

from paths_config import get_histograph_root, histograph_paths  # noqa: E402
from audit_shiji_031_089 import audit_volume  # noqa: E402
from coordinate_index import build_dynasty_index_from_json, build_regime_index  # noqa: E402
from emperor_resolve import build_emperor_info_index  # noqa: E402

WORK_ID = "01史记"
VOL_MAX = 130
# 表/志/书等按 annotate skill 可 skip 的卷号（无 skeleton 时不计失败）
SKIP_VOLUMES = {13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 25, 26, 27, 28, 29, 30}

Issue = Tuple[str, str, str]  # layer, severity, message


@dataclass
class VolumeQC:
    vol: str
    filename: Optional[str] = None
    status: str = "missing"  # ok | fail | missing | skip
    entry_count: int = 0
    json_ok: bool = False
    skeleton_ok: Optional[bool] = None
    final_ok: Optional[bool] = None
    precheck_ok: Optional[bool] = None
    year_audit_errors: int = 0
    year_audit_warns: int = 0
    issues: List[Issue] = field(default_factory=list)


def _env() -> dict:
    env = dict(os.environ)
    root = str(get_histograph_root())
    env["HISTOGRAPH_ROOT"] = env.get("HISTOGRAPH_ROOT", root)
    env["HIST_REPAIR"] = "1"
    return env


def _run_check_format(skeleton: Path, phase: str) -> Tuple[bool, List[str]]:
    cmd = [
        sys.executable,
        str(SKILL / "check_format.py"),
        str(skeleton),
        "--phase",
        phase,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, env=_env())
    out = (proc.stdout or "") + (proc.stderr or "")
    errs = [ln.strip() for ln in out.splitlines() if ln.strip().startswith("❌")]
    if proc.returncode != 0 and not errs:
        tail = out.strip().splitlines()
        errs = [tail[-1] if tail else f"exit {proc.returncode}"]
    return proc.returncode == 0, errs


def _run_precheck(skeleton: Path) -> Tuple[bool, List[str], List[str]]:
    audit_dir = SKILL.parent / "historiography-audit"
    cmd = [sys.executable, str(audit_dir / "audit_precheck.py"), str(skeleton), "--json"]
    proc = subprocess.run(cmd, capture_output=True, text=True, env=_env())
    warnings: List[str] = []
    errors: List[str] = []
    if proc.returncode == 0:
        try:
            # --json 混在 stdout 末尾
            raw = proc.stdout or ""
            idx = raw.rfind("{")
            if idx >= 0:
                report = json.loads(raw[idx:])
                errors = report.get("errors") or []
                warnings = report.get("warnings") or []
        except json.JSONDecodeError:
            pass
        return True, errors, warnings
    out = (proc.stdout or "") + (proc.stderr or "")
    errors = [ln.strip().lstrip("❌ ").strip() for ln in out.splitlines() if "❌" in ln]
    return False, errors, warnings


def _find_skeleton(ann_dir: Path, vol: str) -> Optional[Path]:
    matches = sorted(ann_dir.glob(f"{WORK_ID}_{vol}_*_skeleton.json"))
    return matches[0] if matches else None


def qc_volume(
    vol: str,
    ann_dir: Path,
    emperor_index: dict,
    regime_index: dict,
    dynasty_index: dict,
    *,
    run_year_audit: bool = True,
) -> VolumeQC:
    vol_n = int(vol)
    rec = VolumeQC(vol=vol)

    if vol_n in SKIP_VOLUMES:
        sk = _find_skeleton(ann_dir, vol)
        if sk is None:
            rec.status = "skip"
            rec.issues.append(("meta", "INFO", "表/志/书 skip 卷，无 skeleton 属预期"))
            return rec

    sk = _find_skeleton(ann_dir, vol)
    if sk is None:
        rec.status = "missing"
        rec.issues.append(("L0", "ERROR", "缺少 skeleton 文件"))
        return rec

    rec.filename = sk.name

    try:
        data = json.loads(sk.read_text(encoding="utf-8"))
        rec.json_ok = True
        rec.entry_count = len(data.get("entries") or [])
    except json.JSONDecodeError as e:
        rec.status = "fail"
        rec.issues.append(("L0", "ERROR", f"JSON 解析失败: {e}"))
        return rec

    sk_ok, sk_errs = _run_check_format(sk, "skeleton")
    rec.skeleton_ok = sk_ok
    for e in sk_errs:
        rec.issues.append(("L1-skeleton", "ERROR", e))

    fin_ok, fin_errs = _run_check_format(sk, "final")
    rec.final_ok = fin_ok
    for e in fin_errs:
        rec.issues.append(("L1-final", "ERROR", e))

    pc_ok, pc_errs, pc_warns = _run_precheck(sk)
    rec.precheck_ok = pc_ok
    for e in pc_errs:
        rec.issues.append(("L2-precheck", "ERROR", e))
    for w in pc_warns:
        rec.issues.append(("L2-precheck", "WARN", w))

    if run_year_audit:
        ya_issues = audit_volume(sk, emperor_index, regime_index, dynasty_index)
        for sev, eid, msg in ya_issues:
            layer = "L2-year"
            rec.issues.append((layer, sev, f"[{eid}] {msg}"))
            if sev == "ERROR":
                rec.year_audit_errors += 1
            else:
                rec.year_audit_warns += 1

    rec.status = "ok" if rec.json_ok and sk_ok and fin_ok and pc_ok and rec.year_audit_errors == 0 else "fail"
    return rec


def _summarize(records: List[VolumeQC]) -> Dict[str, Any]:
    by_status = defaultdict(int)
    layer_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in records:
        by_status[r.status] += 1
        for layer, sev, _ in r.issues:
            if sev in ("ERROR", "WARN"):
                layer_counts[layer][sev] += 1

    total_entries = sum(r.entry_count for r in records if r.filename)
    fail_vols = [r.vol for r in records if r.status == "fail"]
    missing_vols = [r.vol for r in records if r.status == "missing"]
    skip_vols = [r.vol for r in records if r.status == "skip"]

    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "work": WORK_ID,
        "vol_range": f"001-{VOL_MAX:03d}",
        "volume_counts": dict(by_status),
        "skeleton_files": sum(1 for r in records if r.filename),
        "total_entries": total_entries,
        "fail_volumes": fail_vols,
        "missing_volumes": missing_vols,
        "skip_volumes": skip_vols,
        "layer_issue_counts": {k: dict(v) for k, v in layer_counts.items()},
        "l1_skeleton_fail": sum(1 for r in records if r.skeleton_ok is False),
        "l1_final_fail": sum(1 for r in records if r.final_ok is False),
        "l2_precheck_fail": sum(1 for r in records if r.precheck_ok is False),
        "l2_year_error_volumes": sum(1 for r in records if r.year_audit_errors > 0),
    }


def _render_md(records: List[VolumeQC], summary: Dict[str, Any]) -> str:
    lines = [
        "# 《史记》全卷质检报告",
        "",
        f"- 生成时间：{summary['generated_at']}",
        f"- 扫描范围：卷 {summary['vol_range']}",
        f"- skeleton 文件：{summary['skeleton_files']} 卷",
        f"- 史略条目合计：{summary['total_entries']} 条",
        "",
        "## 汇总",
        "",
        "| 状态 | 卷数 |",
        "|------|------|",
    ]
    labels = {"ok": "✅ 通过", "fail": "❌ 有问题", "missing": "⚠️ 缺文件", "skip": "⏭ skip（表志书）"}
    for key in ("ok", "fail", "missing", "skip"):
        n = summary["volume_counts"].get(key, 0)
        if n:
            lines.append(f"| {labels.get(key, key)} | {n} |")

    lines.extend([
        "",
        "| 检查层 | 失败卷数 / 问题数 |",
        "|--------|------------------|",
        f"| L1 skeleton (check_format) | {summary['l1_skeleton_fail']} 卷失败 |",
        f"| L1 final (check_format) | {summary['l1_final_fail']} 卷失败 |",
        f"| L2 precheck | {summary['l2_precheck_fail']} 卷失败 |",
        f"| L2 年份/坐标专项 | {summary['l2_year_error_volumes']} 卷有 ERROR |",
        "",
    ])

    fail_recs = [r for r in records if r.status == "fail"]
    if fail_recs:
        lines.append("## 失败卷明细")
        lines.append("")
        for r in fail_recs:
            title = r.filename or f"卷{r.vol}"
            lines.append(f"### 卷 {r.vol} — {title}")
            lines.append("")
            lines.append(f"- 条目数：{r.entry_count}")
            flags = []
            if r.skeleton_ok is False:
                flags.append("skeleton ❌")
            if r.final_ok is False:
                flags.append("final ❌")
            if r.precheck_ok is False:
                flags.append("precheck ❌")
            if r.year_audit_errors:
                flags.append(f"年份 ERROR×{r.year_audit_errors}")
            if r.year_audit_warns:
                flags.append(f"年份 WARN×{r.year_audit_warns}")
            lines.append(f"- 检查：{', '.join(flags) or '—'}")
            lines.append("")
            errors = [(layer, msg) for layer, sev, msg in r.issues if sev == "ERROR"]
            if errors:
                lines.append("**错误：**")
                for layer, msg in errors[:20]:
                    lines.append(f"- `{layer}` {msg}")
                if len(errors) > 20:
                    lines.append(f"- … 另有 {len(errors) - 20} 条")
                lines.append("")

    warn_recs = [r for r in records if r.status == "ok" and any(s == "WARN" for _, s, _ in r.issues)]
    if warn_recs:
        lines.append("## 通过但有 WARN 的卷")
        lines.append("")
        for r in warn_recs[:15]:
            warns = [msg for _, sev, msg in r.issues if sev == "WARN"]
            lines.append(f"- **卷 {r.vol}**：{len(warns)} 条 WARN")
        if len(warn_recs) > 15:
            lines.append(f"- … 另有 {len(warn_recs) - 15} 卷")
        lines.append("")

    if summary.get("missing_volumes"):
        lines.append("## 缺失卷（非 skip）")
        lines.append("")
        lines.append(", ".join(summary["missing_volumes"]))
        lines.append("")

    lines.append("## 建议修复顺序")
    lines.append("")
    lines.append("1. **exclude 误标**（本纪世系链 / 太史公曰）：001–010 等")
    lines.append("2. **Step4 未完成**：024 乐书缺年份与坐标")
    lines.append("3. **年份 WARN**：批量占位、疑似帝王在位年替代生卒 → 逐条考订")
    lines.append("4. 修复后重跑：`HIST_REPAIR=1 python3 check_format.py <file> --phase final`")
    lines.append("")
    return "\n".join(lines)


def _records_to_json(records: List[VolumeQC], summary: Dict[str, Any]) -> dict:
    return {
        **summary,
        "volumes": [
            {
                "vol": r.vol,
                "filename": r.filename,
                "status": r.status,
                "entry_count": r.entry_count,
                "json_ok": r.json_ok,
                "skeleton_ok": r.skeleton_ok,
                "final_ok": r.final_ok,
                "precheck_ok": r.precheck_ok,
                "year_audit_errors": r.year_audit_errors,
                "year_audit_warns": r.year_audit_warns,
                "issues": [{"layer": a, "severity": b, "message": c} for a, b, c in r.issues],
            }
            for r in records
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="《史记》全卷批量质检")
    parser.add_argument("--vol-from", default="001", help="起始卷号")
    parser.add_argument("--vol-to", default=str(VOL_MAX), help="结束卷号")
    parser.add_argument("--no-year-audit", action="store_true", help="跳过年份/坐标专项")
    parser.add_argument("--json-only", action="store_true", help="只写 JSON，不写 MD")
    parser.add_argument("-o", "--output-dir", default=None, help="报告输出目录")
    args = parser.parse_args()

    paths = histograph_paths()
    ann_dir = paths["annotations"]
    out_dir = Path(args.output_dir) if args.output_dir else paths["annotate_work"]
    out_dir.mkdir(parents=True, exist_ok=True)

    vol_from = int(args.vol_from)
    vol_to = int(args.vol_to)

    print(f"🔍 《史记》批量质检 卷 {vol_from:03d}–{vol_to:03d}")
    print(f"   标注目录: {ann_dir}")
    print(f"   报告目录: {out_dir}")

    emperor_index = build_emperor_info_index()
    regime_index = build_regime_index()
    dynasty_index = build_dynasty_index_from_json()

    records: List[VolumeQC] = []
    for v in range(vol_from, vol_to + 1):
        vol = f"{v:03d}"
        print(f"   … 卷 {vol}", flush=True)
        rec = qc_volume(
            vol,
            ann_dir,
            emperor_index,
            regime_index,
            dynasty_index,
            run_year_audit=not args.no_year_audit,
        )
        records.append(rec)

    summary = _summarize(records)
    report_json = _records_to_json(records, summary)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"QC报告_史记_{ts}.json"
    md_path = out_dir / f"QC报告_史记_{ts}.md"
    latest_json = out_dir / "QC报告_史记_latest.json"
    latest_md = out_dir / "QC报告_史记_latest.md"

    json_path.write_text(json.dumps(report_json, ensure_ascii=False, indent=2), encoding="utf-8")
    latest_json.write_text(json.dumps(report_json, ensure_ascii=False, indent=2), encoding="utf-8")

    if not args.json_only:
        md_text = _render_md(records, summary)
        md_path.write_text(md_text, encoding="utf-8")
        latest_md.write_text(md_text, encoding="utf-8")

    print()
    print(f"✅ 完成：skeleton {summary['skeleton_files']} 卷，条目 {summary['total_entries']} 条")
    print(f"   通过 {summary['volume_counts'].get('ok', 0)} | "
          f"失败 {summary['volume_counts'].get('fail', 0)} | "
          f"缺失 {summary['volume_counts'].get('missing', 0)} | "
          f"skip {summary['volume_counts'].get('skip', 0)}")
    print(f"   L1 skeleton 失败: {summary['l1_skeleton_fail']}")
    print(f"   L1 final 失败: {summary['l1_final_fail']}")
    print(f"   报告: {json_path}")
    if not args.json_only:
        print(f"         {md_path}")

    return 1 if summary["volume_counts"].get("fail", 0) or summary["volume_counts"].get("missing", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
