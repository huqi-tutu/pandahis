"""朝代知识详情：参考著作合并与覆盖校验。"""

from __future__ import annotations

import re
from typing import Any

_REF_MARKERS = ("*参考著作", "参考著作")


def strip_reference_section(text: str) -> str:
    body = text
    for marker in _REF_MARKERS:
        if marker in body:
            body = body.split(marker, 1)[0]
    return body.strip()


def extract_book_titles(text: str) -> list[str]:
    return re.findall(r"《([^》]+)》", text)


def parse_index_sources(entry: dict[str, Any]) -> list[str]:
    raw = str(entry.get("主要史料出处") or "").strip()
    if not raw:
        return []
    return [f"《{t}》" for t in extract_book_titles(raw)]


def adopted_bibliography_sources(plan: dict[str, Any] | None) -> list[str]:
    if not plan:
        return []
    refs: list[str] = []
    for item in plan.get("候选著作") or []:
        if not isinstance(item, dict) or not item.get("采用"):
            continue
        src = str(item.get("出处") or "").strip()
        if not src:
            continue
        refs.append(src if src.startswith("《") else f"《{src}》")
    return refs


def _normalize_ref(ref: str) -> str:
    r = ref.strip()
    if not r.startswith("《"):
        r = f"《{r.rstrip('》')}》"
    return r


def _title_key(title: str) -> str:
    t = re.sub(r"\s+", "", title.strip().strip("《》"))
    if "·" in t:
        return t.split("·", 1)[0]
    return t


def dedupe_reference_works(refs: list[str]) -> list[str]:
    """去重：同卷篇只留一条；同一母书的不同卷篇均保留。"""
    mother_plain: dict[str, str] = {}
    for ref in refs:
        r = _normalize_ref(ref)
        inner = r.strip("《》")
        if "·" in inner:
            continue
        key = _title_key(r)
        prev = mother_plain.get(key)
        if prev is None or len(r) > len(prev):
            mother_plain[key] = r

    mothers_with_volume = {
        _title_key(r.strip("《》").split("·", 1)[0])
        for r in (_normalize_ref(x) for x in refs)
        if "·" in r.strip("《》")
    }

    seen: set[str] = set()
    out: list[str] = []
    for ref in refs:
        r = _normalize_ref(ref)
        inner = r.strip("《》")
        if "·" in inner:
            if r in seen:
                continue
            seen.add(r)
            out.append(r)
            continue
        key = _title_key(r)
        if key in mothers_with_volume:
            continue
        best = mother_plain.get(key)
        if not best or best in seen:
            continue
        seen.add(best)
        out.append(best)
    return out


def merge_reference_works(
    entry: dict[str, Any],
    body: str,
    bibliography_plan: dict[str, Any] | None = None,
) -> list[str]:
    """合并索引母本 + 正文实际引用的《书名》（不含未写入正文的 plan 书目）。"""
    _ = bibliography_plan  # 保留参数供后续扩展；当前不以 plan 强行补全
    refs: list[str] = []
    refs.extend(parse_index_sources(entry))
    refs.extend(f"《{t}》" for t in extract_book_titles(body))
    return dedupe_reference_works(refs)


def format_reference_section(refs: list[str]) -> str:
    return f"*参考著作：{''.join(refs)}*"


def attach_reference_section(
    detail_text: str,
    entry: dict[str, Any],
    bibliography_plan: dict[str, Any] | None = None,
) -> str:
    body = strip_reference_section(detail_text)
    refs = merge_reference_works(entry, body, bibliography_plan)
    if not refs:
        return detail_text
    return f"{body.rstrip()}\n\n{format_reference_section(refs)}"


def citation_present(source: str, text: str) -> bool:
    if not source:
        return True
    if source in text:
        return True
    titles = extract_book_titles(source)
    if not titles:
        return False
    for title in titles:
        if f"《{title}》" in text:
            return True
        if f"《{title}·" in text:
            return True
    return False


def _titles_match(a: str, b: str) -> bool:
    if a == b:
        return True
    if _title_key(a) == _title_key(b):
        return True
    if a.startswith(b) or b.startswith(a):
        return True
    return citation_present(f"《{a}》", f"《{b}》") or citation_present(f"《{b}》", f"《{a}》")


def _extract_volume_citations(text: str) -> list[str]:
    """带卷篇的 cite：《书名·卷篇》"""
    return re.findall(r"《([^》]+·[^》]+)》", text)


def _volume_sets_by_mother(titles: list[str]) -> dict[str, set[str]]:
    """{'吕氏春秋': {'贵公', '去私'}}"""
    out: dict[str, set[str]] = {}
    for full in titles:
        if "·" not in full:
            continue
        mother, vol = full.split("·", 1)
        mother = mother.strip()
        vol = vol.strip()
        if mother and vol:
            out.setdefault(mother, set()).add(vol)
    return out


def reference_volume_mismatch_issues(raw_detail: str) -> list[tuple[str, str, str]]:
    """正文与参考著作对同一母书不得出现不同卷篇名（如·贵公 vs ·去私）。"""
    issues: list[tuple[str, str, str]] = []
    if "参考著作" not in raw_detail:
        return issues
    body = strip_reference_section(raw_detail)
    ref_section = raw_detail.split("参考著作", 1)[1]
    body_m = _volume_sets_by_mother(_extract_volume_citations(body))
    ref_m = _volume_sets_by_mother(_extract_volume_citations(ref_section))
    for mother in sorted(set(body_m) & set(ref_m)):
        b_vol = body_m[mother]
        r_vol = ref_m[mother]
        if b_vol != r_vol:
            issues.append(
                (
                    "refs_volume_mismatch",
                    f"正文与参考著作对《{mother}》卷篇不一致："
                    f"正文为{'、'.join(sorted(b_vol))}，"
                    f"参考著作为{'、'.join(sorted(r_vol))}（须同名同卷）",
                    "error",
                )
            )
    return issues


def reference_works_verify_issues(
    raw_detail: str,
    entry: dict[str, Any],
    bibliography_plan: dict[str, Any] | None = None,
) -> list[tuple[str, str, str]]:
    issues: list[tuple[str, str, str]] = []
    if "参考著作" not in raw_detail:
        return issues

    body = strip_reference_section(raw_detail)
    ref_section = raw_detail.split("参考著作", 1)[1]
    ref_titles = extract_book_titles(ref_section)
    body_titles = extract_book_titles(body)

    for title in body_titles:
        if not any(_titles_match(title, rt) for rt in ref_titles):
            issues.append(
                (
                    "refs_missing_body_citation",
                    f"正文引用《{title}》未列入参考著作",
                    "error",
                )
            )

    index_titles = [src.strip("《》") for src in parse_index_sources(entry)]

    for title in ref_titles:
        if any(_titles_match(title, it) for it in index_titles):
            continue
        if not any(_titles_match(title, bt) for bt in body_titles):
            if not citation_present(f"《{title}》", body):
                issues.append(
                    (
                        "refs_orphan",
                        f"参考著作《{title}》未在正文出现",
                        "warn",
                    )
                )

    for src in parse_index_sources(entry):
        title = src.strip("《》")
        if not any(_titles_match(title, rt) for rt in ref_titles):
            issues.append(
                (
                    "refs_missing_index",
                    f"索引主要史料出处 {src} 未列入参考著作",
                    "error",
                )
            )

    issues.extend(reference_volume_mismatch_issues(raw_detail))

    return issues
