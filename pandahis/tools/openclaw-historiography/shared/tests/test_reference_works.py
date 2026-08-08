"""reference_works 合并与校验测试。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reference_works import (  # noqa: E402
    attach_reference_section,
    format_reference_section,
    merge_reference_works,
    normalize_detail_references,
    reference_works_verify_issues,
)


def test_merge_from_body_and_index():
    entry = {"主要史料出处": "《史记·五帝本纪》"}
    body = "按《逸周书·尝麦解》的说法，后世《路史》亦有附会。"
    refs = merge_reference_works(entry, body, None)
    titles = "".join(refs)
    assert "史记" in titles
    assert "逸周书" in titles
    assert "路史" in titles


def test_attach_replaces_incomplete_tail():
    entry = {"主要史料出处": "《史记·五帝本纪》"}
    raw = "正文引《逸周书·尝麦解》。\n\n*参考著作：《史记·五帝本纪》*"
    out = attach_reference_section(raw, entry, None)
    assert "逸周书" in out
    assert out.count("参考著作") == 1
    assert "1. 《" in out


def test_format_reference_section_numbered():
    out = format_reference_section(["《史记·五帝本纪》", "《孟子·滕文公上》"])
    assert out.startswith("参考著作：\n")
    assert "1. 《史记·五帝本纪》" in out
    assert "2. 《孟子·滕文公上》" in out
    assert "*" not in out


def test_normalize_legacy_dash_list():
    raw = (
        "正文。\n\n"
        "*参考著作：*\n"
        "- 《史记·五帝本纪》\n"
        "- 《史记·封禅书》"
    )
    out = normalize_detail_references(raw)
    assert "*参考著作" not in out
    assert "1. 《史记·五帝本纪》" in out
    assert "2. 《史记·封禅书》" in out


def test_verify_catches_missing_body_ref():
    entry = {"主要史料出处": "《史记·五帝本纪》"}
    raw = "见《逸周书·尝麦解》。\n\n*参考著作：《史记·五帝本纪》*"
    issues = reference_works_verify_issues(raw, entry, None)
    codes = [c for c, _, _ in issues]
    assert "refs_missing_body_citation" in codes


def test_dedupe_keeps_multiple_volumes_same_mother():
    entry = {"主要史料出处": "《史记·五帝本纪》"}
    body = "见《史记·五帝本纪》与《史记·夏本纪》的记载。"
    refs = merge_reference_works(entry, body, None)
    joined = "".join(refs)
    assert "五帝本纪" in joined
    assert "夏本纪" in joined


def test_dedupe_shangshu_chapter_alias():
    """《康诰》与《尚书·康诰》只保留后者。"""
    from reference_works import dedupe_reference_works

    refs = dedupe_reference_works(
        [
            "《康诰》",
            "《酒诰》",
            "《梓材》",
            "《尚书·康诰》",
            "《尚书·酒诰》",
            "《尚书·梓材》",
        ]
    )
    joined = "".join(refs)
    assert "尚书·康诰" in joined
    assert "《康诰》" not in joined
    assert joined.count("康诰") == 1


def test_merge_weikangshu_no_duplicate_shangshu():
    entry = {"主要史料出处": "《史记·卷37·卫康叔世家》"}
    body = (
        "见《左传·定公四年》及《尚书·康诰》《尚书·酒诰》《尚书·梓材》，"
        "亦言《康诰》《酒诰》《梓材》。"
    )
    refs = merge_reference_works(entry, body, None)
    assert "《康诰》" not in refs
    assert "《尚书·康诰》" in refs


def test_verify_catches_volume_mismatch():
    entry = {"主要史料出处": "《吕氏春秋·贵公》"}
    raw = (
        "据《吕氏春秋·贵公》记载。\n\n"
        "*参考著作：《吕氏春秋·去私》《史记·五帝本纪》*"
    )
    issues = reference_works_verify_issues(raw, entry, None)
    codes = [c for c, _, sev in issues if sev == "error"]
    assert "refs_volume_mismatch" in codes
