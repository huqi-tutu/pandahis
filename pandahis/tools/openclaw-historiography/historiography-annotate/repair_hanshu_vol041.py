#!/usr/bin/env python3
"""返工《汉书》041 陈胜项籍传：二人合传块界 + 赞曰 exclude。

⛔ 已废止：知识性字段须 Step1/Step4 LLM。本脚本仅保留供对照，运行将 exit 2。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

SKILL_DIR = Path(__file__).resolve().parent
_ROOT = SKILL_DIR.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

from repair_policy import guard_narrative_knowledge_repair  # noqa: E402

guard_narrative_knowledge_repair(__file__)

from paths_config import get_histograph_root  # noqa: E402

ORCH = _ROOT / "historiography-orchestrator"
if str(ORCH) not in sys.path:
    sys.path.insert(0, str(ORCH))

from lib import gates  # noqa: E402
from lib.adapters.openclaw import expected_skeleton_path  # noqa: E402
from lib.blocks_workflow import blocks_path, volume_display_name  # noqa: E402
from lib.db import connect, utc_now  # noqa: E402
from lib.protagonist_workflow import protagonists_path  # noqa: E402

from coordinate_index import ids_from_emperor  # noqa: E402
from emperor_resolve import build_emperor_info_index  # noqa: E402

WORK = "02汉书"
VOL = "041"
DATA = get_histograph_root() / "data"
INDEX_DIR = DATA / "03索引标注条目" / "段落索引"

YEAR_META = {
    "陈胜": (-209, -196, "起事至败亡约前209–前196（生年不详，与《史记·陈涉世家》同轴）"),
    "吴广": (-209, -208, "与陈胜共起大泽乡至荥阳被杀，前209–前208"),
    "项籍": (-232, -202, "少学兵法至乌江自刭，前232–前202（初起年二十四推生年）"),
    "项梁": (-250, -208, "会稽起兵至定陶战死，前250–前208"),
}

PATRON = {
    "陈胜": "秦二世",
    "吴广": "秦二世",
    "项籍": "项羽",
    "项梁": "项羽",
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


def _patch_entries(entries: List[Dict[str, Any]]) -> None:
    for e in entries:
        name = e["史略名称"]
        start, end, year_note = YEAR_META[name]
        e["史略开始年"] = start
        e["史略结束年"] = end
        e["_年LLM依据"] = year_note
        patron = PATRON.get(name)
        if patron:
            e.update(_emperor_coords(patron))
        e.setdefault("_auto_filled", {})
        if isinstance(e["_auto_filled"], dict):
            e["_auto_filled"]["_年LLM依据"] = year_note
        if name in ("项籍", "项梁"):
            e["_auto_filled"]["_坐标主轴说明"] = (
                "本卷以项氏起兵灭秦、西楚分封至垓下为主线，四级帝王取项羽；"
                "早年从项燕、楚义帝见共段事略。"
            )
        e.pop("_needs_llm", None)


def _owner(name: str) -> Dict[str, str]:
    cats = {
        "陈胜": "庶众",
        "吴广": "庶众",
        "项籍": "武将",
        "项梁": "武将",
    }
    return {"name": name, "category": cats[name]}


def build_segment_attribution(total: int) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for p in range(1, total + 1):
        if p == 1:
            rows.append({"paragraph": p, "owners": [], "exclude_reason": "卷首标题"})
        elif p == total:
            rows.append({"paragraph": p, "owners": [], "exclude_reason": "其他"})
        elif p == 2:
            rows.append({"paragraph": p, "owners": [_owner("陈胜")]})
        elif p == 3:
            rows.append({"paragraph": p, "owners": [_owner("吴广")]})
        elif 4 <= p <= 8:
            rows.append({"paragraph": p, "owners": [_owner("陈胜")]})
        elif 9 <= p <= 12:
            owner = _owner("项梁") if 10 <= p <= 12 else _owner("项籍")
            rows.append({"paragraph": p, "owners": [owner]})
        else:
            rows.append({"paragraph": p, "owners": [_owner("项籍")]})
    return rows


def build_entries(paras: List[str], vol_name: str) -> List[Dict[str, Any]]:
    specs = [
        ("陈胜", "庶众", [(2, 2), (4, 8)], "陈胜字涉，阳城人。", "P0",
         "大泽乡首义、建张楚，秦末农民战争标志性人物"),
        ("吴广", "庶众", [(3, 3)], "吴广，字叔，阳夏人也。", "P0",
         "与陈胜共起、为假王监军，荥阳战役关键配角"),
        ("项籍", "武将", [(9, 9), (13, 23)], "项籍字羽，下相人也。", "P0",
         "西楚霸王，灭秦分封至垓下，列传后半主轴"),
        ("项梁", "武将", [(10, 12)], "其季父梁，梁父即楚名将项燕者也。", "P1",
         "楚将项燕之后，会稽起兵、立怀王，定陶战死"),
    ]
    entries: List[Dict[str, Any]] = []
    for i, (name, cat, ranges, quote, pri, reason) in enumerate(specs, 1):
        lo0, hi0 = ranges[0]
        q = quote if len(quote) >= 8 else "\n".join(paras[lo0 - 1 : hi0])[:120]
        prs = [{"volume": vol_name, "paragraph_from": lo, "paragraph_to": hi} for lo, hi in ranges]
        pf = ranges[0][0]
        pt = ranges[-1][1]
        start, end, year_note = YEAR_META[name]
        entries.append({
            "史略ID": f"HANSHU_{VOL}_{i:02d}",
            "史略名称": name,
            "史略分类": cat,
            "史略简介": q[:18] + ("…" if len(q) > 18 else ""),
            "主要史料出处": f"《汉书·{vol_name}》",
            "paragraphs": prs,
            "原文字句": q[:120],
            "优先级": pri,
            "优先级判定理由": reason,
            "史略开始年": start,
            "史略结束年": end,
            "_年LLM依据": year_note,
            "五级细坐标": f"汉书·卷{VOL}·{cat}·{i:02d}",
            "六级段落锚点": f"[P{pf}-P{pt}]",
            "原文出处": f"{vol_name}·P{pf}-P{pt}",
        })
    _patch_entries(entries)
    return entries


def _mark_jobs_done() -> None:
    conn = connect()
    now = utc_now()
    for step in ("1", "2", "3", "4"):
        conn.execute(
            "UPDATE jobs SET status='done', fail_count=0, detail='', finished_at=? "
            "WHERE work_id=? AND vol=? AND step=?",
            (now, WORK, VOL, step),
        )
    conn.commit()


def main() -> None:
    idx = json.loads((INDEX_DIR / f"{WORK}_{VOL}.json").read_text(encoding="utf-8"))
    total = int(idx["total"])
    vol_name = volume_display_name(WORK, VOL, idx)
    paras = [p.get("text", "") for p in idx.get("paragraphs") or []]

    bp = blocks_path(WORK, VOL)
    if bp.exists():
        bp.unlink()
    pp = protagonists_path(WORK, VOL)
    if pp.exists():
        pp.unlink()

    pp.parent.mkdir(parents=True, exist_ok=True)
    pp.write_text(
        json.dumps(
            {
                "work": WORK,
                "vol": VOL,
                "volume_name": vol_name,
                "volume_type_guess": "列传",
                "protagonists": [
                    {"name": "陈胜", "category": "庶众", "rationale": "合传前半主轴"},
                    {"name": "项籍", "category": "武将", "rationale": "合传后半主轴"},
                    {"name": "吴广", "category": "庶众", "rationale": "陈胜起义核心配角"},
                    {"name": "项梁", "category": "武将", "rationale": "项籍起兵引路人"},
                ],
                "excluded_kinds_hint": ["赞曰", "卷首标题", "其他"],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    sk_path = expected_skeleton_path(WORK, VOL, idx)
    if sk_path.exists():
        sk_path.unlink()

    sk = {
        "volume": vol_name,
        "source_file": (idx.get("source_file") or "").strip(),
        "total_paragraphs": total,
        "volume_type": "纪传叙事",
        "segment_attribution": build_segment_attribution(total),
        "entries": build_entries(paras, vol_name),
    }
    sk_path.parent.mkdir(parents=True, exist_ok=True)
    sk_path.write_text(json.dumps(sk, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    gates.step2_prepare(sk_path)
    sk = json.loads(sk_path.read_text(encoding="utf-8"))
    _patch_entries(sk.get("entries") or [])
    sk_path.write_text(json.dumps(sk, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    gates.step3_write_audit_block(WORK, VOL, sk_path)
    gates.step4_prepare(sk_path)
    sk = json.loads(sk_path.read_text(encoding="utf-8"))
    _patch_entries(sk.get("entries") or [])
    sk_path.write_text(json.dumps(sk, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for step in ("1", "2", "3",):
        ok, msg = gates.verify_step(WORK, VOL, step)
        if not ok:
            raise SystemExit(f"Step{step} 失败: {msg[-800:]}")

    gates.step4_finalize(sk_path)
    ok, msg = gates.verify_step(WORK, VOL, "4")
    if not ok:
        raise SystemExit(f"Step4 失败: {msg[-800:]}")
    _mark_jobs_done()
    print(f"✅ 卷{VOL} {vol_name}（{len(sk['entries'])} 条）")


if __name__ == "__main__":
    main()
