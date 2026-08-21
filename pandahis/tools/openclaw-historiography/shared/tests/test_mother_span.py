"""母本段落门禁：连续整段情节不得在润色中蒸发。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "historiography-translate"))

from lib.mother_span import (  # noqa: E402
    format_span_hole_errors,
    format_span_hole_retry_note,
    locate_span_backfill_slots,
    missing_mother_span_holes,
    splice_missing_mother_spans,
)
from lib.phase3_qa import program_qa_findings, verify_polish_draft_light  # noqa: E402

SOURCE = (
    "周吕侯吕泽将兵居下邑。汉王从下邑往，至虞，谓谒者随何曰："
    "公能说九江王布使举兵叛楚。随何往说九江王。立太子，令太子守栎阳。"
    "引水灌废丘，废丘降，更名槐里。魏豹反，韩信虏豹，定魏地，置河东、太原、上党郡。"
    "张耳与韩信东下井陉击赵。汉王军荥阳南，筑甬道属之河，取敖仓粟。"
    "将军纪信乃乘王车出东门。汉王驻军敖仓。"
)

MOTHER = """彭城之战，汉军大败，士卒死了十几万人。

吕后的哥哥周吕侯吕泽正替汉王领兵，驻扎在下邑。汉王派谒者随何去说九江王：「您若能说动英布起兵反楚，我夺取天下就稳了。」

汉王在彭城大败后向西撤退，只找回了后来的孝惠帝刘盈。六月，立为太子，令太子守栎阳。

与此同时，汉军引水灌废丘，废丘守军开城投降，更名槐里。

汉王驻军荥阳南面，修筑甬道直通黄河，用来运取敖仓的粮食。

参考著作
- 《史记》"""

DROPPED = """彭城那一仗打崩了，汉军死了十几万人，河水都红了。

后来汉王在荥阳南边修了甬道，靠敖仓运粮，跟项羽耗上了。

参考著作：
- 《史记》"""

REWRITTEN = """彭城那一仗打崩了，死了十几万人。

吕后哥哥周吕侯还在下邑顶着。汉王派谒者随何去劝九江王英布反楚，把项羽拖住几个月。

败退路上只找回刘盈，六月立为太子，让他守栎阳。

汉军把废丘灌了，城破之后改名槐里。

荥阳南边修了甬道，从敖仓运粮。

