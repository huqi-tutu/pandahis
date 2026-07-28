"""必现词硬锚点：小样本不用比例误杀。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "historiography-translate"))

from lib.verify import (  # noqa: E402
    _must_phrase_block_decision,
    _verify_must_phrases,
)


def test_small_sample_one_miss_does_not_block() -> None:
    should_block, *_ = _must_phrase_block_decision(total=1, hits=0, checklist_size=80)
    assert should_block is False


def test_small_sample_three_misses_do_not_block() -> None:
    should_block, *_ = _must_phrase_block_decision(total=3, hits=0, checklist_size=80)
    assert should_block is False


def test_small_sample_four_misses_blocks() -> None:
    should_block, *_ = _must_phrase_block_decision(total=4, hits=0, checklist_size=80)
    assert should_block is True


def test_large_sample_uses_ratio() -> None:
    should_block, ratio, min_ratio, misses = _must_phrase_block_decision(
        total=10, hits=3, checklist_size=40
    )
    assert misses == 7
    assert ratio == 0.3
    assert should_block is (ratio < min_ratio)


def test_verify_empty_when_one_miss_small_total() -> None:
    plan = {
        "母本逐句清单": [
            {
                "编号": "M001",
                "原文摘句": "威胁韩、魏、赵氏，北有甘泉",
                "必现词": ["赵氏"],
            }
        ]
    }
    detail = "秦王之地遍天下，威胁韩国与魏国，北边有甘泉关隘。"
    assert _verify_must_phrases(detail, plan) == []
