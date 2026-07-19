"""语义覆盖检（coverage-check）：主张是否被白话正文传达，不做字面匹配。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import dynasty_supplement_lib as dkl


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
class CoverageReport:
    entry_id: str
    passed: bool
    claims: list[ClaimResult] = field(default_factory=list)
    summary: str = ""
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "dynasty-knowledge-coverage/v1",
            "checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "史略ID": self.entry_id,
            "passed": self.passed,
            "summary": self.summary,
            "claims": [c.to_dict() for c in self.claims],
            "issues": self.issues,
        }


def extract_coverage_claims(anchor: dict[str, Any] | None) -> list[dict[str, str]]:
    """从 anchor 提取主张列表；兼容旧版 checklist / hard_facts。"""
    if not anchor:
        return []
    raw = anchor.get("coverage_claims") or []
    out: list[dict[str, str]] = []
    for i, item in enumerate(raw):
        if isinstance(item, dict):
            cid = str(item.get("id") or f"c{i + 1:02d}")
            claim = str(item.get("claim") or item.get("text") or "").strip()
        else:
            cid = f"c{i + 1:02d}"
            claim = str(item).strip()
        if claim:
            out.append({"id": cid, "claim": claim})
    if out:
        return out[:8]
    for i, line in enumerate(anchor.get("checklist") or []):
        text = str(line).strip()
        if text:
            out.append({"id": f"chk{i + 1:02d}", "claim": text})
    if out:
        return out[:8]
    for i, fact in enumerate(anchor.get("hard_facts") or []):
        if isinstance(fact, dict):
            text = str(fact.get("text") or "").strip()
        else:
            text = str(fact).strip()
        if text:
            out.append({"id": f"hf{i + 1:02d}", "claim": text})
    return out[:8]


def format_claims_for_compose(anchor: dict[str, Any] | None) -> str:
    """compose prompt 注入块：主张 + 禁止 + 传说。"""
    if not anchor:
        return ""
    lines = ["## 须传达的主张（语义覆盖即可，勿复述 anchor 原句）"]
    claims = extract_coverage_claims(anchor)
    if claims:
        for c in claims:
            lines.append(f"- [{c['id']}] {c['claim']}")
    else:
        lines.append("- （无）")
    forbidden = anchor.get("forbidden_inventions") or []
    if forbidden:
        lines.extend(["", "## 禁止编造"])
        for f in forbidden:
            lines.append(f"- {f}")
    legends = anchor.get("legend_facts") or []
    if legends:
        lines.extend(["", "## 传说/异说（须标注层级，不可当家史）"])
        for leg in legends:
            text = leg.get("text") if isinstance(leg, dict) else str(leg)
            lines.append(f"- {text}")
    return "\n".join(lines) + "\n"


def _normalize_claim_id(cid: str) -> str:
    """c01 / chk01 / hf01 → 数值后缀，便于跨前缀对齐。"""
    m = re.search(r"(\d+)$", str(cid))
    if not m:
        return str(cid)
    return str(int(m.group(1)))


def _row_for_claim(
    spec: dict[str, str],
    index: int,
    *,
    by_id: dict[str, dict[str, Any]],
    by_norm: dict[str, dict[str, Any]],
    llm_claims: list[dict[str, Any]],
    used_indices: set[int],
) -> dict[str, Any]:
    """按 id 精确 → 数值后缀 → 同序位置 对齐 LLM 返回行。"""
    cid = spec["id"]
    if cid in by_id:
        return by_id[cid]
    norm = _normalize_claim_id(cid)
    if norm in by_norm:
        return by_norm[norm]
    if index < len(llm_claims) and index not in used_indices:
        row = llm_claims[index]
        if isinstance(row, dict):
            used_indices.add(index)
            return row
    return {}


def build_coverage_check_prompt(
    entry: dict[str, Any],
    detail_text: str,
    anchor: dict[str, Any] | None,
) -> str:
    claims = extract_coverage_claims(anchor)
    body = dkl.strip_detail_body(detail_text)
    claims_json = json.dumps(claims, ensure_ascii=False, indent=2)
    forbidden = (anchor or {}).get("forbidden_inventions") or []
    id_list = "、".join(c["id"] for c in claims)
    example_json = json.dumps(
        [
            {
                "id": c["id"],
                "status": "conveyed",
                "evidence": "正文依据一句",
                "note": "",
            }
            for c in claims
        ],
        ensure_ascii=False,
        indent=4,
    )
    return f"""你是史实覆盖质检员。详情为**白话叙事**，不要求出现 anchor 原词；只判断「主张是否被传达」。

## 条目
{json.dumps({k: entry.get(k) for k in ('史略ID', '史略名称', '史略分类', '主要史料出处')}, ensure_ascii=False, indent=2)}

