"""L2 语义覆盖（shared）单元测试。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shared.coverage_semantic import (  # noqa: E402
    ClaimSpec,
    parse_semantic_coverage_response,
    should_trigger_l2,
)


class TestShouldTriggerL2(unittest.TestCase):
    def test_passed_l1_skips(self) -> None:
        self.assertFalse(
            should_trigger_l2(
                checklist_size=100,
                ratio=0.72,
                min_ratio=0.70,
                enabled=True,
            )
        )

    def test_too_low_skips(self) -> None:
        self.assertFalse(
            should_trigger_l2(
                checklist_size=100,
                ratio=0.50,
                min_ratio=0.70,
                enabled=True,
                gray_band=0.12,
            )
        )

    def test_gray_zone_triggers(self) -> None:
        self.assertTrue(
            should_trigger_l2(
                checklist_size=100,
                ratio=0.63,
                min_ratio=0.70,
                enabled=True,
                gray_band=0.12,
                min_checklist=50,
            )
        )

    def test_short_text_skips(self) -> None:
        self.assertFalse(
            should_trigger_l2(
                checklist_size=20,
                ratio=0.63,
                min_ratio=0.70,
                enabled=True,
                gray_band=0.12,
                min_checklist=50,
            )
        )


class TestParseSemanticResponse(unittest.TestCase):
    def test_parse_conveyed_batch(self) -> None:
        claims = [ClaimSpec("M001", "禹令益分稻种")]
        text = """```json
{
  "claims": [{"id": "M001", "status": "conveyed", "evidence": "文中有分稻种", "note": ""}],
  "summary": "ok",
  "passed": true
}
```"""
        rep = parse_semantic_coverage_response(text, claims)
        self.assertTrue(rep.passed)
        self.assertEqual(rep.claims[0].status, "conveyed")
        self.assertIn("M001", rep.conveyed_ids)


if __name__ == "__main__":
    unittest.main()
