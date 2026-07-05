#!/usr/bin/env python3
"""返工《史记》005 秦本纪：删重复「秦始皇」条目（主轴在 006），修正卷末君王块与 exclude。"""

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

from paths_config import get_histograph_root  # noqa: E402

ORCH = _ROOT / "historiography-orchestrator"
if str(ORCH) not in sys.path:
    sys.path.insert(0, str(ORCH))

from lib import gates  # noqa: E402
from lib.blocks_workflow import blocks_path, expand_blocks_to_skeleton, volume_display_name  # noqa: E402
from lib.protagonist_workflow import protagonists_path  # noqa: E402
from lib.db import connect, utc_now  # noqa: E402

WORK = "01史记"
VOL = "005"
DATA = get_histograph_root() / "data"
INDEX_DIR = DATA / "03索引标注条目" / "段落索引"

BlockSpec = Tuple[str, str, int, int]
ExcludeSpec = Tuple[int, int, str]

# P6–P20 与旧 blocks 一致；P21 起按段落索引重划（穆公延至 P58）
BLOCKS: List[BlockSpec] = [
    ("秦非子", "君王", 1, 7),
    ("秦仲", "君王", 8, 8),
    ("秦庄公", "君王", 9, 9),
    ("秦襄公", "君王", 10, 10),
    ("秦文公", "君王", 11, 13),
    ("秦宁公", "君王", 14, 15),
    ("秦武公", "君王", 16, 17),
    ("秦德公", "君王", 18, 18),
    ("秦宣公", "君王", 19, 19),
    ("秦成公", "君王", 20, 20),
    ("秦穆公", "君王", 21, 58),
    ("秦康公", "君王", 61, 61),
    ("秦共公", "君王", 62, 62),
    ("秦桓公", "君王", 63, 63),
    ("秦景公", "君王", 64, 64),
    ("秦哀公", "君王", 65, 67),
    ("秦惠公", "君王", 68, 68),
    ("秦悼公", "君王", 69, 69),
    ("秦简公", "君王", 70, 71),
    ("秦悼公", "君王", 72, 72),
    ("秦厉共公", "君王", 73, 74),
    ("秦怀公", "君王", 75, 75),
    ("秦灵公", "君王", 76, 76),
    ("秦简公", "君王", 77, 77),
    ("秦惠公", "君王", 78, 78),
    ("秦出子", "君王", 79, 79),
    ("秦献公", "君王", 81, 81),
    ("秦孝公", "君王", 82, 93),
    ("秦惠文王", "君王", 94, 97),
    ("秦武王", "君王", 98, 98),
    ("秦昭襄王", "君王", 99, 113),
    ("秦孝文王", "君王", 114, 114),
    ("秦庄襄王", "君王", 115, 115),
]

EXCLUDES: List[ExcludeSpec] = [
    (59, 60, "其他"),  # 君子曰论缪公
    (80, 80, "过渡叙事"),
    (116, 116, "其他"),  # 始皇事迹详见 006 本纪
    (117, 117, "太史公曰"),
    (118, 118, "其他"),  # 太史公曰续论
]


def _write_protagonists(vol_name: str) -> None:
    seen: dict[str, str] = {}
    for name, cat, _, _ in BLOCKS:
        seen.setdefault(name, cat)
    payload = {
        "work": WORK,
        "vol": VOL,
        "volume_name": vol_name,
        "volume_type_guess": "本纪",
        "protagonists": [
            {
                "name": n,
                "category": c,
                "rationale": (
                    f"《{vol_name}》历代秦君本纪分块；"
                    f"秦始皇主轴在《秦始皇本纪》，本卷 P116 总述不另立条。"
                ),
            }
            for n, c in seen.items()
        ],
        "excluded_kinds_hint": ["太史公曰", "世系链", "过渡叙事", "其他"],
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
            {"name": n, "category": c, "paragraph_from": pf, "paragraph_to": pt}
            for n, c, pf, pt in BLOCKS
        ],
    }
    blocks_path(WORK, VOL).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


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

    # 卷末庄襄王条：注明始皇另卷
    for entry in sk.get("entries") or []:
        if (entry.get("史略名称") or "").strip() == "秦庄襄王":
            af = dict(entry.get("_auto_filled") or {})
            af["_坐标主轴说明"] = (
                "本纪以庄襄王即位至卒为主线；子政立为秦王及统一事见《秦始皇本纪》，"
                "本卷 P116 总述不另立秦始皇条目。"
            )
            entry["_auto_filled"] = af
            break

    names = {(e.get("史略名称") or "").strip() for e in sk.get("entries") or []}
    if "秦始皇" in names:
        return False, "返工后仍含秦始皇条目"

    sk_path.write_text(json.dumps(sk, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    gates.step2_prepare(sk_path)
    gates.step3_write_audit_block(WORK, VOL, sk_path)

    prep_ok, prep_msg = gates.step4_prepare(sk_path)
    if not prep_ok:
        return False, f"Step4 prepare 失败:\n{prep_msg[-800:]}"
    gates.step4_shiji_person_fallback(sk_path, WORK, VOL)

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
    return True, f"005 {vol_name} 返工完成（{len(sk.get('entries', []))} 条，已去秦始皇重复）"


def main() -> int:
    ok, msg = repair()
    print("✅" if ok else "❌", msg)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
