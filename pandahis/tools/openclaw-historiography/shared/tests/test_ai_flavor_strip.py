"""AI 腔脚本降频。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.ai_flavor_words import (  # noqa: E402
    AI_FLAVOR_WORD_FAIL_AT,
    ai_flavor_verify_issues,
    strip_ai_flavor_excess,
)


def test_strip_ai_flavor_excess_single_word() -> None:
    body = "可谓" * 6
    fixed, changes = strip_ai_flavor_excess(body)
    assert fixed.count("可谓") < AI_FLAVOR_WORD_FAIL_AT
    assert changes
    assert not ai_flavor_verify_issues(fixed)


def test_strip_ai_flavor_excess_total() -> None:
    body = "此外，堪称，可谓，则是，注定"
    fixed, changes = strip_ai_flavor_excess(body)
    assert not ai_flavor_verify_issues(fixed)
    assert changes
