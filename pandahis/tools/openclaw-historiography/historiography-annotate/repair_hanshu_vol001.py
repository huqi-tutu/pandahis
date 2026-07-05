#!/usr/bin/env python3
"""返工《汉书》001 高帝纪第一上：金标卷单人本纪，汉高祖 P2–79。

⛔ 已废止：知识性字段须 Step1/Step4 LLM。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import List, Tuple

SKILL_DIR = Path(__file__).resolve().parent
_ROOT = SKILL_DIR.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

from repair_policy import guard_narrative_knowledge_repair  # noqa: E402

guard_narrative_knowledge_repair(__file__)

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

WORK = "02汉书"
VOL = "001"
DATA = get_histograph_root() / "data"
INDEX_DIR = DATA / "03索引标注条目" / "段落索引"

BlockSpec = Tuple[str, str, int, int]
ExcludeSpec = Tuple[int, int, str]

BLOCKS: List[BlockSpec] = [
    ("汉高祖", "君王", 2, 79),
]

EXCLUDES: List[ExcludeSpec] = [
    (1, 1, "卷首标题"),
]


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


def main() -> None:
    idx = json.loads((INDEX_DIR / f"{WORK}_{VOL}.json").read_text(encoding="utf-8"))
    total = int(idx["total"])
    vn = volume_display_name(WORK, VOL, idx)

    pp = protagonists_path(WORK, VOL)
    pp.parent.mkdir(parents=True, exist_ok=True)
    pp.write_text(
        json.dumps(
            {
                "work": WORK,
                "vol": VOL,
                "volume_name": vn,
                "volume_type_guess": "本纪",
                "protagonists": [
                    {
                        "name": "汉高祖",
                        "category": "君王",
                        "rationale": f"《{vn}》为汉高祖刘邦本纪上册，叙事主轴为汉高祖。",
                    }
                ],
                "excluded_kinds_hint": ["赞曰", "卷首标题", "其他"],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    blocks_path(WORK, VOL).write_text(
        json.dumps(
            {
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
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    sk_path = gates.skeleton_path(WORK, VOL)
    if sk_path is not None and sk_path.exists():
        sk_path.unlink()

    sk_path = expand_blocks_to_skeleton(WORK, VOL, idx)
    sk = json.loads(sk_path.read_text(encoding="utf-8"))
    entry = sk["entries"][0]
    entry["史略开始年"] = -256
    entry["史略结束年"] = -195
    entry["优先级"] = "P0"
    entry["优先级判定理由"] = "高帝纪上册，汉高祖开国叙事，共78段"
    entry["五级细坐标"] = "汉书·卷001·君王·01"
    entry["六级段落锚点"] = "[P2-P79]"
    entry["原文出处"] = f"{vn}·P2-P79"
    entry["_needs_llm"] = []
    entry.update(_emperor_coords("汉高祖"))
    entry["_auto_filled"] = {
        "_坐标主轴说明": "汉高祖本纪上册，自沛丰起兵至楚汉对峙鸿沟议和。"
    }
    sk_path.write_text(json.dumps(sk, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    gates.step2_prepare(sk_path)
    gates.step3_write_audit_block(WORK, VOL, sk_path)
    gates.step4_prepare(sk_path)

    for step in ("1", "2", "3", "4"):
        ok, msg = gates.verify_step(WORK, VOL, step)
        if not ok:
            raise SystemExit(f"卷{VOL} Step{step} 失败:\n{msg[-1200:]}")
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
    print(f"✅ 汉书卷{VOL} {vn} 返工完成（{len(sk.get('entries', []))} 条）")


if __name__ == "__main__":
    main()