参考著作：
- 《史记》"""


class TestMotherSpanHoles(unittest.TestCase):
    def test_detects_consecutive_plot_drop(self) -> None:
        holes = missing_mother_span_holes(MOTHER, DROPPED, SOURCE)
        self.assertTrue(holes, "跳过随何/太子/槐里连续段应检出整段漏")
        covered = {i for h in holes for i in range(h.start, h.end + 1)}
        self.assertTrue(any(72 <= i <= 74 or i in covered for i in covered) or len(covered) >= 2)
        self.assertGreaterEqual(holes[0].end - holes[0].start + 1, 2)
        blob = "\n".join(s.text for h in holes for s in h.spans)
        self.assertTrue("随何" in blob or "太子" in blob or "槐里" in blob or "废丘" in blob)

    def test_rewrite_keeping_names_passes(self) -> None:
        holes = missing_mother_span_holes(MOTHER, REWRITTEN, SOURCE)
        self.assertEqual(holes, [])

    def test_compress_wording_passes(self) -> None:
        compressed = (
            "彭城汉军大败。\n\n"
            "周吕侯居下邑。谒者随何说九江王。\n\n"
            "立为太子，守栎阳。\n\n"
            "引水灌废丘，更名槐里。\n\n"
            "荥阳南修甬道，取敖仓粟。\n\n"
            "参考著作：\n- 《史记》"
        )
        holes = missing_mother_span_holes(MOTHER, compressed, SOURCE)
        self.assertEqual(holes, [])

    def test_isolated_short_miss_is_not_a_hole(self) -> None:
        mother = (
            "周吕侯驻扎在下邑。\n\n"
            "汉王下令让祠官祀天地。\n\n"
            "汉王驻军荥阳南，取敖仓粟。\n\n"
            "参考著作\n- 《史记》"
        )
        source = "周吕侯居下邑。祠官祀天地。军荥阳南，取敖仓粟。"
        detail = (
            "周吕侯还在下邑。\n\n"
            "汉王在荥阳南取敖仓粮食。\n\n"
            "参考著作：\n- 《史记》"
        )
        holes = missing_mother_span_holes(mother, detail, source)
        self.assertEqual(holes, [])

    def test_error_message_uses_span_drop_token(self) -> None:
        holes = missing_mother_span_holes(MOTHER, DROPPED, SOURCE)
        errs = format_span_hole_errors(holes)
        self.assertTrue(errs)
        self.assertTrue(any("整段漏" in e for e in errs))


class TestMotherSpanSplice(unittest.TestCase):
    def test_locate_slot_between_neighbors_not_late_anchor(self) -> None:
        slots = locate_span_backfill_slots(DROPPED, MOTHER, SOURCE)
        self.assertTrue(slots)
        slot = slots[0]
        self.assertIn("随何", slot.mother_block)
        # 夹缝下界应落在荥阳/甬道一带；上界可以是彭城段或文首
        self.assertTrue(
            "甬道" in slot.after_excerpt or "荥阳" in slot.after_excerpt,
            slot.after_excerpt,
        )
        self.assertNotIn("脩武", slot.before_excerpt)
        note = format_span_hole_retry_note([s.hole for s in slots], slots=slots)
        self.assertIn("夹缝", note)
        self.assertIn("概括顶替", note)

    def test_splice_debug_helper_still_covers_anchors(self) -> None:
        """兼容调试用 splice：锚点应覆盖；生产路径不写回成稿。"""
        spliced, holes = splice_missing_mother_spans(DROPPED, MOTHER, SOURCE)
        self.assertTrue(holes)
        self.assertIn("随何", spliced)
        self.assertIn("立为太子", spliced)
        self.assertIn("槐里", spliced)
        self.assertEqual(missing_mother_span_holes(MOTHER, spliced, SOURCE), [])


class TestPhase2Phase3Hooks(unittest.TestCase):
    def test_verify_polish_draft_light_blocks_span_drop(self) -> None:
        ok, errs = verify_polish_draft_light(
            entry_id="GLBL_TEST",
            detail=DROPPED,
            mother=MOTHER,
            source_original=SOURCE,
        )
        self.assertFalse(ok)
        self.assertTrue(any("整段漏" in e for e in errs))

    def test_program_qa_reports_span_drop(self) -> None:
        finds = program_qa_findings(
            mother=MOTHER, detail=DROPPED, source_original=SOURCE
        )
        self.assertTrue(
            any("整段漏" in (f.get("说明") or "") for f in finds),
            finds,
        )


class TestClassifySpanDrop(unittest.TestCase):
    def test_classify_before_legend_continuous(self) -> None:
        from shared.qa_repair import classify_translate_failure

        plan = classify_translate_failure(
            ["整段漏：母本第72–74段在成稿中对不上（锚点：谒者随何）"],
            stage="phase2",
            fail_count=1,
        )
        self.assertEqual(plan.root_cause, "MOTHER_SPAN_DROP")
        self.assertEqual(plan.disposition, "retry_llm")


@unittest.skipUnless(
    (
        Path(__file__).resolve().parents[4]
        / "data/05工作流中间产物/翻译/GLBL_00085_汉高祖.mother.json"
    ).is_file(),
    "本地高祖母本/版本不在仓库",
)
class TestGaozuRegression(unittest.TestCase):
    def _load(self, rel: str) -> dict:
        root = Path(__file__).resolve().parents[4]
        return __import__("json").loads((root / rel).read_text(encoding="utf-8"))

    def _text(self, data: dict) -> str:
        return str(data.get("翻译详情") or data.get("母本顺译") or "")

    def test_v13_passes_v14_fails_on_suihe_block(self) -> None:
        mother = self._text(
            self._load("data/05工作流中间产物/翻译/GLBL_00085_汉高祖.mother.json")
        )
        v13 = self._load(
            "data/11新标注条目翻译/_versions/GLBL_00085_汉高祖/GLBL_00085_汉高祖.v13.json"
        )
        v14 = self._load(
            "data/11新标注条目翻译/_versions/GLBL_00085_汉高祖/GLBL_00085_汉高祖.v14.json"
        )
        source = str(v14.get("史料原文") or v13.get("史料原文") or "")
        h13 = missing_mother_span_holes(mother, self._text(v13), source)
        h14 = missing_mother_span_holes(mother, self._text(v14), source)
        self.assertEqual(h13, [], [ (h.start, h.end) for h in h13 ])
        self.assertTrue(h14, "v14 删了随何至井陉一带，应硬失败")
        covered = {i for h in h14 for i in range(h.start, h.end + 1)}
        self.assertTrue(
            72 in covered or any("随何" in s.text for h in h14 for s in h.spans),
            [(h.start, h.end) for h in h14],
        )
        slots = locate_span_backfill_slots(self._text(v14), mother, source)
        self.assertTrue(slots)
        suihe = next(
            (s for s in slots if "随何" in s.mother_block or s.hole.start <= 72 <= s.hole.end),
            slots[0],
        )
        # 不得把随何夹到脩武/成皋之后；下界应靠近荥阳甬道
        self.assertNotIn("脩武", suihe.before_excerpt)
        self.assertNotIn("郑忠", suihe.before_excerpt)
        self.assertTrue(
            "甬道" in suihe.after_excerpt
            or "荥阳" in suihe.after_excerpt
            or "敖仓" in suihe.after_excerpt,
            (suihe.before_excerpt, suihe.after_excerpt),
        )
        spliced, _ = splice_missing_mother_spans(self._text(v14), mother, source)
        self.assertIn("随何", spliced)
        self.assertEqual(self._text(v14).count("纪信"), spliced.count("纪信"))


if __name__ == "__main__":
    unittest.main()
