#!/usr/bin/env python3
"""《汉书》列传合传批量 repair（043+）：白名单门禁 + 人工块界。

⛔ 已废止：知识性字段须 Step1/Step4 LLM。
"""

from __future__ import annotations

import json
import re
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
from hanshu_hezhuan_gate import validate_repair_plan  # noqa: E402
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
INDEX_DIR = get_histograph_root() / "data" / "03索引标注条目" / "段落索引"

Range = Tuple[int, int]
EntrySpec = Tuple[
    str, str, List[Range], str, str, str, str, int, int, str, str,
]

# vol → (paragraph_owner map as list of (p_from,p_to,name), entry_specs)
# 块界来自段落精读；卷名人物来自 hanshu_hezhuan_gate 白名单
VOL_PLANS: Dict[str, Tuple[List[Tuple[int, int, str]], List[EntrySpec], List[Tuple[int, int]]]] = {
    "043": (
        [(2, 2, "魏豹"), (3, 5, "田儋"), (7, 9, "韩王信")],
        [
            ("魏豹", "君王", [(2, 2)], "", "P0",
             "西魏王，叛汉被杀", "魏豹", -210, -204,
             "从复魏至守荥阳被杀，前210–前204", ""),
            ("田儋", "君王", [(3, 5)], "", "P0",
             "齐王田儋、弟横继统", "田儋", -209, -202,
             "自立齐王至横走梁，前209–前202",
             "本卷齐王宗族叙事；韩王信见后段。"),
            ("韩王信", "君王", [(7, 9)], "", "P0",
             "韩王信叛汉联匈奴", "韩王信", -205, -196,
             "封韩王至降匈奴被杀，前205–前196",
             "本卷后半主轴，四级帝王取汉高祖；魏豹、田儋见前段。"),
        ],
        [(6, 6)],  # 田横就义→韩王信过渡
    ),
    "044": (
        [
            (2, 12, "韩信"), (13, 16, "彭越"), (17, 22, "黥布"),
            (23, 24, "卢绾"), (25, 25, "吴芮"),
        ],
        [
            ("韩信", "武将", [(2, 12)], "", "P0",
             "淮阴侯，汉初名将", "汉高祖", -230, -196,
             "从拜将灭楚至钟室斩，前230–前196", ""),
            ("彭越", "武将", [(13, 16)], "", "P0",
             "梁王，游击断楚粮", "汉高祖", -250, -196,
             "从巨野泽起至诛醢，前250–前196", ""),
            ("黥布", "武将", [(17, 22)], "", "P0",
             "淮南王，反汉被杀", "汉高祖", -250, -195,
             "从番君起兵至长沙被杀，前250–前195", ""),
            ("卢绾", "武将", [(23, 24)], "", "P0",
             "燕王，叛逃匈奴", "汉高祖", -250, -194,
             "从高祖起至亡匈奴，前250–前194", ""),
            ("吴芮", "武将", [(25, 25)], "", "P1",
             "长沙文王，番君之后", "汉高祖", -210, -178,
             "从诸侯入关封长沙王，前210–前178", ""),
        ],
        [],
    ),
    "045": (
        [(2, 2, "荆王"), (3, 4, "燕王"), (5, 13, "刘濞")],
        [
            ("荆王", "君王", [(2, 2)], "", "P0",
             "荆王刘贾，垓下后封", "荆王", -210, -196,
             "从击项羽至为黥布所杀，前210–前196", ""),
            ("燕王", "君王", [(3, 4)], "", "P0",
             "燕王刘泽，诛吕氏", "燕王", -220, -179,
             "从击陈豨至王燕，前220–前179", ""),
            ("刘濞", "君王", [(5, 13)], "", "P0",
             "吴王，七国之乱", "刘濞", -216, -154,
             "封吴至东越斩首，前216–前154", ""),
        ],
        [],
    ),
    "047": (
        [(2, 4, "季布"), (5, 5, "栾布"), (6, 7, "田叔")],
        [
            ("季布", "武将", [(2, 4)], "", "P0",
             "楚将，汉河东守", "汉高祖", -250, -170,
             "从项羽至景帝时卒，前250–前170", ""),
            ("栾布", "武将", [(5, 5)], "", "P0",
             "哭彭越头，封鄃侯", "汉高祖", -250, -145,
             "从彭越客至燕相，前250–前145", ""),
            ("田叔", "武将", [(6, 7)], "", "P0",
             "随张敖至鲁相", "汉高祖", -230, -140,
             "从赵王敖至景帝时卒，前230–前140", ""),
        ],
        [],
    ),
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


def _build_attribution(
    total: int,
    owners: List[Tuple[int, int, str]],
    excludes: List[Tuple[int, int]],
) -> List[dict]:
    pmap: Dict[int, str] = {}
    for pf, pt, name in owners:
        for p in range(pf, pt + 1):
            pmap[p] = name
    ex = set()
    for pf, pt in excludes:
        for p in range(pf, pt + 1):
            ex.add(p)
    rows = []
    for p in range(1, total + 1):
        if p == 1:
            rows.append({"paragraph": p, "owners": [], "exclude_reason": "卷首标题"})
        elif p == total:
            rows.append({"paragraph": p, "owners": [], "exclude_reason": "其他"})
        elif p in ex:
            rows.append({"paragraph": p, "owners": [], "exclude_reason": "过渡叙事"})
        elif p in pmap:
            n = pmap[p]
            rows.append({"paragraph": p, "owners": [{"name": n, "category": _cat_for(n)}]})
        else:
            raise ValueError(f"P{p} 未分配归属")
    return rows


def _cat_for(name: str) -> str:
    for specs in VOL_PLANS.values():
        for spec in specs[1]:
            if spec[0] == name:
                return spec[1]
    return "武将"


def _para_map(idx: dict) -> Dict[int, str]:
    return {int(p["id"]): p.get("text", "") for p in idx.get("paragraphs") or []}


def _quote_from_para(paras: Dict[int, str], pf: int) -> str:
    return re.sub(r"\s+", "", paras.get(pf, ""))[:120]


def _build_entries(
    vol: str, vol_name: str, specs: List[EntrySpec], paras: Dict[int, str],
) -> List[dict]:
    entries = []
    for i, spec in enumerate(specs, 1):
        name, cat, ranges, quote, pri, reason, patron, start, end, year_note, spindle = spec
        pf, pt = ranges[0][0], ranges[-1][1]
        prs = [{"volume": vol_name, "paragraph_from": a, "paragraph_to": b} for a, b in ranges]
        quote = _quote_from_para(paras, ranges[0][0])
        e: Dict[str, Any] = {
            "史略ID": f"HANSHU_{vol}_{i:02d}",
            "史略名称": name,
            "史略分类": cat,
            "史略简介": quote[:18] + ("…" if len(quote) > 18 else ""),
            "主要史料出处": f"《汉书·{vol_name}》",
            "paragraphs": prs,
            "原文字句": quote,
            "优先级": pri,
            "优先级判定理由": reason,
            "史略开始年": start,
            "史略结束年": end,
            "_年LLM依据": year_note,
            "五级细坐标": f"汉书·卷{vol}·{cat}·{i:02d}",
            "六级段落锚点": f"[P{pf}-P{pt}]",
            "原文出处": f"{vol_name}·P{pf}-P{pt}",
        }
        if cat == "君王":
            e.update(_emperor_coords(name))
        elif patron:
            e.update(_emperor_coords(patron))
        af: Dict[str, str] = {"_年LLM依据": year_note}
        if spindle:
            af["_坐标主轴说明"] = spindle
        elif end - start >= 30 and cat in ("武将", "文臣", "庶众", "宦官"):
            af["_坐标主轴说明"] = (
                f"本卷以{reason[:24]}为主线，四级帝王取{patron}；"
                f"合传他段见共段事略。"
            )
        e["_auto_filled"] = af
        entries.append(e)
    return entries


def _patch_entries_from_plan(entries: List[dict], specs: List[EntrySpec], paras: Dict[int, str]) -> None:
    for e, spec in zip(entries, specs):
        name, cat, ranges, _, pri, reason, patron, start, end, year_note, spindle = spec
        pf = ranges[0][0]
        e["史略名称"] = name
        e["史略分类"] = cat
        e["优先级"] = pri
        e["优先级判定理由"] = reason
        e["史略开始年"] = start
        e["史略结束年"] = end
        e["_年LLM依据"] = year_note
        quote = _quote_from_para(paras, pf)
        e["原文字句"] = quote
        e["史略简介"] = quote[:18] + ("…" if len(quote) > 18 else "")
        if cat == "君王":
            e.update(_emperor_coords(name))
        elif patron:
            e.update(_emperor_coords(patron))
        af = dict(e.get("_auto_filled") or {})
        af["_年LLM依据"] = year_note
        if spindle:
            af["_坐标主轴说明"] = spindle
        elif end - start >= 30 and cat in ("武将", "文臣", "庶众", "宦官"):
            af["_坐标主轴说明"] = (
                f"本卷以{reason[:24]}为主线，四级帝王取{patron}；"
                f"合传他段见共段事略。"
            )
        e["_auto_filled"] = af
        e.pop("_needs_llm", None)


def repair_vol(vol: str) -> Tuple[bool, str]:
    vol = vol.zfill(3)
    if vol not in VOL_PLANS:
        return False, f"无 repair 配方: {vol}"
    owner_plan, entry_specs, exclude_plan = VOL_PLANS[vol]
    idx = json.loads((INDEX_DIR / f"{WORK}_{vol}.json").read_text(encoding="utf-8"))
    total = int(idx["total"])
    src = (idx.get("source_file") or "").strip()
    vol_name = volume_display_name(WORK, vol, idx)
    paras = _para_map(idx)

    entry_names = [s[0] for s in entry_specs]
    ok_gate, gate_msg = validate_repair_plan(src, entry_names)
    if not ok_gate:
        return False, f"合传门禁未过: {gate_msg}"

    for path in (blocks_path(WORK, vol), protagonists_path(WORK, vol)):
        if path.exists():
            path.unlink()

    sk_path = expected_skeleton_path(WORK, vol, idx)
    if sk_path.exists():
        sk_path.unlink()

    sk = {
        "volume": vol_name,
        "source_file": src,
        "total_paragraphs": total,
        "volume_type": "纪传叙事",
        "segment_attribution": _build_attribution(total, owner_plan, exclude_plan),
        "entries": _build_entries(vol, vol_name, entry_specs, paras),
    }
    sk_path.write_text(json.dumps(sk, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    gates.step2_prepare(sk_path)
    sk = json.loads(sk_path.read_text(encoding="utf-8"))
    _patch_entries_from_plan(sk.get("entries") or [], entry_specs, paras)
    sk_path.write_text(json.dumps(sk, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    gates.step3_write_audit_block(WORK, vol, sk_path)
    gates.step4_prepare(sk_path)
    sk = json.loads(sk_path.read_text(encoding="utf-8"))
    _patch_entries_from_plan(sk.get("entries") or [], entry_specs, paras)
    sk_path.write_text(json.dumps(sk, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for step in ("1", "2", "3"):
        ok, msg = gates.verify_step(WORK, vol, step)
        if not ok:
            return False, f"Step{step}: {msg[-500:]}"
    gates.step4_finalize(sk_path)
    ok, msg = gates.verify_step(WORK, vol, "4")
    if not ok:
        return False, f"Step4: {msg[-500:]}"

    conn = connect()
    now = utc_now()
    for step in ("1", "2", "3", "4"):
        conn.execute(
            "UPDATE jobs SET status='done', fail_count=0, detail='', finished_at=? "
            "WHERE work_id=? AND vol=? AND step=?",
            (now, WORK, vol, step),
        )
    conn.commit()
    return True, f"卷{vol} {vol_name}（{len(entry_names)} 条）| {gate_msg}"


def main() -> None:
    vols = sys.argv[1:] if len(sys.argv) > 1 else list(VOL_PLANS.keys())
    failed = []
    for vol in vols:
        vol = vol.zfill(3)
        print(f"\n=== {WORK} 卷{vol} ===")
        try:
            ok, msg = repair_vol(vol)
            print("✅" if ok else "❌", msg)
            if not ok:
                failed.append(vol)
        except Exception as e:
            print(f"❌ 异常: {e}")
            failed.append(vol)
    if failed:
        raise SystemExit(f"失败: {failed}")
    print("\n✅ 列传 batch 完成")


if __name__ == "__main__":
    main()
