#!/usr/bin/env python3
"""批量返工《史记》世家卷 031–060（统一诸侯世系专则 + 外戚/功臣专则）。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

SKILL_DIR = Path(__file__).resolve().parent
_ROOT = SKILL_DIR.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

from coordinate_index import build_emperor_index, ids_from_emperor  # noqa: E402
from emperor_resolve import build_emperor_info_index  # noqa: E402
from paths_config import get_histograph_root  # noqa: E402

ORCH = _ROOT / "historiography-orchestrator"
if str(ORCH) not in sys.path:
    sys.path.insert(0, str(ORCH))

from lib import gates  # noqa: E402
from lib.blocks_workflow import blocks_path, expand_blocks_to_skeleton  # noqa: E402
from lib.protagonist_workflow import protagonists_path  # noqa: E402
from lib.db import connect, utc_now  # noqa: E402

WORK = "01史记"
DATA = get_histograph_root() / "data"
INDEX_DIR = DATA / "03索引标注条目" / "段落索引"
ANNOT_DIR = DATA / "05工作流中间产物" / "标注"

# (name, category, p_from, p_to)
BlockSpec = tuple[str, str, int, int]
ExcludeSpec = tuple[int, int, str]


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


from shiji_jiashi_repairs_data import all_jiashi_vols, build_all_repairs  # noqa: E402

REPAIRS: Dict[str, dict] = build_all_repairs()


def _load_index(vol: str) -> dict:
    p = INDEX_DIR / f"{WORK}_{vol}.json"
    return json.loads(p.read_text(encoding="utf-8"))


def _write_protagonists(vol: str, blocks: List[BlockSpec], vol_name: str) -> None:
    seen: dict[str, str] = {}
    for name, cat, _, _ in blocks:
        if name not in seen:
            seen[name] = cat
    protagonists = [
        {
            "name": n,
            "category": c,
            "rationale": f"《{vol_name}》叙事主轴：{n}（{c}）",
        }
        for n, c in seen.items()
    ]
    payload = {
        "work": WORK,
        "vol": vol,
        "volume_name": vol_name,
        "volume_type_guess": "世家",
        "protagonists": protagonists,
        "excluded_kinds_hint": ["太史公曰", "世系链", "卷首标题", "其他"],
    }
    pp = protagonists_path(WORK, vol)
    pp.parent.mkdir(parents=True, exist_ok=True)
    pp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_blocks(vol: str, blocks: List[BlockSpec], excludes: List[ExcludeSpec], total: int) -> None:
    payload = {
        "total_paragraphs": total,
        "excludes": [
            {"paragraph_from": a, "paragraph_to": b, "exclude_reason": r}
            for a, b, r in excludes
        ],
        "blocks": [
            {
                "name": n,
                "category": c,
                "paragraph_from": pf,
                "paragraph_to": pt,
            }
            for n, c, pf, pt in blocks
        ],
    }
    bp = blocks_path(WORK, vol)
    bp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _resolve_entry_meta(
    name: str,
    cat: str,
    pf: int,
    pt: int,
    cfg: dict,
    i: int,
) -> Optional[dict]:
    metas_raw = cfg.get("entry_meta")
    n_seg = pt - pf + 1
    if metas_raw == "auto":
        m: dict = {"reason": f"{name}独立叙事块，共{n_seg}段"}
    elif isinstance(metas_raw, dict):
        m = dict(metas_raw.get(name) or {})
        if not m:
            m = {"reason": f"{name}独立叙事块，共{n_seg}段"}
    elif isinstance(metas_raw, list):
        m = dict(metas_raw[i]) if i < len(metas_raw) else {}
        if not m:
            m = {"reason": f"{name}独立叙事块，共{n_seg}段"}
    else:
        return None
    if cat in ("君王", "诸侯") and m.get("start") is None:
        info = build_emperor_info_index().get(name)
        if info:
            m.setdefault("start", info.get("start_year"))
            m.setdefault("end", info.get("end_year"))
    return m


def _patch_entries(sk: dict, vol: str, cfg: dict) -> None:
    vol_name = sk.get("volume", "")
    for i, entry in enumerate(sk.get("entries") or []):
        name = entry.get("史略名称", "")
        cat = entry.get("史略分类", "")
        m = _resolve_entry_meta(
            name,
            cat,
            entry["paragraphs"][0]["paragraph_from"],
            entry["paragraphs"][-1]["paragraph_to"],
            cfg,
            i,
        )
        if not m:
            continue
        pf = entry["paragraphs"][0]["paragraph_from"]
        pt = entry["paragraphs"][-1]["paragraph_to"]
        if m.get("start") is not None:
            entry["史略开始年"] = m["start"]
        if m.get("end") is not None:
            entry["史略结束年"] = m["end"]
        entry["优先级"] = "P0"
        entry["优先级判定理由"] = m["reason"]
        entry["五级细坐标"] = f"史记·卷{vol}·{cat}·{i + 1:02d}"
        entry["六级段落锚点"] = f"[P{pf}-P{pt}]"
        entry["原文出处"] = f"{vol_name}·P{pf}-P{pt}"
        entry["_needs_llm"] = []
        if cat in ("君王", "诸侯"):
            coords = _emperor_coords(name)
            entry.update(coords)
        elif m.get("patron"):
            entry.update(_emperor_coords(m["patron"]))
        af: dict = {}
        if m.get("axis"):
            af["_坐标主轴说明"] = m["axis"]
        if af:
            entry["_auto_filled"] = af


def repair_vol(vol: str) -> tuple[bool, str]:
    cfg = REPAIRS[vol]
    blocks: List[BlockSpec] = list(cfg["blocks"])
    excludes: List[ExcludeSpec] = list(cfg["excludes"])
    idx = _load_index(vol)
    total = int(idx["total"])
    vol_name = idx.get("source_file", "").split("_")[-1].replace(".txt", "")
    # volume display from index path
    from lib.blocks_workflow import volume_display_name

    vn = volume_display_name(WORK, vol, idx)

    _write_protagonists(vol, blocks, vn)
    _write_blocks(vol, blocks, excludes, total)

    sk_path = gates.skeleton_path(WORK, vol)
    if sk_path is not None and sk_path.exists():
        sk_path.unlink()

    sk_path = expand_blocks_to_skeleton(WORK, vol, idx)
    sk = json.loads(sk_path.read_text(encoding="utf-8"))
    _patch_entries(sk, vol, cfg)
    sk_path.write_text(json.dumps(sk, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    gates.step2_prepare(sk_path)
    gates.step3_write_audit_block(WORK, vol, sk_path)

    logs: List[str] = []
    for step in ("1", "2", "3"):
        ok, msg = gates.verify_step(WORK, vol, step)
        logs.append(f"step{step}: {'OK' if ok else 'FAIL'}")
        if not ok:
            return False, f"卷{vol} Step{step} 校验失败:\n{msg[-800:]}"

    try:
        ok4, msg4 = gates.verify_step(WORK, vol, "4")
        if ok4:
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
            logs.append("step4: OK")
        else:
            logs.append(f"step4: skip ({msg4[:120]})")
    except Exception as exc:
        logs.append(f"step4/db: skip ({exc})")

    return True, f"卷{vol} {vn} 返工完成（{len(sk.get('entries', []))} 条）; " + "; ".join(logs)


def main() -> None:
    vols = sys.argv[1:] if len(sys.argv) > 1 else all_jiashi_vols()
    failed = []
    for vol in vols:
        vol = vol.zfill(3)
        if vol not in REPAIRS:
            print(f"跳过未知卷: {vol}")
            continue
        print(f"\n=== 返工 {WORK} 卷{vol} ===")
        try:
            ok, msg = repair_vol(vol)
            print("✅" if ok else "❌", msg)
            if not ok:
                failed.append(vol)
        except Exception as e:
            print(f"❌ 卷{vol} 异常: {e}")
            failed.append(vol)
    if failed:
        raise SystemExit(f"失败卷: {failed}")
    print("\n✅ 全部完成")


if __name__ == "__main__":
    main()
