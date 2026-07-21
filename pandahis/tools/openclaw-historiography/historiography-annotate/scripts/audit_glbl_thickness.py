#!/usr/bin/env python3
"""对已发布 GLBL 索引做一次性厚度审计（只读 · 不重编号）。

规则 SSOT：reference/史料厚度门规则.md

用法:
  python3 audit_glbl_thickness.py
  python3 audit_glbl_thickness.py --index /path/to/史略索引_01至02.json
  python3 audit_glbl_thickness.py --only downgrade_recommended
  python3 audit_glbl_thickness.py --write-registry   # 将 downgrade 条目写入薄标注注册表（仍不改 GLBL ID）

输出:
  data/05工作流中间产物/薄标注待补全/glbl_thickness_audit.json
  data/05工作流中间产物/薄标注待补全/GLBL厚度审计报告.md
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ANNOTATE_DIR = Path(__file__).resolve().parents[1]
if str(_ANNOTATE_DIR) not in sys.path:
    sys.path.insert(0, str(_ANNOTATE_DIR))

from source_thickness import (  # noqa: E402
    THIN_SOURCE_THRESHOLD,
    classify_glbl_thickness,
    thin_registry_path,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _default_index() -> Path:
    return _repo_root() / "data" / "03索引标注条目" / "史略索引_01至02.json"


def _audit_out_dir() -> Path:
    return _repo_root() / "data" / "05工作流中间产物" / "薄标注待补全"


def audit_index(index_path: Path) -> dict[str, Any]:
    doc = json.loads(index_path.read_text(encoding="utf-8"))
    entries = doc.get("entries") if isinstance(doc, dict) else doc
    if not isinstance(entries, list):
        raise SystemExit("索引格式错误：缺少 entries 数组")

    rows: list[dict[str, Any]] = []
    stats: dict[str, int] = {}

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        eid = str(entry.get("史略ID") or "").strip()
        if not eid.startswith("GLBL_"):
            continue

        result = classify_glbl_thickness(entry)
        verdict = result["verdict"]
        stats[verdict] = stats.get(verdict, 0) + 1

        rows.append(
            {
                "史略ID": eid,
                "史略名称": entry.get("史略名称"),
                "史略分类": entry.get("史略分类"),
                "朝代ID": entry.get("朝代ID"),
                "二级朝代坐标": entry.get("二级朝代坐标"),
                "母本著作": entry.get("母本著作"),
                "史略来源": entry.get("史略来源"),
                "source_han_chars_total": result.get("total", 0),
                "source_han_chars_mother": result.get("mother", 0),
                "source_han_chars_supplement": result.get("supplement", 0),
                "verdict": verdict,
                "recommended_action": result.get("recommended_action"),
                "reason": result.get("reason"),
                "paragraphs": entry.get("paragraphs"),
                "source_entries": entry.get("source_entries"),
            }
        )

    downgrade = [r for r in rows if r["verdict"] == "downgrade_recommended"]
    swap_hint = [r for r in rows if r["verdict"] == "pass_swap_recommended"]

    return {
        "schema": "glbl_thickness_audit/v1",
        "rules_ref": "historiography-annotate/reference/史料厚度门规则.md",
        "audited_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "index_path": str(index_path),
        "threshold_han_chars": THIN_SOURCE_THRESHOLD,
        "total_glbl": len(rows),
        "stats": stats,
        "downgrade_count": len(downgrade),
        "swap_hint_count": len(swap_hint),
        "entries": rows,
        "downgrade_ids": [r["史略ID"] for r in downgrade],
    }


def _render_md(report: dict[str, Any]) -> str:
    lines = [
        "# GLBL 厚度审计报告（只读 · 不重编号）",
        "",
        f"- 审计时间：{report['audited_at']}",
        f"- 索引：`{report['index_path']}`",
        f"- 阈值：**{report['threshold_han_chars']}** 汉字",
        f"- GLBL 总数：**{report['total_glbl']}**",
        "",
        "## 统计",
        "",
        "| verdict | 数量 | 说明 |",
        "|---------|------|------|",
        "| pass | "
        f"{report['stats'].get('pass', 0)} | 合计 ≥ 阈值，可继续翻译 |",
        "| pass_swap_recommended | "
        f"{report['stats'].get('pass_swap_recommended', 0)} | 合计达标但母本过薄（历史 merge 未 swap） |",
        "| **downgrade_recommended** | "
        f"**{report['downgrade_count']}** | **建议降级：停翻译，走朝代补全** |",
        "| skip_not_phase1 | "
        f"{report['stats'].get('skip_not_phase1', 0)} | 朝代补全等非一期条目 |",
        "| error_* | "
        f"{report['stats'].get('error_no_paragraphs', 0) + report['stats'].get('error_recall_failed', 0)} | 需人工复核 |",
        "",
    ]

    def _table(title: str, items: list[dict[str, Any]], limit: int = 80) -> None:
        lines.append(f"## {title}（{len(items)}）")
        lines.append("")
        if not items:
            lines.append("（无）")
            lines.append("")
            return
        lines.append("| GLBL | 名称 | 分类 | 合计字 | 母本 | 补充 | 建议 |")
        lines.append("|------|------|------|--------|------|------|------|")
        for r in items[:limit]:
            lines.append(
                f"| {r['史略ID']} | {r.get('史略名称')} | {r.get('史略分类')} | "
                f"{r.get('source_han_chars_total')} | {r.get('source_han_chars_mother')} | "
                f"{r.get('source_han_chars_supplement')} | {r.get('recommended_action')} |"
            )
        if len(items) > limit:
            lines.append(f"| … | 另有 {len(items) - limit} 条 | | | | | |")
        lines.append("")

    downgrade = [r for r in report["entries"] if r["verdict"] == "downgrade_recommended"]
    downgrade.sort(key=lambda x: (x.get("source_han_chars_total") or 0, x.get("史略ID") or ""))
    _table("建议降级条目", downgrade, limit=200)

    swap = [r for r in report["entries"] if r["verdict"] == "pass_swap_recommended"]
    _table("母本 swap 建议（仍保留 GLBL）", swap, limit=40)

    lines.extend(
        [
            "## 处置说明",
            "",
            "1. **downgrade_recommended**：不在本次脚本中删除或改号 GLBL；运营上停止新翻译/增量 sync，"
            "优先走朝代知识补全；待补全出新 GLBL 后再做 ID 迁移（外科手术式 repair）。",
            "2. 完整 JSON：`data/05工作流中间产物/薄标注待补全/glbl_thickness_audit.json`",
            "",
        ]
    )
    return "\n".join(lines)


def _write_registry_from_audit(report: dict[str, Any], registry_path: Path) -> int:
    """将 downgrade 条目追加/合并进薄标注注册表（不删 GLBL）。"""
    downgrade = [r for r in report["entries"] if r["verdict"] == "downgrade_recommended"]
    existing: dict[str, Any] = {"entries": []}
    if registry_path.is_file():
        existing = json.loads(registry_path.read_text(encoding="utf-8"))

    by_glbl = {str(r.get("史略ID")): r for r in existing.get("entries") or [] if r.get("史略ID")}

    for r in downgrade:
        eid = r["史略ID"]
        by_glbl[eid] = {
            "defer_reason": "glbl_audit_downgrade_recommended",
            "source_char_count": r.get("source_han_chars_total"),
            "recommended_path": "dynasty_knowledge_supplement",
            "published_glbl_id": eid,
            "史略ID": eid,
            "史略名称": r.get("史略名称"),
            "史略分类": r.get("史略分类"),
            "朝代ID": r.get("朝代ID") or "",
            "二级朝代坐标": r.get("二级朝代坐标") or "",
            "paragraphs": r.get("paragraphs") or [],
            "audit_note": r.get("reason"),
            "recommended_action": r.get("recommended_action"),
        }

    doc = {
        "schema": "thin_annotation_deferred/v1",
        "rules_ref": "historiography-annotate/reference/史料厚度门规则.md",
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "threshold_han_chars": THIN_SOURCE_THRESHOLD,
        "entry_count": len(by_glbl),
        "entries": sorted(by_glbl.values(), key=lambda x: str(x.get("史略ID", ""))),
        "sources": ["merge_global_entries", "audit_glbl_thickness"],
    }
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return len(downgrade)


def main() -> int:
    parser = argparse.ArgumentParser(description="GLBL 厚度审计（只读）")
    parser.add_argument("--index", type=Path, default=None, help="全局史略索引 JSON")
    parser.add_argument(
        "--only",
        choices=[
            "downgrade_recommended",
            "pass_swap_recommended",
            "all",
        ],
        default="all",
    )
    parser.add_argument(
        "--write-registry",
        action="store_true",
        help="将 downgrade 条目写入薄标注注册表（仍不改 GLBL 索引）",
    )
    args = parser.parse_args()

    index_path = args.index or _default_index()
    if not index_path.is_file():
        print(f"❌ 索引不存在: {index_path}", file=sys.stderr)
        return 1

    print(f"🔍 审计 {index_path} …")
    report = audit_index(index_path)

    out_dir = _audit_out_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "glbl_thickness_audit.json"
    md_path = out_dir / "GLBL厚度审计报告.md"

    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(_render_md(report), encoding="utf-8")

    print(json.dumps(
        {k: v for k, v in report.items() if k != "entries"},
        ensure_ascii=False,
        indent=2,
    ))
    print(f"\n✅ JSON → {json_path}")
    print(f"✅ MD   → {md_path}")

    if args.only != "all":
        filtered = [r for r in report["entries"] if r["verdict"] == args.only]
        print(f"\n--- {args.only} ({len(filtered)}) ---")
        for r in filtered[:50]:
            print(
                f"  {r['史略ID']} {r.get('史略名称')} "
                f"total={r.get('source_han_chars_total')} "
                f"mother={r.get('source_han_chars_mother')}"
            )
        if len(filtered) > 50:
            print(f"  … 另有 {len(filtered) - 50} 条")

    if args.write_registry:
        n = _write_registry_from_audit(report, thin_registry_path(_repo_root()))
        print(f"\n📋 已写入薄标注注册表 {n} 条 downgrade（published_glbl_id 保留）")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
