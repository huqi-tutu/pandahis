"""语义覆盖检（L2）：判断白话正文是否传达主张，不做字面匹配。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Sequence


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

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "translate-coverage-l2/v1",
            "史略ID": self.entry_id,
            "passed": self.passed,
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


def build_translate_coverage_prompt(
    *,
    entry_id: str,
    entry_name: str,
    detail_text: str,
    claims: Sequence[ClaimSpec],
) -> str:
    body = strip_detail_body(detail_text)
    claims_json = json.dumps([c.to_dict() for c in claims], ensure_ascii=False, indent=2)
    id_list = "、".join(c.claim_id for c in claims)
    example_json = json.dumps(
        [
            {
                "id": c.claim_id,
                "status": "conveyed",
                "evidence": "正文依据一句",
                "note": "",
            }
            for c in claims
        ],
        ensure_ascii=False,
        indent=4,
    )
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
- 每条结果的 id 必须与上表完全一致（允许：{id_list}）

只输出 JSON：
{{
  "claims": {example_json},
  "summary": "一句总评",
  "passed": true
}}

passed=true 当且仅当：本批无 missing、无 contradicted；unclear 最多 1 条。"""


def _normalize_claim_id(cid: str) -> str:
    m = re.search(r"(\d+)$", str(cid))
    if not m:
        return str(cid)
    return str(int(m.group(1)))


def _extract_json_object(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    if stripped.startswith("{"):
        try:
            data = json.loads(stripped)
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            pass
    for block in re.findall(r"```json\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE):
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
            return None
    return None


def parse_semantic_coverage_response(
    text: str,
    claims: Sequence[ClaimSpec],
) -> SemanticCoverageReport:
    data = _extract_json_object(text)
    if not data:
        raise RuntimeError("L2 语义覆盖输出非 JSON")

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

        status = str(row.get("status") or "missing").lower()
        if status not in ("conveyed", "missing", "contradicted", "unclear"):
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

    unclear_n = sum(1 for r in results if r.status == "unclear")
    hard_fail = any(r.status in ("missing", "contradicted") for r in results)
    passed = bool(data.get("passed")) if "passed" in data else (not hard_fail and unclear_n <= 1)
    if hard_fail:
        passed = False

    return SemanticCoverageReport(
        entry_id="",
        passed=passed,
        claims=results,
        summary=str(data.get("summary") or ""),
        issues=issues,
    )


def merge_semantic_reports(reports: Iterable[SemanticCoverageReport]) -> SemanticCoverageReport:
    merged_claims: list[ClaimResult] = []
    issues: list[str] = []
    summaries: list[str] = []
    passed = True
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
    )


def run_semantic_coverage_batches(
    *,
    entry_id: str,
    entry_name: str,
    detail_text: str,
    claims: Sequence[ClaimSpec],
    llm_call: Callable[[str], str],
    batch_size: int | None = None,
    max_attempts: int = 2,
    l1_ratio: float = 0.0,
    l1_min_ratio: float = 0.0,
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
        batch_size = int(os.environ.get("TRANSLATE_COVERAGE_L2_BATCH", "12"))

    specs = list(claims)
    reports: list[SemanticCoverageReport] = []
    for start in range(0, len(specs), batch_size):
        batch = specs[start : start + batch_size]
        prompt = build_translate_coverage_prompt(
            entry_id=entry_id,
            entry_name=entry_name,
            detail_text=detail_text,
            claims=batch,
        )
        last_err: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                text = llm_call(prompt)
                rep = parse_semantic_coverage_response(str(text), batch)
                rep.entry_id = entry_id
                rep.l1_ratio = l1_ratio
                rep.l1_min_ratio = l1_min_ratio
                reports.append(rep)
                break
            except RuntimeError as exc:
                last_err = exc
                if attempt >= max_attempts:
                    raise RuntimeError(
                        f"L2 语义覆盖批次 {start // batch_size + 1} 解析失败: {last_err}"
                    ) from exc
        else:
            raise RuntimeError("L2 语义覆盖未返回有效结果")

    merged = merge_semantic_reports(reports)
    merged.entry_id = entry_id
    merged.l1_ratio = l1_ratio
    merged.l1_min_ratio = l1_min_ratio
    return merged
