#!/usr/bin/env python3
"""返工《汉书》042 张耳陈馀传：二人合传。

⛔ 已废止：知识性字段须 Step1/Step4 LLM。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

SKILL_DIR = Path(__file__).resolve().parent
_ROOT = SKILL_DIR.parent
for p in (str(_ROOT), str(SKILL_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from repair_policy import guard_narrative_knowledge_repair  # noqa: E402

guard_narrative_knowledge_repair(__file__)

from coordinate_index import ids_from_emperor  # noqa: E402
from emperor_resolve import build_emperor_info_index  # noqa: E402
from paths_config import get_histograph_root  # noqa: E402

ORCH = _ROOT / "historiography-orchestrator"
if str(ORCH) not in sys.path:
    sys.path.insert(0, str(ORCH))

from lib import gates  # noqa: E402
from lib.adapters.openclaw import expected_skeleton_path  # noqa: E402
from lib.blocks_workflow import blocks_path, volume_display_name  # noqa: E402
from lib.db import connect, utc_now  # noqa: E402
from lib.protagonist_workflow import protagonists_path  # noqa: E402

WORK = "02汉书"
VOL = "042"
INDEX_DIR = get_histograph_root() / "data" / "03索引标注条目" / "段落索引"

META = {
    "张耳": {
        "cat": "武将",
        "ranges": [(2, 2), (7, 9)],
        "quote": "张耳，大梁人也，少时及魏公子毋忌为客。",
        "pri": "P0",
        "reason": "合传主轴之一，巨鹿后相王至佐汉封赵王",
        "patron": "汉高祖",
        "start": -250,
        "end": -203,
        "year_note": "从魏客游外黄至赵王薨，前250–前203",
        "spindle": "本卷后半以佐汉封赵王、袭常山为主线，四级帝王取汉高祖；早年从项梁、项羽见共段事略。",
    },
    "陈馀": {
        "cat": "武将",
        "ranges": [(3, 6)],
        "quote": "陈馀，亦大梁人，好儒术。",
        "pri": "P0",
        "reason": "合传主轴之一，赵大将军至背汉败死",
        "patron": "项羽",
        "start": -250,
        "end": -204,
        "year_note": "与张耳并起至井陉斩，前250–前204",
        "spindle": "本卷以赵地合纵抗秦为主线，陈馀功在赵将；四级帝王取项羽。",
    },
}


def _emperor_coords(name: str) -> dict:
    eidx = build_emperor_info_index()
    info = eidx.get(name) or {}
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


def _owner(name: str) -> Dict[str, str]:
    return {"name": name, "category": META[name]["cat"]}


def build_attribution(total: int) -> List[dict]:
    rows = []
    for p in range(1, total + 1):
        if p == 1:
            rows.append({"paragraph": p, "owners": [], "exclude_reason": "卷首标题"})
        elif p == total:
            rows.append({"paragraph": p, "owners": [], "exclude_reason": "其他"})
        elif p == 2:
            rows.append({"paragraph": p, "owners": [_owner("张耳")]})
        elif 3 <= p <= 6:
            rows.append({"paragraph": p, "owners": [_owner("陈馀")]})
        else:
            rows.append({"paragraph": p, "owners": [_owner("张耳")]})
    return rows


def build_entries(vol_name: str) -> List[dict]:
    entries = []
    for i, (name, m) in enumerate(META.items(), 1):
        ranges: List[Tuple[int, int]] = m["ranges"]
        pf, pt = ranges[0][0], ranges[-1][1]
        prs = [{"volume": vol_name, "paragraph_from": a, "paragraph_to": b} for a, b in ranges]
        e: Dict[str, Any] = {
            "史略ID": f"HANSHU_{VOL}_{i:02d}",
            "史略名称": name,
            "史略分类": m["cat"],
            "史略简介": m["quote"][:18] + "…",
            "主要史料出处": f"《汉书·{vol_name}》",
            "paragraphs": prs,
            "原文字句": m["quote"],
            "优先级": m["pri"],
            "优先级判定理由": m["reason"],
            "史略开始年": m["start"],
            "史略结束年": m["end"],
            "_年LLM依据": m["year_note"],
            "五级细坐标": f"汉书·卷{VOL}·{m['cat']}·{i:02d}",
            "六级段落锚点": f"[P{pf}-P{pt}]",
            "原文出处": f"{vol_name}·P{pf}-P{pt}",
        }
        e.update(_emperor_coords(m["patron"]))
        af = {"_年LLM依据": m["year_note"]}
        if m.get("spindle"):
            af["_坐标主轴说明"] = m["spindle"]
        e["_auto_filled"] = af
        entries.append(e)
    return entries


def main() -> None:
    idx = json.loads((INDEX_DIR / f"{WORK}_{VOL}.json").read_text(encoding="utf-8"))
    total = int(idx["total"])
    vol_name = volume_display_name(WORK, VOL, idx)

    for path in (blocks_path(WORK, VOL), protagonists_path(WORK, VOL)):
        if path.exists():
            path.unlink()

    sk_path = expected_skeleton_path(WORK, VOL, idx)
    if sk_path.exists():
        sk_path.unlink()

    sk = {
        "volume": vol_name,
        "source_file": idx.get("source_file", "").strip(),
        "total_paragraphs": total,
        "volume_type": "纪传叙事",
        "segment_attribution": build_attribution(total),
        "entries": build_entries(vol_name),
    }
    sk_path.write_text(json.dumps(sk, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    gates.step2_prepare(sk_path)
    gates.step3_write_audit_block(WORK, VOL, sk_path)
    gates.step4_prepare(sk_path)
    sk = json.loads(sk_path.read_text(encoding="utf-8"))
    for e in sk.get("entries") or []:
        name = e.get("史略名称", "")
        if name in META and META[name].get("spindle"):
            e.setdefault("_auto_filled", {})["_坐标主轴说明"] = META[name]["spindle"]
        e.pop("_needs_llm", None)
    sk_path.write_text(json.dumps(sk, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for step in ("1", "2", "3"):
        ok, msg = gates.verify_step(WORK, VOL, step)
        if not ok:
            raise SystemExit(f"Step{step}: {msg[-600:]}")
    gates.step4_finalize(sk_path)
    ok, msg = gates.verify_step(WORK, VOL, "4")
    if not ok:
        raise SystemExit(f"Step4: {msg[-600:]}")

    conn = connect()
    now = utc_now()
    for step in ("1", "2", "3", "4"):
        conn.execute(
            "UPDATE jobs SET status='done', fail_count=0, detail='', finished_at=? "
            "WHERE work_id=? AND vol=? AND step=?",
            (now, WORK, VOL, step),
        )
    conn.commit()
    print(f"✅ 卷{VOL} {vol_name}（{len(sk['entries'])} 条）")


if __name__ == "__main__":
    main()
