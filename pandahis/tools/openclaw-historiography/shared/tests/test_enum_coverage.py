"""enum_coverage 语义覆盖测试。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from enum_coverage import enum_item_covered  # noqa: E402


def test_parenthetical_child():
    body = "长子叫玄嚣，号为青阳，次子叫昌意"
    assert enum_item_covered(body, "玄嚣（青阳）")
    assert enum_item_covered(body, "昌意")


def test_synonym_battle_rounds():
    body = "黄帝与炎帝战于阪泉之野，三战，然后得其志"
    assert enum_item_covered(body, "多次交战")
    assert enum_item_covered(body, "阪泉之野")


def test_synonym_submission():
    body = "炎帝部落战败，整体归服于黄帝"
    assert enum_item_covered(body, "最终归服")


def test_synonym_kill_chiyou():
    body = "战于涿鹿之野，遂禽杀蚩尤"
    assert enum_item_covered(body, "黄帝擒杀蚩尤")


def test_virtue_identity():
    body = "嫫母容貌丑陋，是黄帝的次妃，被黄帝任用。虽貌恶而德不衰，执掌后宫事务"
    assert enum_item_covered(body, "容貌丑陋")
    assert enum_item_covered(body, "德行充实")
    assert enum_item_covered(body, "黄帝次妃")
    assert enum_item_covered(body, "内助后宫")
