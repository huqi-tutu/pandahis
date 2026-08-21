"""浅释 / L0 禁释检测单元测试。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRANSLATE = ROOT / "historiography-translate"
sys.path.insert(0, str(TRANSLATE))

from lib.gloss_rules import (  # noqa: E402
    detect_forbidden_gloss,
    detect_trivial_quote_gloss,
    is_l0_word,
)


class TestTrivialGloss(unittest.TestCase):
    def test_shan_hao(self) -> None:
        text = "沛公说：「善。」——好。那些还没攻下的城池……"
        hits = detect_trivial_quote_gloss(text)
        self.assertTrue(any("善" in h for h in hits), hits)
        self.assertTrue(detect_forbidden_gloss(text))

    def test_nuo(self) -> None:
        text = "王曰：「诺。」——好的。"
        self.assertTrue(detect_trivial_quote_gloss(text))

    def test_keeps_informative_gloss(self) -> None:
        text = (
            "汤说：「予有言：人视水见形，视民知治不」——"
            "人照水见形貌，看民情才知治乱。"
        )
        self.assertEqual(detect_trivial_quote_gloss(text), [])

    def test_l0_ack_words(self) -> None:
        self.assertTrue(is_l0_word("善"))
        self.assertTrue(is_l0_word("诺"))


if __name__ == "__main__":
    unittest.main()
