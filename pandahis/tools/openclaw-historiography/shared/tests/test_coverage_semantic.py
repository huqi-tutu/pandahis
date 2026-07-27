"""L2 语义覆盖（shared）单元测试。"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shared.coverage_semantic import (  # noqa: E402
    ClaimSpec,
    build_coverage_response_skeleton,
    build_translate_coverage_prompt,
    parse_semantic_coverage_response,
    run_semantic_coverage_batches,
    should_trigger_l2,
    unclear_fallback_report,
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

    def test_parse_trailing_garbage(self) -> None:
        claims = [ClaimSpec("M001", "禹令益分稻种")]
        text = '{"claims": [{"id": "M001", "status": "conveyed", "evidence": "x", "note": ""}], "summary": "ok", "passed": true} 以上。'
        rep = parse_semantic_coverage_response(text, claims)
        self.assertEqual(rep.claims[0].status, "conveyed")

    def test_empty_status_becomes_unclear(self) -> None:
        claims = [ClaimSpec("M001", "禹令益分稻种")]
        text = json.dumps(
            {
                "claims": [{"id": "M001", "status": "", "evidence": "", "note": ""}],
                "summary": "",
                "passed": False,
            },
            ensure_ascii=False,
        )
        rep = parse_semantic_coverage_response(text, claims)
        self.assertEqual(rep.claims[0].status, "unclear")


class TestCoverageSkeleton(unittest.TestCase):
    def test_skeleton_in_prompt(self) -> None:
        claims = [ClaimSpec("M001", "a"), ClaimSpec("M002", "b")]
        prompt = build_translate_coverage_prompt(
            entry_id="GLBL_00001",
            entry_name="测试",
            detail_text="正文",
            claims=claims,
        )
        self.assertIn("待填 JSON 骨架", prompt)
        self.assertIn('"id": "M001"', prompt)
        self.assertIn('"status": ""', prompt)
        self.assertIn("禁止增删 claims", prompt)


class TestDegradeFallback(unittest.TestCase):
    def test_unclear_fallback(self) -> None:
        claims = [ClaimSpec("M001", "a"), ClaimSpec("M002", "b")]
        rep = unclear_fallback_report(claims, reason="parse fail")
        self.assertTrue(rep.degraded)
        self.assertEqual({c.status for c in rep.claims}, {"unclear"})

    def test_run_batches_degrade_on_bad_json(self) -> None:
        claims = [ClaimSpec("M001", "a")]

        def bad_llm(_prompt: str) -> str:
            return "这不是 JSON"

        rep = run_semantic_coverage_batches(
            entry_id="GLBL_00001",
            entry_name="测试",
            detail_text="正文",
            claims=claims,
            llm_call=bad_llm,
            max_attempts=1,
        )
        self.assertTrue(rep.degraded)
        self.assertEqual(rep.claims[0].status, "unclear")

    def test_batch_progress_callback(self) -> None:
        claims = [ClaimSpec("M001", "a")]
        seen: list[int] = []

        def ok_llm(_prompt: str) -> str:
            return json.dumps(
                {
                    "claims": [
                        {"id": "M001", "status": "conveyed", "evidence": "x", "note": ""}
                    ],
                    "summary": "ok",
                    "passed": True,
                },
                ensure_ascii=False,
            )

        def on_done(batch_no: int, total: int, _rep, _batch) -> None:
            seen.append(batch_no)
            self.assertEqual(total, 1)

        run_semantic_coverage_batches(
            entry_id="GLBL_00001",
            entry_name="测试",
            detail_text="正文",
            claims=claims,
            llm_call=ok_llm,
            on_batch_done=on_done,
        )
        self.assertEqual(seen, [1])


if __name__ == "__main__":
    unittest.main()
