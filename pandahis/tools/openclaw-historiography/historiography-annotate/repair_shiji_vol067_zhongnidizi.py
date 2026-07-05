#!/usr/bin/env python3
"""返工《史记》067 仲尼弟子列传：Step1a 主人公=众弟子（非孔子），按原文段落分块。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

SKILL_DIR = Path(__file__).resolve().parent
_ROOT = SKILL_DIR.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

from coordinate_index import ids_from_emperor  # noqa: E402
from emperor_resolve import build_emperor_info_index  # noqa: E402
from paths_config import get_histograph_root  # noqa: E402

ORCH = _ROOT / "historiography-orchestrator"
if str(ORCH) not in sys.path:
    sys.path.insert(0, str(ORCH))

from lib import gates  # noqa: E402
from lib.blocks_workflow import blocks_path, expand_blocks_to_skeleton, volume_display_name  # noqa: E402
from lib.protagonist_workflow import protagonists_path  # noqa: E402
from lib.db import connect, utc_now  # noqa: E402

WORK = "01史记"
VOL = "067"
DATA = get_histograph_root() / "data"
INDEX_DIR = DATA / "03索引标注条目" / "段落索引"

BlockSpec = Tuple[str, str, int, int]
ExcludeSpec = Tuple[int, int, str]

# (name, category, p_from, p_to)
BLOCKS: List[BlockSpec] = [
    ("颜回", "文臣", 3, 8),
    ("闵子骞", "文臣", 9, 10),
    ("冉伯牛", "文臣", 11, 12),
    ("冉雍", "文臣", 13, 15),
    ("冉有", "文臣", 16, 18),
    ("子路", "文臣", 19, 33),
    ("宰予", "文臣", 34, 39),
    ("子贡", "文臣", 40, 58),
    ("子游", "文臣", 59, 61),
    ("子夏", "文臣", 62, 66),
    ("子张", "文臣", 67, 70),
    ("曾参", "文臣", 71, 72),
    ("澹台灭明", "文臣", 73, 75),
    ("宓不齐", "文臣", 76, 78),
    ("原宪", "文臣", 79, 82),
    ("公冶长", "文臣", 83, 84),
    ("南宫括", "文臣", 85, 86),
    ("公皙哀", "文臣", 87, 88),
    ("曾蒧", "文臣", 89, 90),
    ("颜无繇", "文臣", 91, 92),
    ("商瞿", "文臣", 93, 94),
    ("高柴", "文臣", 95, 97),
    ("漆彫开", "文臣", 98, 99),
    ("公伯缭", "文臣", 100, 101),
    ("司马耕", "文臣", 102, 104),
    ("樊须", "文臣", 105, 107),
    ("有若", "文臣", 108, 110),
    ("公西赤", "文臣", 111, 113),
    ("巫马施", "文臣", 114, 115),
]

EXCLUDES: List[ExcludeSpec] = [
    (1, 2, "其他"),
    (116, 163, "其他"),  # 弟子名册及仅年名字一句带过，不引入
    (164, 164, "太史公曰"),
]

ENTRY_META: Dict[str, dict] = {
    "颜回": {"patron": "鲁定公", "start": -521, "end": -481, "axis": "颜回从孔子在鲁学门，主轴挂鲁定公；早卒见共段事略。"},
    "闵子骞": {"patron": "鲁定公", "start": -536, "end": -487, "axis": "闵子骞孝行与拒仕，主轴挂鲁定公。"},
    "冉伯牛": {"patron": "鲁定公", "start": -544, "end": -479, "axis": "冉伯牛有德行、恶疾，主轴挂鲁定公。"},
    "冉雍": {"patron": "鲁定公", "start": -543, "end": -474, "axis": "冉雍问政、可使南面，主轴挂鲁定公。"},
    "冉有": {"patron": "鲁定公", "start": -552, "end": -470, "axis": "冉有为季氏宰，主轴挂鲁定公。"},
    "子路": {"patron": "鲁定公", "start": -542, "end": -480, "axis": "子路从孔子、仕卫殉难，主轴挂鲁定公。"},
    "宰予": {"patron": "鲁定公", "start": -522, "end": -476, "axis": "宰予辩辞与丧礼之问，主轴挂鲁定公。"},
    "子贡": {"patron": "鲁定公", "start": -520, "end": -420, "axis": "子贡周游存鲁乱齐，主轴挂鲁定公；后仕卫越见共段事略。"},
    "子游": {"patron": "鲁定公", "start": -506, "end": -443, "axis": "子游武城宰弦歌，主轴挂鲁定公。"},
    "子夏": {"patron": "魏文侯", "start": -507, "end": -420, "axis": "子夏居西河教授、为魏文侯师，主轴挂魏文侯。"},
    "子张": {"patron": "鲁定公", "start": -503, "end": -480, "axis": "子张问干禄与达，主轴挂鲁定公。"},
    "曾参": {"patron": "鲁定公", "start": -505, "end": -436, "axis": "曾参传孝经，主轴挂鲁定公。"},
    "澹台灭明": {"patron": "鲁定公", "start": -512, "end": -470, "axis": "澹台灭明南游授徒，主轴挂鲁定公。"},
    "宓不齐": {"patron": "鲁定公", "start": -528, "end": -448, "axis": "宓不齐单父宰，主轴挂鲁定公。"},
    "原宪": {"patron": "鲁定公", "start": -515, "end": -430, "axis": "原宪守道安贫，主轴挂鲁定公。"},
    "公冶长": {"patron": "鲁定公", "start": -530, "end": -470, "axis": "公冶长可妻，主轴挂鲁定公。"},
    "南宫括": {"patron": "鲁定公", "start": -540, "end": -468, "axis": "南宫括问羿奡，主轴挂鲁定公。"},
    "公皙哀": {"patron": "鲁定公", "start": -548, "end": -475, "axis": "公皙哀未尝仕，主轴挂鲁定公。"},
    "曾蒧": {"patron": "鲁定公", "start": -518, "end": -468, "axis": "曾蒧言志浴沂，主轴挂鲁定公。"},
    "颜无繇": {"patron": "鲁定公", "start": -550, "end": -481, "axis": "颜无繇颜回父，主轴挂鲁定公。"},
    "商瞿": {"patron": "鲁定公", "start": -520, "end": -458, "axis": "商瞿传易，主轴挂鲁定公。"},
    "高柴": {"patron": "鲁定公", "start": -521, "end": -478, "axis": "高柴子羔愚直，主轴挂鲁定公。"},
    "漆彫开": {"patron": "鲁定公", "start": -538, "end": -472, "axis": "漆彫开辞仕，主轴挂鲁定公。"},
    "公伯缭": {"patron": "鲁定公", "start": -546, "end": -475, "axis": "公伯缭愬子路，主轴挂鲁定公。"},
    "司马耕": {"patron": "鲁定公", "start": -549, "end": -474, "axis": "司马耕子牛问仁，主轴挂鲁定公。"},
    "樊须": {"patron": "鲁定公", "start": -541, "end": -469, "axis": "樊须问稼圃，主轴挂鲁定公。"},
    "有若": {"patron": "鲁定公", "start": -532, "end": -471, "axis": "有若状似孔子被立为师，主轴挂鲁定公。"},
    "公西赤": {"patron": "鲁定公", "start": -519, "end": -473, "axis": "公西赤子华使齐，主轴挂鲁定公。"},
    "巫马施": {"patron": "鲁定公", "start": -534, "end": -466, "axis": "巫马施释孔子知礼，主轴挂鲁定公。"},
}


def _emperor_coords(name: str) -> dict:
    eidx = build_emperor_info_index()
    info = eidx.get(name)
    if not info:
        raise KeyError(f"帝王表无: {name}")
    rec = {
        "emperor": name,
        "dynasty": info.get("dynasty", ""),
        "regime": info.get("regime", ""),
        "civilization": info.get("civilization", "华夏"),
        "dynasty_id": info.get("dynasty_id", ""),
        "regime_id": info.get("regime_id", ""),
        "civilization_id": info.get("civilization_id", "HX"),
        "id": info.get("id", ""),
    }
    out = {
        "四级帝王坐标": name,
        "三级政权坐标": info.get("regime", ""),
        "二级朝代坐标": info.get("dynasty", ""),
        "一级文明坐标": info.get("civilization", "华夏"),
    }
    out.update(ids_from_emperor(rec))
    return out


def _write_protagonists(vol_name: str) -> None:
    seen: dict[str, str] = {}
    for name, cat, _, _ in BLOCKS:
        seen.setdefault(name, cat)
    payload = {
        "work": WORK,
        "vol": VOL,
        "volume_name": vol_name,
        "volume_type_guess": "列传",
        "protagonists": [
            {
                "name": n,
                "category": c,
                "rationale": (
                    f"《{vol_name}》以孔子弟子为传主；{n}有独立叙事段，"
                    f"非孔子本人；P116 起名册及仅年名字一句带过者不引入。"
                ),
            }
            for n, c in seen.items()
        ],
        "excluded_kinds_hint": ["太史公曰", "卷首总论", "弟子名册", "仅年名字一笔带过"],
    }
    pp = protagonists_path(WORK, VOL)
    pp.parent.mkdir(parents=True, exist_ok=True)
    pp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_blocks(total: int) -> None:
    payload = {
        "total_paragraphs": total,
        "excludes": [
            {"paragraph_from": a, "paragraph_to": b, "exclude_reason": r}
            for a, b, r in EXCLUDES
        ],
        "blocks": [
            {
                "name": n,
                "category": c,
                "paragraph_from": pf,
                "paragraph_to": pt,
            }
            for n, c, pf, pt in BLOCKS
        ],
    }
    blocks_path(WORK, VOL).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _patch_entries(sk: dict, vol: str) -> None:
    vol_name = sk.get("volume", "")
    for i, entry in enumerate(sk.get("entries") or []):
        name = (entry.get("史略名称") or "").strip()
        m = ENTRY_META.get(name)
        if not m:
            continue
        cat = entry.get("史略分类", "文臣")
        pf = entry["paragraphs"][0]["paragraph_from"]
        pt = entry["paragraphs"][-1]["paragraph_to"]
        n_para = sum(
            int(b.get("paragraph_to", 0)) - int(b.get("paragraph_from", 0)) + 1
            for b in entry.get("paragraphs") or []
        )
        entry["史略开始年"] = m["start"]
        entry["史略结束年"] = m["end"]
        entry["优先级"] = "P0"
        entry["优先级判定理由"] = f"{name}弟子传主轴叙事，共{n_para}段"
        entry["五级细坐标"] = f"史记·卷{vol}·{cat}·{i + 1:02d}"
        entry["六级段落锚点"] = f"[P{pf}-P{pt}]"
        entry["原文出处"] = f"{vol_name}·P{pf}-P{pt}"
        entry["_needs_llm"] = []
        entry.update(_emperor_coords(m["patron"]))
        af = dict(entry.get("_auto_filled") or {})
        af["_坐标主轴说明"] = m["axis"]
        af["_年LLM依据"] = f"{name}生卒学界主流约前{abs(m['start'])}–前{abs(m['end'])}"
        af["年规则"] = "出生年 → 去世年"
        entry["_auto_filled"] = af


def repair() -> tuple[bool, str]:
    idx = json.loads((INDEX_DIR / f"{WORK}_{VOL}.json").read_text(encoding="utf-8"))
    total = int(idx["total"])
    vol_name = volume_display_name(WORK, VOL, idx)

    _write_protagonists(vol_name)
    _write_blocks(total)

    sk_path = gates.skeleton_path(WORK, VOL)
    if sk_path is not None and sk_path.exists():
        sk_path.unlink()

    sk_path = expand_blocks_to_skeleton(WORK, VOL, idx)
    sk = json.loads(sk_path.read_text(encoding="utf-8"))
    _patch_entries(sk, VOL)
    sk_path.write_text(json.dumps(sk, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    gates.step2_prepare(sk_path)
    gates.step3_write_audit_block(WORK, VOL, sk_path)

    for step in ("1", "2", "3", "4"):
        ok, msg = gates.verify_step(WORK, VOL, step)
        if not ok:
            return False, f"Step{step} 校验失败:\n{msg[-1200:]}"
    gates.step4_finalize(sk_path)

    conn = connect()
    now = utc_now()
    for step in ("1", "2", "3", "4"):
        conn.execute(
            "UPDATE jobs SET status='done', fail_count=0, detail='', finished_at=? "
            "WHERE work_id=? AND vol=? AND step=?",
            (now, WORK, VOL, step),
        )
    conn.commit()
    return True, f"067 {vol_name} 返工完成（{len(sk.get('entries', []))} 条弟子传）"


def main() -> int:
    ok, msg = repair()
    print("✅" if ok else "❌", msg)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
