"""对照表今地：只拦表内已知地名的首次漏标，不假装全库。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "historiography-translate"))

from lib.place_now import (  # noqa: E402
    load_gazetteer,
    missing_first_now_places,
    parse_gazetteer_markdown,
)


SAMPLE = """
| 古地名 | 今地参考 |
|--------|----------|
| 废丘 | 今陕西兴平一带 |
| 朝歌 | 今河南淇县 |
| 汜水 | 今河南荥阳一带 |
| 广武 | 今河南荥阳东北 |
| 曲逆 | 今河北顺平 |
| 洛阳 | 今河南洛阳（古今同名可不标） |
| 宛 | 今河南南阳 |
"""


class TestPlaceNowGazetteer(unittest.TestCase):
    def test_parse_skips_optional_and_short(self) -> None:
        rows = parse_gazetteer_markdown(SAMPLE)
        names = {r["name"] for r in rows}
        self.assertIn("废丘", names)
        self.assertIn("朝歌", names)
        self.assertNotIn("洛阳", names)
        self.assertNotIn("宛", names)

    def test_missing_first_occurrence(self) -> None:
        rows = parse_gazetteer_markdown(SAMPLE)
        detail = "定都废丘，又定都朝歌（今河南淇县）。后来再提废丘不必重复。"
        missing = missing_first_now_places(detail, gazetteer=rows)
        self.assertEqual(missing, ["废丘"])

    def test_skips_now_paren_and_title_suffix(self) -> None:
        rows = parse_gazetteer_markdown(SAMPLE)
        detail = (
            "成皋（今河南荥阳汜水镇一带）。封广武君、曲逆侯。后来定都广武。"
        )
        missing = missing_first_now_places(detail, gazetteer=rows)
        self.assertNotIn("汜水", missing)
        self.assertNotIn("曲逆", missing)
        self.assertEqual(missing, ["广武"])

    def test_annotated_first_pass(self) -> None:
        rows = parse_gazetteer_markdown(SAMPLE)
        detail = "定都废丘（今陕西兴平一带），又定都朝歌（今河南淇县）。"
        self.assertEqual(missing_first_now_places(detail, gazetteer=rows), [])

    def test_load_real_table(self) -> None:
        rows = load_gazetteer()
        names = {r["name"] for r in rows}
        self.assertIn("幽陵", names)
        self.assertNotIn("长安", names)


if __name__ == "__main__":
    unittest.main()
