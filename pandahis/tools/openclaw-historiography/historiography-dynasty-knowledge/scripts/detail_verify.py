"""详情 Python 硬检（Phase C verify）：规则见 reference/详情撰写规则.md §七。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import dynasty_supplement_lib as dkl
from shared.legend_quota import analyze_legend_quota, legend_quota_verify_issues
from shared.reference_works import reference_works_verify_issues
from shared.source_citation import source_citation_verify_issues


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
    bibliography_plan: dict[str, Any] | None = None,
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
    else:
        for code, message, severity in reference_works_verify_issues(
            raw, entry, bibliography_plan
        ):
            issues.append(VerifyIssue(code, message, severity=severity))

    # AI 腔词频（非 100% 禁用，见 shared/ai_flavor_words.py）
    for code, message, severity in dkl.ai_flavor_verify_issues(body):
        issues.append(VerifyIssue(code, message, severity=severity))

    for code, message, severity in legend_quota_verify_issues(body, priority=pri):
        issues.append(VerifyIssue(code, message, severity=severity))

    for code, message, severity in source_citation_verify_issues(
        body,
        bibliography_plan=bibliography_plan,
        priority=pri,
    ):
        issues.append(VerifyIssue(code, message, severity=severity))

    # 元叙述 / 编辑腔（交付物 §0.3）
    for phrase in dkl.FORBIDDEN_META_PHRASES:
        if phrase in body:
            issues.append(VerifyIssue("meta_prose", f"含元叙述/编辑腔「{phrase}」"))

    # 【】
    if "【" in body or "】" in body:
        issues.append(VerifyIssue("forbidden_brackets", "禁止【】引文标记"))

    # Markdown 加粗（小程序仅对「」『』内原文自动加粗）
    if re.search(r"\*\*[^*]+\*\*", body):
        issues.append(
            VerifyIssue(
                "markdown_bold",
                "禁止 ** Markdown 加粗；史料原文请用直角引号「」，由小程序自动加粗",
            )
        )

    # 注音括注（后处理硬检，prompt 不提）
    for pin in dkl.detect_over_pinyin(body):
        issues.append(VerifyIssue("over_pinyin", f"多余括注：{pin}"))

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

    paragraphs = dkl.split_detail_paragraphs(raw)
    # 段落数下限校验已移除（不再以段数硬卡 gate/verify）

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

    # 锚点覆盖改由 coverage-check（语义）负责；此处不再做字面匹配
    if anchor:
        if not (
            anchor.get("coverage_claims")
            or anchor.get("checklist")
            or anchor.get("hard_facts")
        ):
            issues.append(
                VerifyIssue(
                    "missing_coverage_claims",
                    "锚点缺少 coverage_claims（或 legacy checklist/hard_facts）",
                    severity="warn",
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

    legend_m = analyze_legend_quota(body)
    if cat == "典制":
        story_hits = sum(body.count(t) for t in ("尧", "舜", "丹朱", "禹", "鲧"))
        inst_hits = sum(
            body.count(t)
            for t in ("制度", "程序", "规则", "运作", "推举", "摄政", "合法性", "共主")
        )
        if story_hits >= 12 and story_hits > inst_hits * 2:
            issues.append(
                VerifyIssue(
                    "category_drift",
                    f"典制条目人物叙事（尧舜等 {story_hits} 处）明显多于制度表述"
                    f"（{inst_hits} 处），疑似写成事略",
                    severity="error",
                )
            )

    passed = not any(i.severity == "error" for i in issues)
    metrics = {
        "char_count": char_count,
        "effective_floor": floor,
        "source_density": density,
        "paragraph_count": len(paragraphs),
        "legend_trigger_count": legend_m.trigger_count,
        "legend_char_ratio": round(legend_m.legend_char_ratio, 3),
    }
    return VerifyReport(entry_id=eid, passed=passed, issues=issues, metrics=metrics)


def format_verify_issues(report: VerifyReport) -> list[str]:
    return [
        f"[{report.entry_id}] ({i.severity}) {i.code}: {i.message}"
        for i in report.issues
    ]
