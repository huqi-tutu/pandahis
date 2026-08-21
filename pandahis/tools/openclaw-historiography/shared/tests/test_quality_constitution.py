"""质量宪法切片注入。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "historiography-translate"))

from lib.quality_constitution import (  # noqa: E402
    constitution_path,
    constitution_snip,
)
from lib.rule_bundle import compile_rule_bundle  # noqa: E402


class TestQualityConstitution(unittest.TestCase):
    def test_ssot_exists(self) -> None:
        self.assertTrue(constitution_path().is_file())

    def test_mother_snip(self) -> None:
        s = constitution_snip(phase="draft_mother")
        self.assertIn("八大守恒", s)
        self.assertIn("Phase1", s)
        self.assertIn("省略可恢复", s)

    def test_polish_snip(self) -> None:
        s = constitution_snip(phase="polish")
        self.assertIn("必须有锚点", s)
        self.assertIn("母本锁定", s)
        self.assertIn("Phase2", s)

    def test_phase3_snip(self) -> None:
        s = constitution_snip(phase="phase3")
        self.assertIn("Evidence Backtrace", s)
        self.assertIn("依据", s)

    def test_plan_empty(self) -> None:
        self.assertEqual(constitution_snip(phase="plan"), "")

    def test_bundle_injects_mother(self) -> None:
        b = compile_rule_bundle({"id": "T", "blocks": [], "母本内容": []}, phase="draft_mother")
        self.assertIn("【质量宪法】", b)
        self.assertIn("八大守恒", b)
        self.assertIn("【主场】规则十", b)

    def test_bundle_injects_enrich(self) -> None:
        b = compile_rule_bundle({"id": "T", "blocks": [], "母本内容": []}, phase="draft_enrich")
        self.assertIn("【质量宪法】", b)
        self.assertIn("必须有锚点", b)


if __name__ == "__main__":
    unittest.main()
