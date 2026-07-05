#!/usr/bin/env python3
"""《汉书》全卷批量质检：结构硬门 + 预检 + 语义启发式 + 跨书对照。

只读扫描，不修改 skeleton。产出 MD + JSON 报告。

用法:
  cd historiography-annotate
  python3 batch_qc_hanshu.py
  python3 batch_qc_hanshu.py --vol-from 041 --vol-to 119
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

from audit_hanshu_volumes import audit_file  # noqa: E402
from coordinate_index import migrate_entry_fields, normalize_entry_category  # noqa: E402
from emperor_resolve import build_emperor_info_index  # noqa: E402
from hezhuan_attribution_gate import load_paragraph_text_map  # noqa: E402
from lib_config import owner_key, paths  # noqa: E402

WORK_ID = "02汉书"
VOL_MAX = 119
# 表/志/书：本次 scope 外，无 skeleton 属预期
SKIP_VOLUMES = set(range(14, 41))

Issue = Tuple[str, str, str]  # layer, severity, message


@dataclass
class VolumeQC:
    vol: str
    filename: Optional[str] = None
    status: str = "missing"
    entry_count: int = 0
    json_ok: bool = False
    skeleton_ok: Optional[bool] = None
    final_ok: Optional[bool] = None
    precheck_ok: Optional[bool] = None
    issues: List[Issue] = field(default_factory=list)


def _env() -> dict:
    env = dict(os.environ)
    env["HIST_REPAIR"] = "1"
    return env


def _run_check_format(skeleton: Path, phase: str) -> Tuple[bool, List[str]]:
    cmd = [sys.executable, str(SKILL / "check_format.py"), str(skeleton), "--phase", phase]
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
    errors: List[str] = []
    warnings: List[str] = []
    if proc.returncode == 0:
        raw = proc.stdout or ""
        idx = raw.rfind("{")
        if idx >= 0:
            try:
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


def _semantic_checks(data: dict, sk: Path, zj_map: Dict[str, str]) -> List[Issue]:
    out: List[Issue] = []
    vol = sk.name.split("_")[1]
    entries = data.get("entries") or []
    entry_names = {e.get("史略名称"): e.get("史略分类") for e in entries}
    entry_keys = {owner_key(e.get("史略名称", ""), e.get("史略分类", "")) for e in entries}

    para_map: Dict[int, str] = {}
    try:
        para_map = load_paragraph_text_map(data, sk)
    except Exception:
        pass

    for e in entries:
        migrate_entry_fields(e)
        eid = e.get("史略ID", "?")
        name = (e.get("史略名称") or "").strip()
        intro = (e.get("史略简介") or "").strip()
        cat = e.get("史略分类", "")
        quote = (e.get("原文字句") or "").strip()
        af = e.get("_auto_filled") or {}

        if name and intro == name:
            out.append(("L3-semantic", "WARN", f"[{eid}] 简介占位（简介=名称）"))

        if not af.get("_年LLM依据"):
            out.append(("L3-semantic", "ERROR", f"[{eid}] 缺 _年LLM依据"))

        kp = data.get("knowledge_provenance") or {}
        if (data.get("volume_type") or "") == "纪传叙事":
            s4 = (kp.get("step4") or {}).get("source", "")
            if s4 != "llm":
                out.append(("L3-semantic", "WARN", f"卷{vol} knowledge_provenance.step4 非 llm（={s4!r}）"))

        lv5 = e.get("五级细坐标", "")
        m = re.search(r"·([^·]+)·\d+$", lv5)
        if m and m.group(1) not in ("卷" + vol, cat) and not lv5.startswith(f"汉书·卷{vol}·{cat}"):
            if m.group(1) != cat:
                out.append(("L3-semantic", "ERROR", f"[{eid}] 五级细坐标分类「{m.group(1)}」≠ 史略分类「{cat}」"))

        if cat == "宗戚" and name in zj_map:
            exp = zj_map[name]
            got = (e.get("四级帝王坐标") or "").strip()
            if exp and got != exp:
                out.append(("L3-semantic", "ERROR", f"[{eid}] {name} 宗戚册封之君 现={got} 应为={exp}"))

        if quote and para_map:
            pgs = e.get("paragraphs") or []
            if pgs:
                pf = pgs[0].get("paragraph_from")
                text = para_map.get(int(pf), "")
                norm_q = re.sub(r"[\s\u200b\u3000]+", "", quote)[:12]
                norm_t = re.sub(r"[\s\u200b\u3000]+", "", text)[:80]
                if norm_q and norm_q not in norm_t and not re.match(r".*[纪传]第", quote):
                    out.append(("L3-semantic", "WARN", f"[{eid}] 原文字句与 P{pf} 段首不一致"))

    for seg in data.get("segment_attribution") or []:
        if seg.get("exclude_reason"):
            continue
        p = seg.get("paragraph")
        for ow in seg.get("owners") or []:
            n, c = ow.get("name"), ow.get("category")
            key = owner_key(n or "", c or "")
            if key not in entry_keys and n in entry_names:
                if entry_names[n] != c:
                    out.append(("L3-semantic", "ERROR", f"P{p} segment {n}({c}) ≠ entry({entry_names[n]})"))
            elif key not in entry_keys and n:
                out.append(("L3-semantic", "WARN", f"P{p} 归属 {n}({c}) 无对应 entry"))

    return out


def _cross_work_checks(hanshu_entries: Dict[str, dict], shiji_entries: Dict[str, dict]) -> List[Issue]:
    """同人物跨史记/汉书：分类不一致。"""
    out: List[Issue] = []
    overlap = set(hanshu_entries) & set(shiji_entries)
    for name in sorted(overlap):
        h = hanshu_entries[name]
        s = shiji_entries[name]
        if h["cat"] != s["cat"]:
            out.append((
                "L4-cross",
                "WARN",
                f"{name}: 汉书={h['cat']}({h['vol']}) vs 史记={s['cat']}({s['vol']})",
            ))
    return out


def _collect_work_entries(ann_dir: Path, work: str) -> Dict[str, dict]:
    result: Dict[str, dict] = {}
    for sk in ann_dir.glob(f"{work}_*_skeleton.json"):
        vol = sk.name.split("_")[1]
        data = json.loads(sk.read_text(encoding="utf-8"))
        for e in data.get("entries") or []:
            name = (e.get("史略名称") or "").strip()
            if not name:
                continue
            cat = normalize_entry_category(e.get("史略分类", ""))
            prev = result.get(name)
            if prev and prev["cat"] != cat:
                result[name] = {**prev, "cat": f"{prev['cat']}|{cat}", "vol": f"{prev['vol']},{vol}"}
            else:
                result[name] = {"cat": cat, "vol": vol, "eid": e.get("史略ID")}
    return result


def qc_volume(vol: str, ann_dir: Path, zj_map: Dict[str, str]) -> VolumeQC:
    vol_n = int(vol)
    rec = VolumeQC(vol=vol)

    if vol_n in SKIP_VOLUMES:
        sk = _find_skeleton(ann_dir, vol)
        if sk is None:
            rec.status = "skip"
            rec.issues.append(("meta", "INFO", "表/志/书 scope 外，无 skeleton 属预期"))
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

    audit = audit_file(sk, phase="final")
    for msg in audit["field_missing"] + audit["basic_errors"] + audit["coord_errors"] + audit["coord_chain_mismatch"]:
        rec.issues.append(("L2-coord", "ERROR", msg))

    pc_ok, pc_errs, pc_warns = _run_precheck(sk)
    rec.precheck_ok = pc_ok
    for e in pc_errs:
        rec.issues.append(("L2-precheck", "ERROR", e))
    for w in pc_warns:
        rec.issues.append(("L2-precheck", "WARN", w))

    for layer, sev, msg in _semantic_checks(data, sk, zj_map):
        rec.issues.append((layer, sev, msg))

    has_error = any(s == "ERROR" for _, s, _ in rec.issues)
    rec.status = "ok" if rec.json_ok and sk_ok and fin_ok and pc_ok and not has_error else "fail"
    return rec


def _summarize(records: List[VolumeQC], cross_issues: List[Issue]) -> Dict[str, Any]:
    by_status = defaultdict(int)
    layer_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in records:
        by_status[r.status] += 1
        for layer, sev, _ in r.issues:
            if sev in ("ERROR", "WARN"):
                layer_counts[layer][sev] += 1
    for layer, sev, _ in cross_issues:
        layer_counts[layer][sev] += 1

    intro_placeholders = sum(
        1 for r in records for layer, sev, msg in r.issues
        if layer == "L3-semantic" and "简介占位" in msg
    )

    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "work": WORK_ID,
        "volume_counts": dict(by_status),
        "skeleton_files": sum(1 for r in records if r.filename),
        "total_entries": sum(r.entry_count for r in records if r.filename),
        "fail_volumes": [r.vol for r in records if r.status == "fail"],
        "missing_volumes": [r.vol for r in records if r.status == "missing"],
        "skip_volumes": [r.vol for r in records if r.status == "skip"],
        "layer_issue_counts": {k: dict(v) for k, v in layer_counts.items()},
        "intro_placeholder_entries": intro_placeholders,
        "l1_final_fail": sum(1 for r in records if r.final_ok is False),
        "cross_work_warns": sum(1 for _, s, _ in cross_issues if s == "WARN"),
    }


def _render_md(records: List[VolumeQC], summary: Dict[str, Any], cross_issues: List[Issue]) -> str:
    lines = [
        "# 《汉书》多层质检报告",
        "",
        f"- 生成时间：{summary['generated_at']}",
        f"- skeleton：{summary['skeleton_files']} 卷 / {summary['total_entries']} 条",
        "",
        "## 检查层说明",
        "",
        "| 层级 | 工具 | 能发现什么 |",
        "|------|------|------------|",
        "| L0 | JSON | 文件损坏 |",
        "| L1 | check_format | 硬门：字段、坐标、身份门、provenance |",
        "| L2-coord | audit_hanshu_volumes | 坐标链、缺字段、年代倒置 |",
        "| L2-precheck | audit_precheck | 段落归属孤儿、密度、三明治 exclude |",
        "| L3-semantic | 启发式 | 简介占位、原文字句漂移、宗戚册封、segment 不一致 |",
        "| L4-cross | 跨书 | 与史记同名人物分类差异 |",
        "",
        "## 汇总",
        "",
        "| 状态 | 卷数 |",
        "|------|------|",
    ]
    labels = {"ok": "✅ 通过", "fail": "❌ 有问题", "missing": "⚠️ 缺文件", "skip": "⏭ 表志 scope 外"}
    for key in ("ok", "fail", "missing", "skip"):
        n = summary["volume_counts"].get(key, 0)
        if n:
            lines.append(f"| {labels.get(key, key)} | {n} |")

    lc = summary.get("layer_issue_counts") or {}
    lines.extend(["", "| 层级 | ERROR | WARN |", "|------|------:|------:|"])
    for layer in sorted(lc.keys()):
        lines.append(f"| {layer} | {lc[layer].get('ERROR', 0)} | {lc[layer].get('WARN', 0)} |")

    lines.extend([
        "",
        f"- 简介占位条目：{summary.get('intro_placeholder_entries', 0)} 条（非硬门，影响展示质量）",
        f"- 跨书分类 WARN：{summary.get('cross_work_warns', 0)} 条",
        "",
    ])

    fail_recs = [r for r in records if r.status == "fail"]
    if fail_recs:
        lines.append("## ❌ 失败卷明细")
        lines.append("")
        for r in fail_recs:
            lines.append(f"### 卷 {r.vol} — {r.filename}")
            errors = [(layer, msg) for layer, sev, msg in r.issues if sev == "ERROR"]
            for layer, msg in errors[:15]:
                lines.append(f"- `{layer}` {msg}")
            if len(errors) > 15:
                lines.append(f"- … 另有 {len(errors) - 15} 条 ERROR")
            lines.append("")

    if cross_issues:
        lines.append("## 跨书对照（史记 vs 汉书同名人物分类差异）")
        lines.append("")
        for _, _, msg in cross_issues[:25]:
            lines.append(f"- {msg}")
        if len(cross_issues) > 25:
            lines.append(f"- … 另有 {len(cross_issues) - 25} 条")
        lines.append("")

    lines.extend([
        "## 建议的进一步人工抽检",
        "",
        "1. **合传块边界**：`python3 audit_hezhuan_alignment.py --work 02汉书`（WARN 多属合传总述，你已确认可接受）",
        "2. **随机 10 卷深读**：对照段落索引 + 原文 txt，核对传主段界与分类理由",
        "3. **跨书主补**：读 `data/03索引标注条目/合并预判/01至02跨著作主补预判表.md`",
        "4. **简介批量补全**：303 条「简介=名称」需 Step4 LLM 写 20 字内简介",
        "",
        "## 重跑命令",
        "",
        "```bash",
        "cd pandahis/pandahis/tools/openclaw-historiography/historiography-annotate",
        "python3 batch_qc_hanshu.py",
        "HIST_REPAIR=1 python3 check_format.py <skeleton.json> --phase final  # 单卷",
        "```",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="《汉书》全卷批量质检")
    parser.add_argument("--vol-from", default="001")
    parser.add_argument("--vol-to", default=str(VOL_MAX))
    parser.add_argument("--json-only", action="store_true")
    parser.add_argument("-o", "--output-dir", default=None)
    args = parser.parse_args()

    ann_dir = paths()["annotations"]
    out_dir = Path(args.output_dir) if args.output_dir else ann_dir / "标注审计"
    out_dir.mkdir(parents=True, exist_ok=True)

    zj_path = SKILL / "reference" / "宗戚.json"
    zj_map = {}
    if zj_path.exists():
        zj_map = {r["宗戚名称"]: r.get("册封之君", "") for r in json.loads(zj_path.read_text(encoding="utf-8"))}

    vol_from = int(args.vol_from)
    vol_to = int(args.vol_to)

    print(f"🔍 《汉书》批量质检 卷 {vol_from:03d}–{vol_to:03d}")

    records: List[VolumeQC] = []
    for v in range(vol_from, vol_to + 1):
        vol = f"{v:03d}"
        print(f"   … 卷 {vol}", flush=True)
        records.append(qc_volume(vol, ann_dir, zj_map))

    h_entries = _collect_work_entries(ann_dir, "02汉书")
    s_entries = _collect_work_entries(ann_dir, "01史记")
    cross_issues = _cross_work_checks(h_entries, s_entries)

    summary = _summarize(records, cross_issues)
    report = {**summary, "cross_work_issues": [{"layer": a, "severity": b, "message": c} for a, b, c in cross_issues]}

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"QC报告_汉书_{ts}.json"
    md_path = out_dir / f"QC报告_汉书_{ts}.md"
    latest_json = out_dir / "QC报告_汉书_latest.json"
    latest_md = out_dir / "QC报告_汉书_latest.md"

    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    latest_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if not args.json_only:
        md_text = _render_md(records, summary, cross_issues)
        md_path.write_text(md_text, encoding="utf-8")
        latest_md.write_text(md_text, encoding="utf-8")

    print()
    print(f"✅ 完成：通过 {summary['volume_counts'].get('ok', 0)} | "
          f"失败 {summary['volume_counts'].get('fail', 0)} | "
          f"skip {summary['volume_counts'].get('skip', 0)}")
    print(f"   L1 final 失败: {summary['l1_final_fail']}")
    print(f"   简介占位: {summary.get('intro_placeholder_entries', 0)} 条")
    print(f"   报告: {md_path if not args.json_only else json_path}")

    return 1 if summary["volume_counts"].get("fail", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
