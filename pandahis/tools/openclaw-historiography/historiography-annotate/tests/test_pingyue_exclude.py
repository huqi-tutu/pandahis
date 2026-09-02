"""三国志「评曰」须 exclude、不划入事略。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ANNOTATE = Path(__file__).resolve().parents[1]
V2_SCRIPTS = ANNOTATE.parent / "historiography-annotate-v2" / "scripts"
ORCH = ANNOTATE.parent / "historiography-orchestrator"
for p in (ANNOTATE, V2_SCRIPTS, str(ORCH)):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from paragraph_utils import (  # noqa: E402
    decompose_line_to_paragraphs,
    lunzan_exclude_reason,
    split_glued_pingyue,
)
from v2_expand_to_skeleton import _detect_exclude_paragraphs  # noqa: E402
from lib.volume_manifest import build_mechanical_blocks  # noqa: E402


class TestPingyueDetect(unittest.TestCase):
    def test_lunzan_reason_pingyue(self) -> None:
        self.assertEqual(
            lunzan_exclude_reason("评曰：汉末，天下大乱，雄豪并起。"),
            "评曰",
        )
        self.assertIsNone(lunzan_exclude_reason("太祖武皇帝，沛国谯人也。"))

    def test_split_glued_pingyue(self) -> None:
        text = "允友人同郡崔赞，亦尝以处世太盛戒允云。评曰：夏侯、曹氏，世为婚姻。"
        parts = split_glued_pingyue(text)
        self.assertIsNotNone(parts)
        assert parts is not None
        self.assertEqual(len(parts), 2)
        self.assertTrue(parts[0].endswith("戒允云。"))
        self.assertTrue(parts[1].startswith("评曰"))

    def test_decompose_splits_glued_pingyue(self) -> None:
        line = "经不能从，终以致败。评曰：夏侯、曹氏，世为婚姻。"
        parts = decompose_line_to_paragraphs(line)
        self.assertEqual(len(parts), 2)
        self.assertTrue(parts[1].startswith("评曰"))

    def test_mechanical_single_excludes_pingyue_only(self) -> None:
        para = {
            1: "卷三 魏书三  明帝纪第三",
            2: "明皇帝讳叡，字元仲，文帝太子也。",
            3: "评曰：明帝沉毅断识，任心而行。",
            4: "上三国志注表",
        }
        excludes = _detect_exclude_paragraphs(para, "04三国志")
        reasons = {(pf, pt, r) for pf, pt, r in excludes}
        self.assertIn((3, 3, "评曰"), reasons)
        self.assertNotIn((4, 4, "评曰"), reasons)
        self.assertNotIn((4, 4, "论赞"), reasons)

    def test_volume_manifest_single_excludes_pingyue(self) -> None:
        m = {
            "work": "04三国志",
            "vol": "003",
            "volume_name": "明帝纪",
            "narrative_mode": "single",
            "protagonists": [
                {"name": "魏明帝", "category": "君王", "rationale": "本纪"}
            ],
        }
        draft = build_mechanical_blocks(
            m,
            total_paragraphs=4,
            para_text={
                1: "卷三 魏书三  明帝纪第三",
                2: "明皇帝讳叡，字元仲，文帝太子也。",
                3: "太和元年春正月，郊祀武皇帝以配天。",
                4: "评曰：明帝沉毅断识，任心而行。",
            },
        )
        self.assertEqual(draft["blocks"][0]["paragraph_from"], 2)
        self.assertEqual(draft["blocks"][0]["paragraph_to"], 3)
        self.assertTrue(any(e["exclude_reason"] == "评曰" for e in draft["excludes"]))


if __name__ == "__main__":
    unittest.main()
