"""翻译线语义覆盖：合并后 LLM 复核 + 账本缓存。"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Tuple

from shared.coverage_semantic import (
    ClaimSpec,
    SemanticCoverageReport,
    run_semantic_coverage_batches,
)

from lib.coverage_info import CoverageUnit, build_coverage_units, info_point_is_classical
from lib.coverage_ledger import (
    apply_claim_results,
    claim_fingerprint,
    conveyed_ratio,
    load_ledger,
    pending_units,
    save_ledger,
)


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
    """语义覆盖专用：DeepSeek JSON 模式 + temperature=0，避免非 JSON 输出。"""
    from llm.config import PROVIDER_DEEPSEEK, get_provider_name
    from llm.deepseek_provider import run_deepseek_turn
    from lib.openclaw import run_agent_turn

    nonce = uuid.uuid4().hex[:8]
    session_id = f"tr-cov-{entry_id.replace('_', '-').lower()}-{nonce}"
    if get_provider_name() == PROVIDER_DEEPSEEK:
        res = run_deepseek_turn(
            prompt,
            session_id=session_id,
            timeout_sec=600,
            temperature=0,
            response_format={"type": "json_object"},
        )
        return str(res.get("result") or "")
    return str(run_agent_turn(prompt, session_id=session_id, timeout_sec=600))


def save_l2_artifact(work_dir: Path, entry_id: str, report: SemanticCoverageReport) -> Path:
    out_dir = work_dir / "coverage"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{entry_id}_coverage_l2.json"
    path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _semantic_min_ratio() -> float:
    return float(os.environ.get("TRANSLATE_COVERAGE_SEMANTIC_MIN_RATIO", "0.80"))


def _semantic_max_fail() -> int:
    return int(os.environ.get("TRANSLATE_COVERAGE_SEMANTIC_MAX_FAIL", "3"))


def _semantic_batch_min_ratio() -> float:
    return float(os.environ.get("TRANSLATE_COVERAGE_SEMANTIC_BATCH_MIN_RATIO", "0.90"))


def _semantic_batch_max_fail() -> int:
    return int(os.environ.get("TRANSLATE_COVERAGE_SEMANTIC_BATCH_MAX_FAIL", "1"))


def _incremental_coverage_enabled() -> bool:
    return os.environ.get("TRANSLATE_COVERAGE_INCREMENTAL", "1") != "0"


def semantic_coverage_gate_passed(
    ok_count: int,
    total: int,
    weak_count: int,
    *,
    min_ratio: float | None = None,
    max_fail: int | None = None,
) -> Tuple[bool, str]:
    """
    语义覆盖放行：传达率 >= min_ratio，或未通过条数 <= max_fail（满足其一即可）。
    """
    if total <= 0:
        return True, "无待检单元"
    ratio = ok_count / total
    min_r = _semantic_min_ratio() if min_ratio is None else min_ratio
    max_f = _semantic_max_fail() if max_fail is None else max_fail
    ratio_ok = ratio >= min_r
    count_ok = weak_count <= max_f
    if ratio_ok or count_ok:
        parts: List[str] = [f"{ok_count}/{total} 单元已传达 ({ratio:.0%})"]
        if weak_count:
            parts.append(f"未传达 {weak_count} 条")
        if ratio_ok and count_ok:
            parts.append(f"满足传达率 ≥{min_r:.0%} 且未传达 ≤{max_f}")
        elif ratio_ok:
            parts.append(f"满足传达率 ≥{min_r:.0%}")
        else:
            parts.append(f"未传达 ≤{max_f} 条（传达率 {ratio:.0%} < {min_r:.0%}，按条数容错放行）")
        return True, "；".join(parts)
    return (
        False,
        f"{ok_count}/{total} 已传达 ({ratio:.0%} < {min_r:.0%})，"
        f"且未传达 {weak_count} 条 > {max_f}",
    )


def verify_mother_semantic_coverage(
    detail: str,
    plan: Dict[str, Any],
    *,
    entry_id: str = "",
    entry_name: str = "",
    work_dir: Path | None = None,
    max_report: int = 8,
    gate_min_ratio: float | None = None,
    gate_max_fail: int | None = None,
    save_l2: bool = True,
    scope_label: str = "",
) -> Tuple[bool, List[str]]:
    """
    语义覆盖：仅对账本未 conveyed 的单元调 LLM；已通过的不重复请求。
    scope_label 用于日志（如「第 3/12 批」或「合并补验」）。
    """
    errors: List[str] = []
    checklist = plan.get("母本逐句清单") or []
    if not isinstance(checklist, list) or not checklist:
        errors.append("source plan 缺少「母本逐句清单」，无法校验母本覆盖")
        return False, errors

    units = build_coverage_units(checklist)
    if not units:
        return True, []

    if work_dir is None:
        errors.append("语义覆盖需要 work_dir 以读写账本")
        return False, errors

    entries = load_ledger(work_dir, entry_id)
    to_review, fps, cached_ok = pending_units(units, entries)

    if scope_label:
        print(f"   ℹ️ 语义覆盖{scope_label}：待复核 {len(to_review)}/{len(units)} 单元", flush=True)

    if to_review:
        claims = [unit_to_claim(unit) for unit in to_review]
        label_by_claim = {c.claim_id: unit.label for unit, c in zip(to_review, claims)}

        def _on_batch_done(
            batch_no: int,
            total_batches: int,
            batch_report: SemanticCoverageReport,
            _batch: tuple,
        ) -> None:
            for cr in batch_report.claims:
                label = label_by_claim.get(cr.claim_id, cr.claim_id)
                apply_claim_results(
                    entries,
                    claim_id=label,
                    status=cr.status,
                    claim_fp=fps.get(label, ""),
                    note=cr.note or cr.evidence,
                )
            save_ledger(work_dir, entry_id, entries)
            print(
                f"   ℹ️ 语义覆盖账本已更新 [{batch_no}/{total_batches}]",
                flush=True,
            )

        try:
            report = run_semantic_coverage_batches(
                entry_id=entry_id,
                entry_name=entry_name or str(plan.get("史略名称") or ""),
                detail_text=detail,
                claims=claims,
                llm_call=lambda prompt: _translate_llm_call(entry_id, prompt),
                on_batch_done=_on_batch_done,
            )
            if save_l2:
                save_l2_artifact(work_dir, entry_id, report)
            if report.degraded:
                print(
                    f"   ⚠️ 语义覆盖：部分批次 JSON 解析失败，已降级为 unclear（见 coverage 产物）",
                    flush=True,
                )
            for cr in report.claims:
                label = label_by_claim.get(cr.claim_id, cr.claim_id)
                apply_claim_results(
                    entries,
                    claim_id=label,
                    status=cr.status,
                    claim_fp=fps.get(label, ""),
                    note=cr.note or cr.evidence,
                )
        except Exception as exc:
            errors.append(f"母本语义覆盖 LLM 复核失败: {exc}")
            return False, errors
    else:
        print(
            f"   ℹ️ 语义覆盖：{len(cached_ok)}/{len(units)} 单元已由账本确认，跳过 LLM",
            flush=True,
        )

    save_ledger(work_dir, entry_id, entries)

    ok_count, total = conveyed_ratio(units, entries, fps)
    min_ratio = _semantic_min_ratio() if gate_min_ratio is None else gate_min_ratio
    max_fail = _semantic_max_fail() if gate_max_fail is None else gate_max_fail

    weak_labels: List[str] = []
    for unit in units:
        rec = entries.get(unit.label) or {}
        fp = fps.get(unit.label) or claim_fingerprint(unit)
        status = str(rec.get("status") or "")
        if status == "conveyed" and str(rec.get("claim_fp") or "") == fp:
            continue
        weak_labels.append(unit.label)

    passed, gate_note = semantic_coverage_gate_passed(
        ok_count, total, len(weak_labels), min_ratio=min_ratio, max_fail=max_fail
    )
    if not passed:
        msgs = [f"母本语义覆盖不足: {gate_note}"]
        for label in weak_labels[:max_report]:
            rec = entries.get(label) or {}
            status = str(rec.get("status") or "未复核")
            note = str(rec.get("note") or "")[:48]
            row = next((u.primary for u in units if u.label == label), {})
            snippet = str(row.get("原文摘句") or row.get("信息点") or "")[:48]
            msgs.append(f"  [{status}] {label} {snippet}" + (f" — {note}" if note else ""))
        if len(weak_labels) > max_report:
            msgs.append(f"  …另有 {len(weak_labels) - max_report} 单元未传达")
        errors.extend(msgs)
        return False, errors

    info = f"母本语义覆盖: {gate_note}"
    if to_review:
        info += f"；本次新复核 {len(to_review)} 单元"
    else:
        info += "；全部命中账本缓存"
    return True, [f"[info] {info}"]


def verify_mother_batch_semantic_coverage(
    detail: str,
    plan: Dict[str, Any],
    *,
    entry_id: str = "",
    entry_name: str = "",
    work_dir: Path | None = None,
    batch_label: str = "",
    max_report: int = 6,
) -> Tuple[bool, List[str]]:
    """Phase1 分批：仅验本批 M，对照本批译文（非全文）。"""
    if not _incremental_coverage_enabled():
        return True, []
    scope = f"（{batch_label}）" if batch_label else "（本批）"
    return verify_mother_semantic_coverage(
        detail,
        plan,
        entry_id=entry_id,
        entry_name=entry_name,
        work_dir=work_dir,
        max_report=max_report,
        gate_min_ratio=_semantic_batch_min_ratio(),
        gate_max_fail=_semantic_batch_max_fail(),
        save_l2=False,
        scope_label=scope,
    )


def verify_mother_merge_semantic_coverage(
    detail: str,
    plan: Dict[str, Any],
    *,
    entry_id: str = "",
    entry_name: str = "",
    work_dir: Path | None = None,
    max_report: int = 8,
) -> Tuple[bool, List[str]]:
    """Phase1 合并后：仅复核账本 pending 单元，全篇门槛 80%/≤3。"""
    if not _incremental_coverage_enabled():
        return verify_mother_semantic_coverage(
            detail,
            plan,
            entry_id=entry_id,
            entry_name=entry_name,
            work_dir=work_dir,
            max_report=max_report,
            scope_label="（全篇）",
        )
    return verify_mother_semantic_coverage(
        detail,
        plan,
        entry_id=entry_id,
        entry_name=entry_name,
        work_dir=work_dir,
        max_report=max_report,
        gate_min_ratio=_semantic_min_ratio(),
        gate_max_fail=_semantic_max_fail(),
        save_l2=True,
        scope_label="（合并补验）",
    )


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
    """L1 灰区兜底：对弱覆盖单元做语义复核（legacy）。"""
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
    """将 L2 判为 conveyed 的单元补计入 L1 命中数（legacy L1 路径）。"""
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
