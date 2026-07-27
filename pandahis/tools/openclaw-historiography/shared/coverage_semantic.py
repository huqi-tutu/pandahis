"""语义覆盖检（L2）：判断白话正文是否传达主张，不做字面匹配。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Protocol, Sequence


class OnBatchDone(Protocol):
    def __call__(
        self,
        batch_no: int,
        total_batches: int,
        report: "SemanticCoverageReport",
        batch: Sequence[ClaimSpec],
    ) -> None: ...

_VALID_STATUSES = frozenset({"conveyed", "missing", "contradicted", "unclear"})


@dataclass
class ClaimSpec:
    claim_id: str
    claim: str

    def to_dict(self) -> dict[str, str]:
        return {"id": self.claim_id, "claim": self.claim}


@dataclass
class ClaimResult:
    claim_id: str
    claim: str
    status: str  # conveyed | missing | contradicted | unclear
    evidence: str = ""
    note: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.claim_id,
            "claim": self.claim,
            "status": self.status,
            "evidence": self.evidence,
            "note": self.note,
        }


@dataclass
class SemanticCoverageReport:
    entry_id: str
    passed: bool
    claims: list[ClaimResult] = field(default_factory=list)
    summary: str = ""
    issues: list[str] = field(default_factory=list)
    l1_ratio: float = 0.0
    l1_min_ratio: float = 0.0
    degraded: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "translate-coverage-l2/v1",
            "史略ID": self.entry_id,
            "passed": self.passed,
            "degraded": self.degraded,
            "summary": self.summary,
            "l1_ratio": round(self.l1_ratio, 4),
            "l1_min_ratio": round(self.l1_min_ratio, 4),
            "claims": [c.to_dict() for c in self.claims],
            "issues": self.issues,
        }

    @property
    def conveyed_ids(self) -> set[str]:
        return {c.claim_id for c in self.claims if c.status == "conveyed"}


def strip_detail_body(detail: str) -> str:
    return detail.split("*参考著作*")[0].split("参考著作")[0].strip()


def should_trigger_l2(
    *,
    checklist_size: int,
    ratio: float,
    min_ratio: float,
    enabled: bool | None = None,
    gray_band: float | None = None,
    min_checklist: int | None = None,
) -> bool:
    """L1 未过且落在灰区、且篇目够长时，启用 L2 语义复核。"""
    import os

    if enabled is None:
        enabled = os.environ.get("TRANSLATE_COVERAGE_L2", "1") != "0"
    if not enabled:
        return False
    if ratio >= min_ratio:
        return False
    if gray_band is None:
        gray_band = float(os.environ.get("TRANSLATE_COVERAGE_L2_GRAY_BAND", "0.12"))
    if min_checklist is None:
        min_checklist = int(os.environ.get("TRANSLATE_COVERAGE_L2_MIN_CHECKLIST", "50"))
    if checklist_size < min_checklist:
        return False
    return ratio >= min_ratio - gray_band


def build_coverage_response_skeleton(claims: Sequence[ClaimSpec]) -> dict[str, Any]:
    """由代码生成待填 JSON 骨架；模型只填 status / evidence / note / summary。"""
    return {
        "claims": [
            {"id": c.claim_id, "status": "", "evidence": "", "note": ""}
            for c in claims
        ],
        "summary": "",
        "passed": None,
    }


def build_translate_coverage_prompt(
    *,
    entry_id: str,
    entry_name: str,
    detail_text: str,
    claims: Sequence[ClaimSpec],
) -> str:
    body = strip_detail_body(detail_text)
    claims_json = json.dumps([c.to_dict() for c in claims], ensure_ascii=False, indent=2)
    skeleton_json = json.dumps(
        build_coverage_response_skeleton(claims),
        ensure_ascii=False,
        indent=2,
    )
    id_list = "、".join(c.claim_id for c in claims)
    return f"""你是史略翻译质检员。正文为**白话译文**，不要求出现古籍原词；只判断「该句母本信息是否已被读者读到」。

## 条目
史略ID: {entry_id}
史略名称: {entry_name}