## 须传达的主张
{claims_json}

## 禁止编造（若正文出现则 contradicted）
{json.dumps(forbidden, ensure_ascii=False)}

## 正文
{body}

## 判定纪律
- **conveyed**：白话改写也算；读者能get到同一信息即可
- **missing**：完全未涉及或过于模糊
- **contradicted**：与主张或 forbidden 明显矛盾
- **unclear**：疑似写到但无法确认
- 不得因未出现古籍原词、未出现 anchor 关键词而判 missing
- **每条结果的 id 必须与上表完全一致**（允许的值：{id_list}；禁止改用 c01/chk01 等其他编号）

只输出 JSON：
{{
  "claims": {example_json},
  "summary": "一句总评",
  "passed": true
}}

passed=true 当且仅当：无 missing、无 contradicted；unclear 最多 1 条。"""


def parse_coverage_response(text: str, claims: list[dict[str, str]]) -> CoverageReport:
    data = dkl.extract_json_object(text)
    if not data:
        raise RuntimeError("coverage-check 输出非 JSON")
    llm_claims = [c for c in (data.get("claims") or []) if isinstance(c, dict)]
    by_id = {str(c.get("id")): c for c in llm_claims if c.get("id") is not None}
    by_norm: dict[str, dict[str, Any]] = {}
    for key, row in by_id.items():
        by_norm[_normalize_claim_id(key)] = row
    used_indices: set[int] = set()
    results: list[ClaimResult] = []
    issues: list[str] = []
    for i, spec in enumerate(claims):
        cid = spec["id"]
        row = _row_for_claim(
            spec,
            i,
            by_id=by_id,
            by_norm=by_norm,
            llm_claims=llm_claims,
            used_indices=used_indices,
        )
        status = str(row.get("status") or "missing").lower()
        if status not in ("conveyed", "missing", "contradicted", "unclear"):
            status = "unclear"
        cr = ClaimResult(
            claim_id=cid,
            claim=spec["claim"],
            status=status,
            evidence=str(row.get("evidence") or "")[:200],
            note=str(row.get("note") or "")[:200],
        )
        results.append(cr)
        if status == "missing":
            issues.append(f"missing [{cid}]: {spec['claim'][:60]}")
        elif status == "contradicted":
            issues.append(f"contradicted [{cid}]: {spec['claim'][:60]}")
        elif status == "unclear":
            issues.append(f"unclear [{cid}]: {spec['claim'][:60]}")
    unclear_n = sum(1 for r in results if r.status == "unclear")
    hard_fail = any(r.status in ("missing", "contradicted") for r in results)
    passed = bool(data.get("passed")) if "passed" in data else (not hard_fail and unclear_n <= 1)
    if hard_fail:
        passed = False
    elif not hard_fail and unclear_n <= 1 and any(r.status == "conveyed" for r in results):
        passed = True
    return CoverageReport(
        entry_id="",
        passed=passed,
        claims=results,
        summary=str(data.get("summary") or ""),
        issues=issues,
    )


def coverage_artifact_path(logs_dir: Path, entry_id: str) -> Path:
    return logs_dir / "coverage" / f"{entry_id}_coverage.json"


def save_coverage_artifact(logs_dir: Path, entry_id: str, report: CoverageReport) -> Path:
    report.entry_id = entry_id
    path = coverage_artifact_path(logs_dir, entry_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def run_coverage_check_llm(
    entry: dict[str, Any],
    detail: dict[str, Any],
    *,
    anchor: dict[str, Any] | None,
    prompt: str | None = None,
    timeout_sec: int = 600,
    max_attempts: int = 3,
) -> CoverageReport:
    claims = extract_coverage_claims(anchor)
    if not claims:
        return CoverageReport(
            entry_id=str(entry.get("史略ID") or ""),
            passed=True,
            summary="无 coverage_claims，跳过",
        )
    body = str(detail.get("翻译详情") or "")
    if prompt is None:
        prompt = build_coverage_check_prompt(entry, body, anchor)
    eid = str(entry.get("史略ID") or "")
    last_err: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            text = dkl.call_llm(
                prompt,
                session_prefix=f"dk-cov-{eid}-a{attempt}-",
                timeout_sec=timeout_sec,
                temperature=0,
            )
            report = parse_coverage_response(str(text), claims)
            report.entry_id = eid
            return report
        except RuntimeError as exc:
            last_err = exc
            if attempt < max_attempts:
                continue
    raise RuntimeError(
        f"coverage-check 在 {max_attempts} 次尝试后仍无法解析 JSON"
        f"（{last_err}）"
    ) from last_err
