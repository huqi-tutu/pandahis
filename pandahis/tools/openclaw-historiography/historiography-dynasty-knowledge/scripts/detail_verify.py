"""详情 Python 硬检（Phase C verify）：规则见 reference/详情撰写规则.md §七。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import dynasty_supplement_lib as dkl


@dataclass
class VerifyIssue:
    code: str
    message: str
    severity: str = "error"  # error | warn

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message, "severity": self.severity}


@dataclass
class VerifyReport:
    entry_id: str
    passed: bool
    issues: list[VerifyIssue] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "dynasty-knowledge-verify/v1",
            "verified_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "史略ID": self.entry_id,
            "passed": self.passed,
            "issues": [i.to_dict() for i in self.issues],
            "metrics": self.metrics,
        }


def _count_sentences(paragraph: str) -> int:
    parts = re.split(r"[。！？!?]", paragraph)
    return len([p for p in parts if p.strip()])


def _anchor_keywords(fact: Any) -> list[str]:
    if isinstance(fact, dict):
        kws = fact.get("keywords") or []
        if kws:
            return [str(k).strip() for k in kws if str(k).strip()]
        text = str(fact.get("text") or "")
    else:
        text = str(fact)
    text = re.sub(r"《[^》]+》", "", text)
    tokens = re.findall(r"[\u4e00-\u9fff]{2,6}", text)
    return tokens[:4]


def _body_contains_keywords(body: str, keywords: list[str]) -> bool:
    if not keywords:
        return True
    hits = sum(1 for kw in keywords if kw and kw in body)
    return hits >= max(1, len(keywords) // 2)


def verify_detail(
    entry: dict[str, Any],
    detail: dict[str, Any],
    *,
    anchor: dict[str, Any] | None = None,
) -> VerifyReport:
    """程序化质检；返回 VerifyReport（passed = 无 error 级 issue）。"""
    eid = str(entry.get("史略ID") or detail.get("史略ID") or "?")
    cat = dkl.normalize_category(str(entry.get("史略分类") or ""))
    pri = str(entry.get("优先级") or "P1")
    raw = str(detail.get("翻译详情") or "")
    body = dkl.strip_detail_body(raw)
    issues: list[VerifyIssue] = []

    if not body.strip():
        issues.append(VerifyIssue("empty_body", "详情正文为空"))
        return VerifyReport(entry_id=eid, passed=False, issues=issues)

    # 参考著作
    if "参考著作" not in raw:
        issues.append(VerifyIssue("missing_refs", "缺少文末「参考著作」"))

    # 禁词
    for word in dkl.FORBIDDEN_PROSE_WORDS:
        if word in body:
            issues.append(VerifyIssue("forbidden_word", f"含禁词「{word}」"))

    # 【】
    if "【" in body or "】" in body:
        issues.append(VerifyIssue("forbidden_brackets", "禁止【】引文标记"))

    # 注音
    for pin in dkl.detect_over_pinyin(body):
        issues.append(VerifyIssue("over_pinyin", f"多余注音：{pin}"))

    # 小标题 / 列表符号
    if re.search(r"^#{1,6}\s", body, re.MULTILINE):
        issues.append(VerifyIssue("markdown_heading", "禁止 Markdown 小标题"))
    if re.search(r"^[\s]*[-*•]\s", body, re.MULTILINE):
        issues.append(VerifyIssue("list_marker", "禁止列表符号段落"))
    if re.search(r"^第[一二三四五六七八九十\d]+[，,、]", body, re.MULTILINE):
        issues.append(VerifyIssue("numbered_section", "禁止「第一，…」式分节"))

    # 字数
    density = dkl.resolve_source_density(entry, anchor)
    floor = dkl.detail_effective_floor(cat, pri, entry, anchor)
    char_count = len(body)
    if char_count < floor:
        wc_issue = VerifyIssue(
            "word_count",
            f"正文 {char_count} 字 < effective_floor {floor}（{density}）",
        )
        if density in ("S0", "S1") and char_count >= int(floor * 0.85):
            wc_issue.severity = "warn"
        issues.append(wc_issue)

    # 段落
    paragraphs = dkl.split_detail_paragraphs(raw)
    min_para = dkl.MIN_PARAGRAPHS_BY_PRIORITY.get(pri, 5)
    if len(paragraphs) < min_para:
        issues.append(
            VerifyIssue(
                "paragraph_count",
                f"段落 {len(paragraphs)} < 下限 {min_para}（含开篇引入）",
            )
        )

    # 连续单句碎段
    streak = 0
    for para in paragraphs:
        if _count_sentences(para) <= 1 and len(para) < 80:
            streak += 1
            if streak >= 3:
                issues.append(VerifyIssue("single_sentence_streak", "连续 3 段以上单句碎段"))
                break
        else:
            streak = 0

    # 锚点 hard_facts 覆盖
    if anchor:
        missing_facts: list[str] = []
        for fact in anchor.get("hard_facts") or []:
            kws = _anchor_keywords(fact)
            if not _body_contains_keywords(body, kws):
                label = fact.get("text") if isinstance(fact, dict) else str(fact)
                missing_facts.append(str(label)[:40])
        if missing_facts:
            issues.append(
                VerifyIssue(
                    "anchor_hard_facts",
                    f"hard_facts 未覆盖 {len(missing_facts)} 条："
                    + "；".join(missing_facts[:3]),
                )
            )

        for enum in anchor.get("core_enumerations") or []:
            if not isinstance(enum, dict):
                continue
            items = enum.get("items") or []
            label = str(enum.get("label") or enum.get("name") or "核心列举")
            missing_items: list[str] = []
            for item in items:
                item_s = str(item)
                token = item_s.split("-")[0].split("：")[0].split(":")[0].strip()
                if token and token not in body and item_s not in body:
                    missing_items.append(item_s[:20])
            min_need = int(enum.get("min_mentions") or len(items))
            covered = len(items) - len(missing_items)
            if items and covered < min_need:
                sev = "warn" if len(items) > 6 else "error"
                issues.append(
                    VerifyIssue(
                        "core_enumeration",
                        f"「{label}」仅覆盖 {covered}/{len(items)} 项",
                        severity=sev,
                    )
                )
    elif str(entry.get("朝代ID", "")) == "CD_HX_WUDI":
        issues.append(
            VerifyIssue(
                "missing_anchor",
                "五帝补全建议先跑 anchor-research 产出锚点",
                severity="warn",
            )
        )

    passed = not any(i.severity == "error" for i in issues)
    metrics = {
        "char_count": char_count,
        "effective_floor": floor,
        "source_density": density,
        "paragraph_count": len(paragraphs),
        "min_paragraphs": min_para,
    }
    return VerifyReport(entry_id=eid, passed=passed, issues=issues, metrics=metrics)


def format_verify_issues(report: VerifyReport) -> list[str]:
    return [
        f"[{report.entry_id}] ({i.severity}) {i.code}: {i.message}"
        for i in report.issues
    ]
