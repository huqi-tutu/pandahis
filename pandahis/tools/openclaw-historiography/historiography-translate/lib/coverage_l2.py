"""翻译线 L2 语义覆盖：在 L1 灰区调用 LLM 复核弱覆盖单元。"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Tuple

from shared.coverage_semantic import ClaimSpec, SemanticCoverageReport, run_semantic_coverage_batches

from lib.coverage_info import CoverageUnit, info_point_is_classical


def unit_to_claim(unit: CoverageUnit) -> ClaimSpec:
    row = unit.primary
    cid = unit.label or str(row.get("编号") or "")
    info = str(row.get("信息点") or "").strip()
    orig = str(row.get("原文摘句") or row.get("text") or "").strip()
    if info and not info_point_is_classical(info, orig):
        claim = info
    elif orig:
        claim = f"母本信息：{orig}"
    else:
        claim = cid
    if unit.kind == "group" and len(unit.items) > 1:
        parts = [str(x.get("原文摘句") or "").strip() for x in unit.items if x.get("原文摘句")]
        if parts:
            claim = "；".join(parts[:4])
    return ClaimSpec(claim_id=cid, claim=claim[:240])


def _translate_llm_call(entry_id: str, prompt: str) -> str:
    from lib.openclaw import run_agent_turn

    nonce = uuid.uuid4().hex[:8]
    session_id = f"tr-cov-{entry_id.replace('_', '-').lower()}-{nonce}"
    return str(run_agent_turn(prompt, session_id=session_id, timeout_sec=600))


def save_l2_artifact(work_dir: Path, entry_id: str, report: SemanticCoverageReport) -> Path:
    out_dir = work_dir / "coverage"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{entry_id}_coverage_l2.json"
    path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def run_l2_coverage_review(
    *,
    entry_id: str,
    entry_name: str,
    detail: str,
    weak_units: List[Tuple[CoverageUnit, float]],
    l1_ratio: float,
    l1_min_ratio: float,
    work_dir: Path | None = None,
) -> SemanticCoverageReport:
    """对 L1 弱覆盖单元做语义复核；按得分从低到高优先送审。"""
    import os

    max_claims = int(os.environ.get("TRANSLATE_COVERAGE_L2_MAX_CLAIMS", "24"))
    ordered = sorted(weak_units, key=lambda x: x[1])
    claims = [unit_to_claim(unit) for unit, _ in ordered[:max_claims]]

    report = run_semantic_coverage_batches(
        entry_id=entry_id,
        entry_name=entry_name,
        detail_text=detail,
        claims=claims,
        llm_call=lambda prompt: _translate_llm_call(entry_id, prompt),
        l1_ratio=l1_ratio,
        l1_min_ratio=l1_min_ratio,
    )
    if work_dir is not None:
        save_l2_artifact(work_dir, entry_id, report)
    return report


def apply_l2_rescue(
    *,
    ok_count: int,
    units_total: int,
    min_ratio: float,
    weak_units: List[Tuple[CoverageUnit, float]],
    report: SemanticCoverageReport,
) -> Tuple[int, bool, List[str]]:
    """
    将 L2 判为 conveyed 的单元补计入 L1 命中数。
    返回 (新 ok_count, 是否 rescued 通过, 说明信息)。
    """
    weak_labels = {unit.label for unit, _ in weak_units}
    rescued = [cid for cid in report.conveyed_ids if cid in weak_labels]
    new_ok = ok_count + len(rescued)
    new_ratio = new_ok / units_total if units_total else 1.0
    notes: List[str] = []
    if rescued:
        notes.append(f"L2 语义复核救回 {len(rescued)} 单元: {', '.join(rescued[:6])}")
    hard = [c for c in report.claims if c.status == "contradicted"]
    if hard:
        for c in hard[:5]:
            notes.append(f"L2 矛盾 [{c.claim_id}]: {c.claim[:48]}")
    missing = [c for c in report.claims if c.status == "missing"]
    for c in missing[:5]:
        notes.append(f"L2 仍缺失 [{c.claim_id}]: {c.claim[:48]}")
    passed = new_ratio >= min_ratio and not hard
    return new_ok, passed, notes
