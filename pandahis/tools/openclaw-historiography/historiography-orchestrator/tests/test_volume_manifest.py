"""volume_manifest 与四级坐标 LLM 分工测试。"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ORCH = Path(__file__).resolve().parents[1]
ANNOTATE = ORCH.parent / "historiography-annotate"
sys.path.insert(0, str(ORCH))
sys.path.insert(0, str(ANNOTATE))

from lib.volume_manifest import (  # noqa: E402
    build_mechanical_blocks,
    infer_narrative_mode,
    manifest_payload_errors,
    skip_reason_from_volume_name,
)
from fill_fields import (  # noqa: E402
    _needs_for_entry,
    prepare_spindle_emperor_for_llm,
    merge_all_entries,
)
from coordinate_index import FOURTH_EMPIRE_COORD_FIELD, SCRIPT_COORD_FIELDS  # noqa: E402


class TestVolumeManifest(unittest.TestCase):
    def test_skip_zhizhi_volume(self):
        reason = skip_reason_from_volume_name("食货志")
        self.assertIn("志卷", reason or "")

    def test_infer_single_mode(self):
        m = {
            "protagonists": [{"name": "张良", "category": "文臣", "rationale": "x"}]
        }
        self.assertEqual(infer_narrative_mode(m), "single")

    def test_infer_fanzuo_mode(self):
        m = {
            "protagonists": [{"name": "南越", "category": "蕃祚", "rationale": "x"}]
        }
        self.assertEqual(infer_narrative_mode(m), "fanzuo")

    def test_skip_manifest_requires_reason(self):
        m = {
            "narrative_mode": "skip",
            "protagonists": [],
        }
        errs = manifest_payload_errors(m)
        self.assertTrue(any("skip_reason" in e for e in errs))

    def test_mechanical_blocks_single(self):
        m = {
            "work": "02汉书",
            "vol": "077",
            "volume_name": "东方朔传",
            "narrative_mode": "single",
            "protagonists": [
                {"name": "东方朔", "category": "文臣", "rationale": "卷名主人公"}
            ],
        }
        draft = build_mechanical_blocks(
            m,
            total_paragraphs=5,
            para_text={
                1: "东方朔传第三十五",
                2: "东方朔，平原厌次人也。",
                3: "武帝时，朔为郎。",
                4: "朔卒，谥曰缪。",
                5: "班固曰：其辞虽俳，其意则正。",
            },
        )
        self.assertEqual(len(draft["blocks"]), 1)
        self.assertEqual(draft["blocks"][0]["paragraph_from"], 2)
        self.assertEqual(draft["blocks"][0]["paragraph_to"], 4)
        self.assertTrue(any(e["exclude_reason"] == "卷首标题" for e in draft["excludes"]))

    def test_mechanical_blocks_single_excludes_part_subtitle(self):
        m = {
            "work": "02汉书",
            "vol": "085",
            "volume_name": "韦贤传",
            "narrative_mode": "single",
            "protagonists": [
                {"name": "韦贤", "category": "文臣", "rationale": "卷名主人公"}
            ],
        }
        draft = build_mechanical_blocks(
            m,
            total_paragraphs=5,
            para_text={
                1: "卷七十三",
                2: "韦贤传第四十三",
                3: "韦贤字长孺。鲁国邹人也。",
                4: "昭帝崩，无嗣，大将军霍光与公卿共尊立孝宣帝。",
                5: "赞曰：遗子黄金满籝，不如一经。",
            },
        )
        self.assertEqual(len(draft["blocks"]), 1)
        self.assertEqual(draft["blocks"][0]["paragraph_from"], 3)
        self.assertEqual(draft["blocks"][0]["paragraph_to"], 4)
        self.assertTrue(any(e["exclude_reason"] == "篇内小标题" for e in draft["excludes"]))

    def test_mechanical_blocks_hezhuan(self):
        m = {
            "work": "02汉书",
            "vol": "044",
            "volume_name": "韩彭英卢吴传",
            "narrative_mode": "hezhuan",
            "protagonists": [
                {"name": "韩信", "category": "武将", "rationale": "x"},
                {"name": "彭越", "category": "武将", "rationale": "x"},
                {"name": "英布", "category": "武将", "rationale": "x"},
                {"name": "卢绾", "category": "武将", "rationale": "x"},
                {"name": "吴芮", "category": "君王", "rationale": "x"},
            ],
        }
        para = {
            1: "卷三十四韩彭英卢吴传第四",
            2: "韩信，淮阴人也。",
            12: "遂夷信三族。",
            13: "彭越字仲，昌邑人也。",
            15: "遂夷越宗族。",
            16: "黥布，六人也，姓英氏。",
            21: "布走度淮。",
            22: "封贲赫为列侯。卢绾，丰人也，与高祖同里。",
            24: "孝景帝时，绾孙它人以东胡王降。",
            25: "吴芮，秦时番阳令也。",
            26: "赞曰：昔高祖定天下。",
        }
        draft = build_mechanical_blocks(m, total_paragraphs=26, para_text=para)
        self.assertEqual(len(draft["blocks"]), 5)
        by_name = {b["name"]: b for b in draft["blocks"]}
        self.assertEqual(by_name["韩信"]["paragraph_from"], 2)
        self.assertEqual(by_name["韩信"]["paragraph_to"], 12)
        self.assertEqual(by_name["彭越"]["paragraph_from"], 13)
        self.assertEqual(by_name["英布"]["paragraph_from"], 16)
        self.assertEqual(by_name["英布"]["paragraph_to"], 21)
        self.assertEqual(by_name["卢绾"]["paragraph_from"], 22)
        self.assertEqual(by_name["吴芮"]["paragraph_from"], 25)

    def test_mechanical_blocks_hezhuan_same_paragraph_handoff(self):
        """合传同段接力（如 052 张苍 P2 末接周昌者）须后移块界避免重复归属。"""
        m = {
            "work": "02汉书",
            "vol": "052",
            "volume_name": "张周赵任申屠传",
            "narrative_mode": "hezhuan",
            "protagonists": [
                {"name": "张苍", "category": "文臣", "rationale": "x"},
                {"name": "周昌", "category": "文臣", "rationale": "x"},
                {"name": "赵尧", "category": "文臣", "rationale": "x"},
            ],
        }
        para = {
            1: "卷四十二张周赵任申屠传第十二",
            2: "张苍，阳武人也。身长大，肥白如瓠。周昌者，沛人也。",
            3: "六年，与萧、曹等俱封，为汾阴侯。赵尧为符玺御史。",
            4: "吾念之欲如是，而群臣谁可者？",
            5: "高祖尝避吏，吏系吕后。",
            6: "申屠嘉，梁人也。",
            7: "嘉坐自如，弗为礼。",
            8: "赞曰：张苍文好律历。",
        }
        draft = build_mechanical_blocks(m, total_paragraphs=8, para_text=para)
        by_name = {b["name"]: b for b in draft["blocks"]}
        self.assertEqual(by_name["张苍"]["paragraph_from"], 2)
        self.assertEqual(by_name["周昌"]["paragraph_from"], 3)
        self.assertEqual(by_name["赵尧"]["paragraph_from"], 4)


class TestSpindleFourthEmperor(unittest.TestCase):
    def test_needs_llm_only_fourth_emperor(self):
        entry = {
            "史略分类": "宗戚",
            "史略名称": "吕太后",
            "优先级": "P0",
            "优先级判定理由": "x",
            "史略开始年": -247,
            "史略结束年": -180,
        }
        needs = _needs_for_entry(entry)
        self.assertIn(FOURTH_EMPIRE_COORD_FIELD, needs)
        for f in SCRIPT_COORD_FIELDS:
            self.assertNotIn(f, needs)

    def test_prepare_clears_only_fourth_for_spindle(self):
        data = {
            "entries": [
                {
                    "史略ID": "T_01",
                    "史略名称": "吕太后",
                    "史略分类": "宗戚",
                    "史略简介": "高后临朝",
                }
            ]
        }
        n = prepare_spindle_emperor_for_llm(data, work_id="02汉书")
        self.assertEqual(n, 1)
        entry = data["entries"][0]
        self.assertNotIn(FOURTH_EMPIRE_COORD_FIELD, entry)
        needs = entry.get("_needs_llm") or []
        self.assertEqual(needs, [FOURTH_EMPIRE_COORD_FIELD])
        self.assertIn("_主轴参考", str(entry.get("_auto_filled") or {}))


if __name__ == "__main__":
    unittest.main()
