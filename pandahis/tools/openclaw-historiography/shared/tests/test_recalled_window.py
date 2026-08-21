"""recalled 本批原文窗口：本批 + 前后各 N 段。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRANSLATE = ROOT / "historiography-translate"
sys.path.insert(0, str(TRANSLATE))

from lib.recalled_window import (  # noqa: E402
    ZONE_AFTER,
    ZONE_BEFORE,
    ZONE_MUST,
    batch_window_guard_note,
    build_batch_recalled_payload,
    build_mother_batch_m_payload,
    flatten_mother_paragraphs,
    parse_paragraph_ids_from_checklist,
)


def _mother_recalled(n: int = 12) -> dict:
    paras = [{"id": i, "text": f"原文段落{i}。" * 3} for i in range(1, n + 1)]
    return {
        "史略ID": "GLBL_TEST",
        "史略名称": "测试",
        "blocks": [
            {
                "role": "母本",
                "work": "01史记",
                "vol": "008",
                "volume": "高祖本纪",
                "paragraph_from": 1,
                "paragraph_to": n,
                "paragraph_count": n,
                "paragraphs": paras,
            },
            {
                "role": "补充",
                "work": "02汉书",
                "vol": "001",
                "volume": "高帝纪",
                "paragraph_from": 5,
                "paragraph_to": 7,
                "paragraph_count": 3,
                "paragraphs": [
                    {"id": 5, "text": "汉书补充五。"},
                    {"id": 6, "text": "汉书补充六。"},
                    {"id": 7, "text": "汉书补充七。"},
                ],
            },
        ],
    }


def _items_for_paras(*pids: int) -> list[dict]:
    return [
        {"编号": f"M{i:03d}", "段落": f"01史记 卷008 高祖本纪 P{pid}"}
        for i, pid in enumerate(pids, start=1)
    ]


class TestRecalledWindow(unittest.TestCase):
    def test_parse_paragraph_ids(self) -> None:
        items = _items_for_paras(5, 5, 6, 7)
        self.assertEqual(parse_paragraph_ids_from_checklist(items), [5, 6, 7])

    def test_flatten_mother_only(self) -> None:
        flat = flatten_mother_paragraphs(_mother_recalled(5))
        self.assertEqual([p["id"] for p in flat], [1, 2, 3, 4, 5])

    def test_window_middle_batch(self) -> None:
        recalled = _mother_recalled(12)
        # 本批 P5–P7 → 上文 P2–P4，下文 P8–P10
        payload = build_batch_recalled_payload(
            recalled, _items_for_paras(5, 6, 7), radius=3
        )
        self.assertEqual(payload["window_mode"], "batch_context")
        self.assertEqual(payload["must_translate_paragraph_ids"], [5, 6, 7])
        self.assertEqual(payload["context_before_paragraph_ids"], [2, 3, 4])
        self.assertEqual(payload["context_after_paragraph_ids"], [8, 9, 10])
        # 母本段均带 zone
        mother_paras = []
        for b in payload["blocks"]:
            if b.get("role") == "母本":
                mother_paras.extend(b["paragraphs"])
        zones = {p["id"]: p["zone"] for p in mother_paras}
        self.assertEqual(zones[2], ZONE_BEFORE)
        self.assertEqual(zones[5], ZONE_MUST)
        self.assertEqual(zones[10], ZONE_AFTER)
        # 不应包含 P1 / P11 / P12
        self.assertNotIn(1, zones)
        self.assertNotIn(12, zones)
        # 补充落在窗口内
        supp = [b for b in payload["blocks"] if b.get("role") == "补充"]
        self.assertTrue(supp)
        supp_ids = {int(p["id"]) for p in supp[0]["paragraphs"]}
        self.assertTrue({5, 6, 7}.issubset(supp_ids))

    def test_window_first_batch_no_before(self) -> None:
        payload = build_batch_recalled_payload(
            _mother_recalled(10), _items_for_paras(1, 2), radius=3
        )
        self.assertEqual(payload["context_before_paragraph_ids"], [])
        self.assertEqual(payload["must_translate_paragraph_ids"], [1, 2])
        self.assertEqual(payload["context_after_paragraph_ids"], [3, 4, 5])

    def test_window_last_batch_no_after(self) -> None:
        payload = build_batch_recalled_payload(
            _mother_recalled(10), _items_for_paras(9, 10), radius=3
        )
        self.assertEqual(payload["context_after_paragraph_ids"], [])
        self.assertEqual(payload["context_before_paragraph_ids"], [6, 7, 8])

    def test_fallback_without_para_refs(self) -> None:
        payload = build_batch_recalled_payload(
            _mother_recalled(4), [{"编号": "M001", "段落": "无段号"}]
        )
        self.assertEqual(payload["window_mode"], "full_fallback")

    def test_guard_note_mentions_must(self) -> None:
        payload = build_batch_recalled_payload(
            _mother_recalled(8), _items_for_paras(4), radius=2
        )
        note = batch_window_guard_note(payload)
        self.assertIn("must_translate", note)
        self.assertIn("P4", note)
        self.assertIn("禁止", note)

    def test_mother_m_payload_no_full_paragraphs(self) -> None:
        """Phase1：批界落在段中时只注入本批 M 摘句，不得把整段 P 灌进 must。"""
        items = [
            {
                "编号": "M070",
                "段落": "01史记 卷008 高祖本纪 P16",
                "原文摘句": "沛公还军亢父，至方与，未战。",
            },
            {
                "编号": "M071",
                "段落": "01史记 卷008 高祖本纪 P16",
                "原文摘句": "陈王使魏人周市略地。",
            },
            {
                "编号": "M072",
                "段落": "01史记 卷008 高祖本纪 P16",
                "原文摘句": "周市使人谓雍齿曰：“丰，故梁徙也。”",
            },
        ]
        payload = build_mother_batch_m_payload(_mother_recalled(20), items)
        self.assertEqual(payload["window_mode"], "m_sentences")
        self.assertEqual(payload["must_m_ids"], ["M070", "M071", "M072"])
        self.assertEqual(payload["blocks"], [])
        self.assertEqual(payload["must_translate_paragraph_ids"], [])
        # 摘句在 must_sentences，且不应出现未列入的后文
        texts = " ".join(r["原文摘句"] for r in payload["must_sentences"])
        self.assertIn("周市使人谓雍齿", texts)
        self.assertNotIn("雍齿雅不欲属沛公", texts)
        # 同段分组 + 合段提示
        self.assertEqual(len(payload["must_by_paragraph"]), 1)
        self.assertEqual(payload["must_by_paragraph"][0]["段落键"], "P16")
        self.assertEqual(payload["must_by_paragraph"][0]["sentence_count"], 3)
        note = batch_window_guard_note(payload)
        self.assertIn("按 M 句级", note)
        self.assertIn("一条 M", note)


if __name__ == "__main__":
    unittest.main()
