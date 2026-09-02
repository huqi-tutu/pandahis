"""verify 分级单元测试。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRANSLATE = ROOT / "historiography-translate"
if str(TRANSLATE) not in sys.path:
    sys.path.insert(0, str(TRANSLATE))

from lib.verify_tiers import partition_verify_errors  # noqa: E402


class TestVerifyTiers(unittest.TestCase):
    def test_ai_flavor_becomes_ticket(self) -> None:
        errs = ["AI 腔词「此外」出现 5 次 ≥ 5（单篇最多 4 次）"]
        blocks, tickets, _ = partition_verify_errors(errs)
        self.assertEqual(blocks, [])
        self.assertEqual(len(tickets), 1)

    def test_json_missing_stays_block(self) -> None:
        errs = ["缺少字段: ['史料原文']"]
        blocks, tickets, _ = partition_verify_errors(errs)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(tickets, [])

    def test_coverage_ticket_when_report_mode(self) -> None:
        errs = ["母本顺译 覆盖不足: 传达率 0.65"]
        blocks, tickets, _ = partition_verify_errors(
            errs,
            coverage_report=True,
        )
        self.assertEqual(blocks, [])
        self.assertEqual(len(tickets), 1)


if __name__ == "__main__":
    unittest.main()
