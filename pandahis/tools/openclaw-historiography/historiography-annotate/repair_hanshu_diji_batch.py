#!/usr/bin/env python3
"""批量返工《汉书》帝纪 002–013：单人本纪块 + 卷首/赞曰 exclude。

⛔ 已废止：知识性字段须 Step1/Step4 LLM。
"""

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
DATA = get_histograph_root() / "data"
INDEX_DIR = DATA / "03索引标注条目" / "段落索引"

BlockSpec = Tuple[str, str, int, int]
ExcludeSpec = Tuple[int, int, str]

# (vol, name, category, p_from, p_to, title_exclude_to, praise_from)
DIJI: List[Tuple[str, str, str, int, int, int, int]] = [
    ("002", "汉高祖", "君王", 2, 69, 1, 70),
    ("003", "汉惠帝", "君王", 2, 30, 1, 31),
    ("004", "吕太后", "宗戚", 2, 17, 1, 18),
    ("005", "汉文帝", "君王", 2, 79, 1, 80),
    ("006", "汉景帝", "君王", 2, 82, 1, 83),
    ("007", "汉武帝", "君王", 2, 271, 1, 272),
    ("008", "汉昭帝", "君王", 2, 82, 1, 83),
    ("009", "汉宣帝", "君王", 2, 147, 1, 148),
    ("010", "汉元帝", "君王", 2, 83, 1, 84),
    ("011", "汉成帝", "君王", 2, 140, 1, 141),
    ("012", "汉哀帝", "君王", 3, 48, 2, 49),  # P49–50 赞曰（跨段）
    ("013", "汉平帝", "君王", 3, 50, 2, 51),
]

PATRON: Dict[str, str] = {
    "吕太后": "汉惠帝",
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


def _load_index(vol: str) -> dict:
    return json.loads((INDEX_DIR / f"{WORK}_{vol}.json").read_text(encoding="utf-8"))


def repair_vol(vol: str, name: str, cat: str, pf: int, pt: int, title_to: int, praise_from: int) -> tuple[bool, str]:
    idx = _load_index(vol)
    total = int(idx["total"])
    vn = volume_display_name(WORK, vol, idx)

    blocks: List[BlockSpec] = [(name, cat, pf, pt)]
    excludes: List[ExcludeSpec] = [(1, title_to, "卷首标题")]
    if praise_from <= total:
        excludes.append((praise_from, total, "其他"))

    pp = protagonists_path(WORK, vol)
    pp.parent.mkdir(parents=True, exist_ok=True)
    pp.write_text(
        json.dumps(
            {
                "work": WORK,
                "vol": vol,
                "volume_name": vn,
                "volume_type_guess": "本纪",
                "protagonists": [
                    {
                        "name": name,
                        "category": cat,
                        "rationale": f"《{vn}》叙事主轴：{name}（{cat}）",
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

    blocks_path(WORK, vol).write_text(
        json.dumps(
            {
                "total_paragraphs": total,
                "excludes": [
                    {"paragraph_from": a, "paragraph_to": b, "exclude_reason": r}
                    for a, b, r in excludes
                ],
                "blocks": [
                    {
                        "name": n,
                        "category": c,
                        "paragraph_from": bpf,
                        "paragraph_to": bpt,
                    }
                    for n, c, bpf, bpt in blocks
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    sk_path = gates.skeleton_path(WORK, vol)
    if sk_path is not None and sk_path.exists():
        sk_path.unlink()

    sk_path = expand_blocks_to_skeleton(WORK, vol, idx)
    sk = json.loads(sk_path.read_text(encoding="utf-8"))
    entry = sk["entries"][0]
    eidx = build_emperor_info_index()
    info = eidx.get(name) or {}
    start = int(info.get("即位时间") or info.get("accession") or -200)
    end = int(info.get("退位时间") or info.get("death") or start)
    if cat == "君王":
        entry.update(_emperor_coords(name))
    elif PATRON.get(name):
        entry.update(_emperor_coords(PATRON[name]))
    entry["史略开始年"] = start
    entry["史略结束年"] = end
    entry["优先级"] = "P0"
    entry["优先级判定理由"] = f"{vn}本纪主轴，P{pf}–P{pt}"
    entry["五级细坐标"] = f"汉书·卷{vol}·{cat}·01"
    entry["六级段落锚点"] = f"[P{pf}-P{pt}]"
    entry["原文出处"] = f"{vn}·P{pf}-P{pt}"
    entry["_needs_llm"] = []
    if cat == "宗戚" and name == "吕太后":
        entry["_auto_filled"] = {"_坐标主轴说明": "高后纪叙事主轴锚汉惠帝朝（临朝称制）。"}
    sk_path.write_text(json.dumps(sk, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    gates.step2_prepare(sk_path)
    gates.step3_write_audit_block(WORK, vol, sk_path)
    gates.step4_prepare(sk_path)

    for step in ("1", "2", "3", "4"):
        ok, msg = gates.verify_step(WORK, vol, step)
        if not ok:
            return False, f"Step{step}: {msg[-600:]}"
    gates.step4_finalize(sk_path)

    conn = connect()
    now = utc_now()
    for step in ("1", "2", "3", "4"):
        conn.execute(
            "UPDATE jobs SET status='done', fail_count=0, detail='', finished_at=? "
            "WHERE work_id=? AND vol=? AND step=?",
            (now, WORK, vol, step),
        )
    conn.commit()
    return True, f"卷{vol} {vn}（1 条）"


def main() -> None:
    vols = sys.argv[1:] if len(sys.argv) > 1 else [r[0] for r in DIJI]
    cfg_map = {r[0]: r[1:] for r in DIJI}
    failed = []
    for vol in vols:
        vol = vol.zfill(3)
        if vol not in cfg_map:
            print(f"跳过: {vol}")
            continue
        name, cat, pf, pt, title_to, praise_from = cfg_map[vol]
        print(f"\n=== {WORK} 卷{vol} {name} ===")
        try:
            ok, msg = repair_vol(vol, name, cat, pf, pt, title_to, praise_from)
            print("✅" if ok else "❌", msg)
            if not ok:
                failed.append(vol)
        except Exception as e:
            print(f"❌ 异常: {e}")
            failed.append(vol)
    if failed:
        raise SystemExit(f"失败: {failed}")
    print("\n✅ 帝纪批量完成")


if __name__ == "__main__":
    main()
