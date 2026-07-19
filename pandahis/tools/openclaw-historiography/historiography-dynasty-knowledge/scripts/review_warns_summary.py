"""汇总 Kimi review 的硬史实问题，供人工裁定（不阻断流水线）。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import dynasty_supplement_lib as dkl


def _factual_error_rows(review: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for err in review.get("factual_errors") or []:
        if not isinstance(err, dict):
            continue
        quote = str(err.get("quote") or "").strip()
        reason = str(err.get("reason") or "").strip()
        fix = str(err.get("fix_hint") or "").strip()
        if quote or reason:
            rows.append({"quote": quote, "reason": reason, "fix_hint": fix})
    return rows


def _paragraph_issues(review: dict[str, Any]) -> list[dict[str, Any]]:
    """兼容 v1 逐段审校产物。"""
    rows: list[dict[str, Any]] = []
    for pr in review.get("paragraph_reviews") or []:
        if not isinstance(pr, dict):
            continue
        verdict = str(pr.get("verdict") or "pass").lower()
        if verdict not in ("warn", "fail"):
            continue
        issues = pr.get("issues") or []
        if not issues and verdict == "warn":
            continue
        rows.append(
            {
                "paragraph_index": pr.get("paragraph_index"),
                "verdict": verdict,
                "issues": [str(i) for i in issues],
                "suggested_fix": str(pr.get("suggested_fix") or ""),
            }
        )
    return rows


def build_entry_review_row(
    entry_id: str,
    entry_name: str,
    review: dict[str, Any],
) -> dict[str, Any] | None:
    factual = _factual_error_rows(review)
    forced_pass = bool(review.get("forced_pass"))
    has_factual = (bool(review.get("has_factual_errors")) or bool(factual)) and not forced_pass
    overall = str(review.get("overall_verdict") or ("fail" if has_factual else "pass")).lower()
    if forced_pass:
        overall = "forced_pass"
    para_issues = _paragraph_issues(review)

    if not has_factual and overall in ("pass", "forced_pass") and not para_issues:
        if not forced_pass:
            return None

    return {
        "史略ID": entry_id,
        "史略名称": entry_name,
        "overall_verdict": overall,
        "summary": str(review.get("summary") or ""),
        "reviewed_at": review.get("reviewed_at"),
        "review_fix_round": review.get("review_fix_round"),
        "forced_pass": forced_pass,
        "factual_errors": factual if not forced_pass else factual,
        "paragraph_issues": para_issues,
        "human_review_required": forced_pass or has_factual or overall in ("warn", "fail") or bool(para_issues),
    }


def aggregate_review_warns(
    logs_dir: Path,
    *,
    entries: list[dict[str, Any]] | None = None,
    details_dir: Path | None = None,
) -> dict[str, Any]:
    """扫描 logs/reviews，汇总需人工关注的条目。"""
    name_by_id: dict[str, str] = {}
    if entries:
        for e in entries:
            eid = str(e.get("史略ID") or "")
            if eid:
                name_by_id[eid] = str(e.get("史略名称") or "")

    reviews_dir = logs_dir / "reviews"
    rows: list[dict[str, Any]] = []
    if reviews_dir.is_dir():
        for path in sorted(reviews_dir.glob("*_review.json")):
            review = json.loads(path.read_text(encoding="utf-8"))
            eid = str(review.get("史略ID") or path.stem.replace("_review", ""))
            name = name_by_id.get(eid, "")
            if not name and details_dir and details_dir.is_dir():
                for detail_path in details_dir.glob(f"{eid}_*.json"):
                    stem = detail_path.stem
                    if "_" in stem:
                        name = stem.split("_", 1)[1]
                        break
            if not name:
                name = eid
            row = build_entry_review_row(eid, name, review)
            if row:
                rows.append(row)

    rows.sort(
        key=lambda r: (
            r["overall_verdict"] != "fail",
            r["overall_verdict"] != "warn",
            r["史略ID"],
        )
    )
    return {
        "schema": "dynasty-knowledge-review-warns-summary/v1",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "entry_count": len(rows),
        "entries": rows,
    }


def write_review_warns_summary(
    logs_dir: Path,
    *,
    entries: list[dict[str, Any]] | None = None,
    dynasty_name: str = "朝代",
    details_dir: Path | None = None,
) -> tuple[Path, Path]:
    doc = aggregate_review_warns(logs_dir, entries=entries, details_dir=details_dir)
    json_path = logs_dir / "review_warns_汇总.json"
    md_path = logs_dir / "review_warns_汇总.md"
    json_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        f"# {dynasty_name} · Kimi 事实核查人工关注汇总",
        "",
        f"生成时间：{doc['generated_at']}  ",
        f"需关注条目：**{doc['entry_count']}**  ",
        "",
        "> Kimi 硬史实问题 **不阻断**流水线；请在本表裁定是否改稿或放行。",
        "",
    ]
    if not doc["entries"]:
        lines.append("*（当前无硬史实问题）*")
    else:
        for row in doc["entries"]:
            if row.get("forced_pass"):
                flag = "⏭️ forced_pass"
            elif row["overall_verdict"] == "fail":
                flag = "🔴 有硬错误"
            else:
                flag = "🟡 warn"
            lines.append(f"## {flag} {row['史略ID']} {row['史略名称']}")
            lines.append("")
            if row.get("forced_pass"):
                lines.append(
                    f"**状态**：自动改稿已终止（Kimi 第 {row.get('review_fix_round') or '?'} 轮仍有问题），"
                    f"**强制通过**，请人工裁定。"
                )
                lines.append("")
            lines.append(f"**总评**：{row['summary']}")
            lines.append("")
            if row.get("factual_errors"):
                lines.append("**硬史实问题**：")
                for i, err in enumerate(row["factual_errors"], 1):
                    if err.get("quote"):
                        lines.append(f"- #{i} 问题句：{err['quote']}")
                    if err.get("reason"):
                        lines.append(f"  - 原因：{err['reason']}")
                    if err.get("fix_hint"):
                        lines.append(f"  - 建议：{err['fix_hint']}")
                lines.append("")
            if row.get("paragraph_issues"):
                lines.append("**分段问题（旧版审校）**：")
                for pi in row["paragraph_issues"]:
                    pidx = pi.get("paragraph_index")
                    pv = pi.get("verdict")
                    lines.append(f"- P{pidx} ({pv})：")
                    for issue in pi.get("issues") or []:
                        lines.append(f"  - {issue}")
                    fix = pi.get("suggested_fix")
                    if fix:
                        lines.append(f"  - 建议：{fix}")
                lines.append("")
            lines.append("---")
            lines.append("")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path
