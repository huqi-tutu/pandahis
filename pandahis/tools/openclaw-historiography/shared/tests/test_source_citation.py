"""source_citation 校验测试。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from source_citation import (  # noqa: E402
    curved_quote_after_source_citation_issues,
    nested_corner_ascii_quote_issues,
    source_citation_verify_issues,
    verified_snippet_quote_issues,
)


def test_curved_quote_after_cite_is_error():
    body = '《山海经》里写的是"黄帝妻雷祖，生昌意"，雷祖就是嫘祖。'
    issues = curved_quote_after_source_citation_issues(body)
    assert issues and issues[0][0] == "source_curved_quote"


def test_corner_quote_after_cite_ok():
    body = '《山海经》载「黄帝妻雷祖，生昌意」——雷祖就是嫘祖。'
    assert not curved_quote_after_source_citation_issues(body)


def test_mencius_dialogue_curved_quote_ok():
    body = '《孟子·万章上》记载，公孙丑问：“有伊尹之志则可，无伊尹之志则篡也。”'
    assert not curved_quote_after_source_citation_issues(body)


def test_nested_corner_ascii_is_error():
    body = '汤说：「"予有言：人视水见形"」——译述。'
    issues = nested_corner_ascii_quote_issues(body)
    assert issues and issues[0][0] == "nested_corner_quote"


def test_verified_snippet_must_be_in_corner_quotes():
    body = "正文仅白话转述黄帝居轩辕之丘，而无摘句。"
    plan = {
        "候选著作": [
            {
                "snippet_verified": True,
                "原文摘句": "黄帝居轩辕之丘，而娶于西陵之女，是为嫘祖",
                "出处": "《史记·五帝本纪》",
            }
        ]
    }
    codes = [c for c, _, _ in verified_snippet_quote_issues(body, plan)]
    assert "verified_snippet_missing" in codes or "verified_snippet_not_quoted" in codes


def test_verified_snippet_skips_non_adopted():
    body = "正文未引用山海经神话摘句。"
    plan = {
        "候选著作": [
            {
                "采用": False,
                "snippet_verified": True,
                "原文摘句": "洪水滔天，鲧窃帝之息壤以湮洪水",
                "出处": "《山海经·海内经》",
            }
        ]
    }
    assert not verified_snippet_quote_issues(body, plan)


def test_density_warn_when_many_cites_no_quotes():
    body = "见《史记·五帝本纪》与《尚书·尧典》及《孟子·万章上》与《荀子·正论》与《论语·泰伯》的记载。"
    codes = [c for c, _, s in source_citation_verify_issues(body, priority="P1") if s == "warn"]
    assert "missing_source_quotes" in codes