## 须确认已传达的信息（来自母本逐句清单）
{claims_json}

## 白话译文
{body}

## 判定纪律
- **conveyed**：白话改写、意译也算；读者能 get 到同一事实即可
- **missing**：完全未涉及或过于模糊
- **contradicted**：与主张明显矛盾
- **unclear**：疑似写到但无法确认
- 不得因未出现文言原词、未出现清单关键词而判 missing

## 输出要求（严格遵守）
1. **只输出 JSON**，不要 markdown 代码块，不要任何前后说明
2. 使用下方骨架，**禁止增删 claims、禁止改 id**（允许 id：{id_list}）
3. 你只填：`status`、`evidence`、`note`、`summary`；`passed` 填 true/false
4. `status` 只能是：conveyed | missing | contradicted | unclear

## 待填 JSON 骨架（请原样保留结构，只填空字段）
{skeleton_json}

`passed=true` 当且仅当：本批无 missing、无 contradicted；unclear 最多 1 条。"""


def build_translate_coverage_retry_prompt(base_prompt: str, *, bad_output: str, error: str) -> str:
    preview = bad_output.strip()[:800]
    return f"""{base_prompt}

---
【上次输出无法解析】{error}
请严格按骨架只返回合法 JSON，不要 markdown，不要解释。
上次输出片段：
{preview}
"""


def _normalize_claim_id(cid: str) -> str:
    m = re.search(r"(\d+)$", str(cid))
    if not m:
        return str(cid)
    return str(int(m.group(1)))


def _extract_json_object(text: str) -> dict[str, Any] | None:
    if not text or not text.strip():
        return None
    stripped = text.strip()
    if stripped.startswith("{"):
        try:
            data = json.loads(stripped)
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            pass
    for block in re.findall(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE):
        try:
            data = json.loads(block.strip())
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            continue
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            data = json.loads(text[start : end + 1])
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            pass
    if start >= 0:
        try:
            data, _ = json.JSONDecoder().raw_decode(text[start:])
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def _normalize_status(raw: Any) -> str:
    status = str(raw or "").strip().lower()
    if status not in _VALID_STATUSES:
        return "unclear"
    return status


def _claim_results_from_data(
    data: dict[str, Any],
    claims: Sequence[ClaimSpec],
) -> tuple[list[ClaimResult], list[str]]:
    llm_claims = [c for c in (data.get("claims") or []) if isinstance(c, dict)]
    by_id = {str(c.get("id")): c for c in llm_claims if c.get("id") is not None}
    by_norm = {_normalize_claim_id(k): v for k, v in by_id.items()}
    used_indices: set[int] = set()
    results: list[ClaimResult] = []
    issues: list[str] = []

    for i, spec in enumerate(claims):
        cid = spec.claim_id
        row: dict[str, Any] = {}
        if cid in by_id:
            row = by_id[cid]
        else:
            norm = _normalize_claim_id(cid)
            if norm in by_norm:
                row = by_norm[norm]
            elif i < len(llm_claims) and i not in used_indices:
                row = llm_claims[i]
                used_indices.add(i)

        status = _normalize_status(row.get("status"))
        if not str(row.get("status") or "").strip():
            status = "unclear"
        cr = ClaimResult(
            claim_id=cid,
            claim=spec.claim,
            status=status,
            evidence=str(row.get("evidence") or "")[:200],
            note=str(row.get("note") or "")[:200],
        )
        results.append(cr)
        if status == "missing":
            issues.append(f"missing [{cid}]: {spec.claim[:60]}")
        elif status == "contradicted":
            issues.append(f"contradicted [{cid}]: {spec.claim[:60]}")

    return results, issues


def parse_semantic_coverage_response(
    text: str,
    claims: Sequence[ClaimSpec],
) -> SemanticCoverageReport:
    data = _extract_json_object(text)
    if not data:
        raise RuntimeError("L2 语义覆盖输出非 JSON")

    results, issues = _claim_results_from_data(data, claims)
    unclear_n = sum(1 for r in results if r.status == "unclear")
    hard_fail = any(r.status in ("missing", "contradicted") for r in results)
    passed = bool(data.get("passed")) if data.get("passed") is not None else (
        not hard_fail and unclear_n <= 1
    )
    if hard_fail:
        passed = False

    return SemanticCoverageReport(
        entry_id="",
        passed=passed,
        claims=results,
        summary=str(data.get("summary") or ""),
        issues=issues,
    )


def unclear_fallback_report(
    claims: Sequence[ClaimSpec],
    *,
    reason: str,
    entry_id: str = "",
    l1_ratio: float = 0.0,
    l1_min_ratio: float = 0.0,
) -> SemanticCoverageReport:
    """JSON 解析失败时降级：本批全部标 unclear，不阻断整条流水线。"""
    note = reason[:200]
    results = [
        ClaimResult(
            claim_id=spec.claim_id,
            claim=spec.claim,
            status="unclear",
            evidence="",
            note=note,
        )
        for spec in claims
    ]
    return SemanticCoverageReport(
        entry_id=entry_id,
        passed=False,
        claims=results,
        summary=f"解析降级: {reason[:120]}",
        issues=[reason],
        l1_ratio=l1_ratio,
        l1_min_ratio=l1_min_ratio,
        degraded=True,
    )


def _batch_status_counts(report: SemanticCoverageReport) -> dict[str, int]:
    counts = {"conveyed": 0, "unclear": 0, "missing": 0, "contradicted": 0}
    for cr in report.claims:
        key = cr.status if cr.status in counts else "unclear"
        counts[key] += 1
    return counts


def _log_batch_progress(
    batch_no: int,
    total_batches: int,
    report: SemanticCoverageReport,
) -> None:
    c = _batch_status_counts(report)
    tag = " [降级]" if report.degraded else ""
    print(
        f"   ℹ️ 语义覆盖复核 [{batch_no}/{total_batches}] "
        f"conveyed={c['conveyed']} unclear={c['unclear']} "
        f"missing={c['missing']} contradicted={c['contradicted']}{tag}",
        flush=True,
    )


def _finish_batch(
    *,
    reports: list[SemanticCoverageReport],
    rep: SemanticCoverageReport,
    batch: Sequence[ClaimSpec],
    batch_no: int,
    total_batches: int,
    on_batch_done: OnBatchDone | None,
) -> None:
    reports.append(rep)
    _log_batch_progress(batch_no, total_batches, rep)
    if on_batch_done is not None:
        on_batch_done(batch_no, total_batches, rep, batch)


def merge_semantic_reports(reports: Iterable[SemanticCoverageReport]) -> SemanticCoverageReport:
    merged_claims: list[ClaimResult] = []
    issues: list[str] = []
    summaries: list[str] = []
    passed = True
    degraded = False
    entry_id = ""
    l1_ratio = 0.0
    l1_min_ratio = 0.0
    for rep in reports:
        entry_id = entry_id or rep.entry_id
        l1_ratio = rep.l1_ratio or l1_ratio
        l1_min_ratio = rep.l1_min_ratio or l1_min_ratio
        merged_claims.extend(rep.claims)
        issues.extend(rep.issues)
        if rep.summary:
            summaries.append(rep.summary)
        if rep.degraded:
            degraded = True
        if not rep.passed:
            passed = False
    hard_fail = any(c.status in ("missing", "contradicted") for c in merged_claims)
    if hard_fail:
        passed = False
    return SemanticCoverageReport(
        entry_id=entry_id,
        passed=passed,
        claims=merged_claims,
        summary="；".join(summaries[:3]),
        issues=issues,
        l1_ratio=l1_ratio,
        l1_min_ratio=l1_min_ratio,
        degraded=degraded,
    )


def run_semantic_coverage_batches(
    *,
    entry_id: str,
    entry_name: str,
    detail_text: str,
    claims: Sequence[ClaimSpec],
    llm_call: Callable[[str], str],
    batch_size: int | None = None,
    max_attempts: int = 3,
    l1_ratio: float = 0.0,
    l1_min_ratio: float = 0.0,
    on_batch_done: OnBatchDone | None = None,
) -> SemanticCoverageReport:
    import os

    if not claims:
        return SemanticCoverageReport(
            entry_id=entry_id,
            passed=True,
            summary="无待复核主张",
            l1_ratio=l1_ratio,
            l1_min_ratio=l1_min_ratio,
        )
    if batch_size is None:
        batch_size = int(os.environ.get("TRANSLATE_COVERAGE_L2_BATCH", "6"))
    degrade_on_fail = os.environ.get("TRANSLATE_COVERAGE_L2_DEGRADE", "1") != "0"

    specs = list(claims)
    total_batches = (len(specs) + batch_size - 1) // batch_size
    print(
        f"   ℹ️ 语义覆盖复核开始: {len(specs)} 单元 → {total_batches} 批（每批 ≤{batch_size}）",
        flush=True,
    )
    reports: list[SemanticCoverageReport] = []
    for start in range(0, len(specs), batch_size):
        batch = specs[start : start + batch_size]
        batch_no = start // batch_size + 1
        base_prompt = build_translate_coverage_prompt(
            entry_id=entry_id,
            entry_name=entry_name,
            detail_text=detail_text,
            claims=batch,
        )
        last_err: Exception | None = None
        last_text = ""
        batch_done = False
        for attempt in range(1, max_attempts + 1):
            prompt = base_prompt
            if attempt > 1 and last_text:
                prompt = build_translate_coverage_retry_prompt(
                    base_prompt,
                    bad_output=last_text,
                    error=str(last_err or "输出非 JSON"),
                )
            try:
                last_text = str(llm_call(prompt))
                rep = parse_semantic_coverage_response(last_text, batch)
                rep.entry_id = entry_id
                rep.l1_ratio = l1_ratio
                rep.l1_min_ratio = l1_min_ratio
                _finish_batch(
                    reports=reports,
                    rep=rep,
                    batch=batch,
                    batch_no=batch_no,
                    total_batches=total_batches,
                    on_batch_done=on_batch_done,
                )
                batch_done = True
                break
            except RuntimeError as exc:
                last_err = exc
                if attempt >= max_attempts:
                    if degrade_on_fail:
                        reason = f"L2 语义覆盖批次 {batch_no} 解析失败: {last_err}"
                        _finish_batch(
                            reports=reports,
                            rep=unclear_fallback_report(
                                batch,
                                reason=reason,
                                entry_id=entry_id,
                                l1_ratio=l1_ratio,
                                l1_min_ratio=l1_min_ratio,
                            ),
                            batch=batch,
                            batch_no=batch_no,
                            total_batches=total_batches,
                            on_batch_done=on_batch_done,
                        )
                        batch_done = True
                        break
                    raise RuntimeError(
                        f"L2 语义覆盖批次 {batch_no} 解析失败: {last_err}"
                    ) from exc
        if not batch_done:
            if degrade_on_fail:
                _finish_batch(
                    reports=reports,
                    rep=unclear_fallback_report(
                        batch,
                        reason="L2 语义覆盖未返回有效结果",
                        entry_id=entry_id,
                        l1_ratio=l1_ratio,
                        l1_min_ratio=l1_min_ratio,
                    ),
                    batch=batch,
                    batch_no=batch_no,
                    total_batches=total_batches,
                    on_batch_done=on_batch_done,
                )
            else:
                raise RuntimeError("L2 语义覆盖未返回有效结果")

    merged = merge_semantic_reports(reports)
    merged.entry_id = entry_id
    merged.l1_ratio = l1_ratio
    merged.l1_min_ratio = l1_min_ratio
    c = _batch_status_counts(merged)
    print(
        f"   ℹ️ 语义覆盖复核完成: conveyed={c['conveyed']}/{len(merged.claims)} "
        f"unclear={c['unclear']} missing={c['missing']} contradicted={c['contradicted']}"
        + (" [含降级批次]" if merged.degraded else ""),
        flush=True,
    )
    return merged
