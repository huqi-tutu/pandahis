"""汉书头段修复：同步收缩 entries 段落范围。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.hanshu_autofix import _trim_entry_paragraph_ranges  # noqa: E402


def test_trim_entry_paragraph_ranges_skips_excluded_header():
    attr_map = {
        2: {"paragraph": 2, "owners": [], "exclude_reason": "篇内小标题"},
        3: {"paragraph": 3, "owners": [{"name": "刘钦", "category": "宗戚"}]},
        4: {"paragraph": 4, "owners": [{"name": "刘钦", "category": "宗戚"}]},
        5: {"paragraph": 5, "owners": [{"name": "刘钦", "category": "宗戚"}]},
    }
    entries = [
        {
            "史略名称": "刘钦",
            "史略分类": "宗戚",
            "paragraphs": [{"volume": "宣元六王传", "paragraph_from": 2, "paragraph_to": 5}],
        }
    ]
    fixes = _trim_entry_paragraph_ranges(entries, attr_map)
    assert fixes == ["刘钦 P2-P5→P3-P5"]
    assert entries[0]["paragraphs"] == [
        {"volume": "宣元六王传", "paragraph_from": 3, "paragraph_to": 5}
    ]


def test_trim_entry_paragraph_ranges_keeps_matching_range():
    attr_map = {
        3: {"paragraph": 3, "owners": [{"name": "刘钦", "category": "宗戚"}]},
        4: {"paragraph": 4, "owners": [{"name": "刘钦", "category": "宗戚"}]},
    }
    entries = [
        {
            "史略名称": "刘钦",
            "史略分类": "宗戚",
            "paragraphs": [{"volume": "宣元六王传", "paragraph_from": 3, "paragraph_to": 4}],
        }
    ]
    fixes = _trim_entry_paragraph_ranges(entries, attr_map)
    assert fixes == []
    assert entries[0]["paragraphs"][0]["paragraph_from"] == 3


if __name__ == "__main__":
    test_trim_entry_paragraph_ranges_skips_excluded_header()
    test_trim_entry_paragraph_ranges_keeps_matching_range()
    print("ok")
