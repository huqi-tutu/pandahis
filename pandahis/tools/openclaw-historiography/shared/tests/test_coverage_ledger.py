"""覆盖账本单元测试。"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "historiography-translate"))

from lib.coverage_info import CoverageUnit  # noqa: E402
from lib.coverage_ledger import (  # noqa: E402
    apply_claim_results,
    claim_fingerprint,
    is_conveyed_cached,
    pending_units,
)


def _unit(label: str, info: str, orig: str) -> CoverageUnit:
    row = {"编号": label, "信息点": info, "原文摘句": orig}
    return CoverageUnit(kind="item", items=(row,), label=label)


class TestCoverageLedger(unittest.TestCase):
    def test_pending_skips_conveyed_with_same_fp(self) -> None:
        u1 = _unit("M001", "禹将天下传给益。", "以天下授益。")
        u2 = _unit("M002", "益让位给启。", "益让于启。")
        fp1 = claim_fingerprint(u1)
        entries = {}
        apply_claim_results(entries, claim_id="M001", status="conveyed", claim_fp=fp1)
        pending, fps, cached = pending_units([u1, u2], entries)
        self.assertEqual(cached, {"M001"})
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].label, "M002")
        self.assertTrue(is_conveyed_cached(u1, entries, fp=fp1))

    def test_claim_change_invalidates_cache(self) -> None:
        u1 = _unit("M001", "禹将天下传给益。", "以天下授益。")
        fp_old = claim_fingerprint(u1)
        entries = {}
        apply_claim_results(entries, claim_id="M001", status="conveyed", claim_fp=fp_old)
        u1b = _unit("M001", "禹把天下交给启。", "以天下授启。")
        self.assertFalse(is_conveyed_cached(u1b, entries))


if __name__ == "__main__":
    unittest.main()


class TestFrozenUnits(unittest.TestCase):
    def setUp(self) -> None:
        self._old = os.environ.get("TRANSLATE_COVERAGE_L2_MAX_ATTEMPTS")
        os.environ["TRANSLATE_COVERAGE_L2_MAX_ATTEMPTS"] = "2"

    def tearDown(self) -> None:
        if self._old is None:
            os.environ.pop("TRANSLATE_COVERAGE_L2_MAX_ATTEMPTS", None)
        else:
            os.environ["TRANSLATE_COVERAGE_L2_MAX_ATTEMPTS"] = self._old

    def test_unclear_freezes_after_max_attempts(self) -> None:
        u1 = _unit("M001", "禹将天下传给益。", "以天下授益。")
        fp = claim_fingerprint(u1)
        entries: dict = {}
        apply_claim_results(entries, claim_id="M001", status="unclear", claim_fp=fp)
        pending, _, _ = pending_units([u1], entries)
        self.assertEqual(len(pending), 1)
        apply_claim_results(entries, claim_id="M001", status="unclear", claim_fp=fp)
        self.assertTrue(entries["M001"]["frozen"])
        self.assertEqual(entries["M001"]["attempts"], 2)
        pending, _, _ = pending_units([u1], entries)
        self.assertEqual(pending, [])

    def test_fp_change_unfreezes(self) -> None:
        u1 = _unit("M001", "禹将天下传给益。", "以天下授益。")
        fp = claim_fingerprint(u1)
        entries: dict = {}
        apply_claim_results(entries, claim_id="M001", status="unclear", claim_fp=fp)
        apply_claim_results(entries, claim_id="M001", status="unclear", claim_fp=fp)
        u1b = _unit("M001", "禹把天下交给启。", "以天下授启。")
        pending, _, _ = pending_units([u1b], entries)
        self.assertEqual(len(pending), 1)

    def test_conveyed_never_frozen(self) -> None:
        u1 = _unit("M001", "禹将天下传给益。", "以天下授益。")
        fp = claim_fingerprint(u1)
        entries: dict = {}
        for _ in range(3):
            apply_claim_results(entries, claim_id="M001", status="conveyed", claim_fp=fp)
        self.assertFalse(entries["M001"]["frozen"])
