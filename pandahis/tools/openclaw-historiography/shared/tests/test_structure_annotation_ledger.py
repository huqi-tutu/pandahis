"""结构账本 / 标注账本单元测试。"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "historiography-translate"))

from lib.annotation_ledger import (  # noqa: E402
    apply_annotation_autofix,
    era_token_to_ce_note,
    format_annotation_gate_errors,
    format_annotation_ledger,
    load_gazetteer,
    missing_era_year_notes,
    places_in_text,
)
from lib.place_now import parse_gazetteer_markdown  # noqa: E402
from lib.structure_ledger import (  # noqa: E402
    build_structure_ledger,
    format_structure_ledger,
    structure_order_warnings,
)


MOTHER = (
    "汉二年，汉王东进，废丘未下。\n\n"
    "韩信击赵，破井陉。\n\n"
    "随何说英布，英布举兵叛楚。\n\n"
    "立太子，赦天下。"
)


class TestStructureLedger(unittest.TestCase):
    def test_builds_ordered_segments(self) -> None:
        segs = build_structure_ledger(MOTHER, "废丘井陉随何英布")
        self.assertGreaterEqual(len(segs), 3)
        self.assertEqual(segs[0].id, "S001")
        self.assertEqual(segs[0].sequence_lock, 1)
        self.assertEqual(segs[1].sequence_lock, 2)
        text = format_structure_ledger(MOTHER, "废丘井陉随何英布")
        self.assertIn("S001", text)
        self.assertIn("顺序锁", text)

    def test_order_warning_runs(self) -> None:
        detail = (
            "先写立太子赦天下。再写随何说英布叛楚。"
            "又写韩信井陉破赵。最后才提汉二年废丘。"
            "参考著作：《史记》"
        )
        warns = structure_order_warnings(detail, MOTHER, "废丘井陉随何英布立太子")
        self.assertIsInstance(warns, list)


class TestAnnotationLedger(unittest.TestCase):
    def test_places_from_mother(self) -> None:
        rows = parse_gazetteer_markdown(
            "| 古地名 | 今地参考 |\n|--------|----------|\n"
            "| 废丘 | 今陕西兴平一带 |\n| 井陉 | 今河北井陉 |\n"
        )
        found = places_in_text(MOTHER, gazetteer=rows)
        names = {p["name"] for p in found}
        self.assertIn("废丘", names)
        self.assertIn("井陉", names)
        ledger = format_annotation_ledger(MOTHER)
        self.assertIn("标注账本", ledger)
        self.assertIn("纪年", ledger)

    def test_missing_era_year(self) -> None:
        self.assertEqual(
            missing_era_year_notes("汉二年（前205年），战事起。"),
            [],
        )
        self.assertEqual(missing_era_year_notes("汉二年，战事起。"), ["汉二年"])
        self.assertIn("建元六年", missing_era_year_notes("建元六年，窦太后崩。"))

    def test_gate_errors_era_and_place(self) -> None:
        os.environ["TRANSLATE_PLACE_NOW_GATE"] = "1"
        os.environ["TRANSLATE_ERA_YEAR_GATE"] = "1"
        detail = "汉二年，大军围废丘，久攻不下。"
        mother = "汉二年，围废丘。"
        gate = format_annotation_gate_errors(detail, mother=mother)
        self.assertTrue(any("纪年" in e for e in gate), gate)
        if any(r["name"] == "废丘" for r in load_gazetteer()):
            self.assertTrue(any("地名" in e for e in gate), gate)

    def test_autofix_place_and_era(self) -> None:
        os.environ["TRANSLATE_PLACE_NOW_GATE"] = "1"
        os.environ["TRANSLATE_ERA_YEAR_GATE"] = "1"
        detail = "汉二年，大军围废丘，久攻不下。"
        mother = "汉二年，围废丘。"
        fixed, changes = apply_annotation_autofix(detail, mother=mother)
        self.assertTrue(changes, changes)
        self.assertIn("（前205年）", fixed)
        self.assertEqual(era_token_to_ce_note("汉十一年"), "（前196年）")
        gate = format_annotation_gate_errors(fixed, mother=mother)
        self.assertFalse(any("纪年" in e for e in gate), gate)
        if any(r["name"] == "废丘" for r in load_gazetteer()):
            self.assertIn("（今", fixed)
            self.assertFalse(any("地名" in e for e in gate), gate)

    def test_compound_place_now_nearby(self) -> None:
        from lib.place_now import missing_first_now_places

        # 丰邑中阳里人（今…）应视为已标
        body = "刘邦是沛县丰邑中阳里人（今江苏沛县、丰县一带），姓刘。"
        self.assertNotIn("丰邑", missing_first_now_places(body))


if __name__ == "__main__":
    unittest.main()
