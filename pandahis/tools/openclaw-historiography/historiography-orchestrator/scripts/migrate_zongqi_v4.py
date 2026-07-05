#!/usr/bin/env python3
"""宫眷→宗戚、同姓藩王迁出帝王.json、已标注 skeleton 批量修正。"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

ROOT = Path(__file__).resolve().parents[4]  # pandahis/pandahis
DATA_EMPEROR = ROOT / "data" / "01历史坐标数据" / "帝王.json"
DATA_ZONGQI = ROOT / "data" / "01历史坐标数据" / "宗戚.json"
REF_EMPEROR = ROOT / "tools/openclaw-historiography/historiography-annotate/reference/帝王.json"
REF_ZONGQI = ROOT / "tools/openclaw-historiography/historiography-annotate/reference/宗戚.json"
SK_DIR = ROOT / "data" / "03索引标注条目"
MID_DIR = ROOT / "data" / "05工作流中间产物" / "标注"

# 从帝王.json 迁出 → 宗戚.json 的标准名
VASSAL_STANDARD_NAMES: Set[str] = {
    "楚元王", "荆王", "燕王", "齐悼惠王", "梁孝王", "梁孝王刘武",
    "齐王刘闳", "燕王刘旦", "广陵王刘胥",
    "刘长", "刘安", "刘赐", "刘勃", "刘参", "刘揖",
}

# 史略名称别名 → 宗戚.json 标准名
VASSAL_ALIASES: Dict[str, str] = {
    "刘交": "楚元王",
    "刘贾": "荆王", "荆王刘贾": "荆王",
    "刘泽": "燕王", "燕王刘泽": "燕王",
    "刘肥": "齐悼惠王",
    "刘武": "梁孝王",
    "燕王旦": "燕王刘旦",
    "吴王濞": "刘濞",
}

# 册封之君（四级帝王坐标）
ENFEOFFING_EMPEROR: Dict[str, str] = {
    "楚元王": "汉高祖", "荆王": "汉高祖", "燕王": "汉高祖",
    "齐悼惠王": "汉高祖", "刘襄": "汉高祖", "刘章": "汉高祖", "刘濞": "汉高祖",
    "梁孝王": "汉文帝", "梁孝王刘武": "汉文帝",
    "刘参": "汉文帝", "刘揖": "汉文帝",
    "刘长": "汉高祖", "刘安": "汉文帝", "刘赐": "汉文帝", "刘勃": "汉文帝",
    "齐王刘闳": "汉武帝", "燕王刘旦": "汉武帝", "广陵王刘胥": "汉武帝",
}

EXTRA_ZONGQI_STUBS: List[Dict[str, Any]] = [
    {
        "宗戚名称": "刘濞", "宗戚原名": "刘濞", "宗戚类型": "同姓藩王",
        "册封之君": "汉高祖", "政权": "西汉", "受封时间": "-196", "卒年": "-154",
        "标签": "吴王，景帝削藩之乱",
    },
    {
        "宗戚名称": "刘襄", "宗戚原名": "刘襄", "宗戚类型": "同姓藩王",
        "册封之君": "汉高祖", "政权": "西汉", "受封时间": "-179", "卒年": "-179",
        "标签": "齐哀王，诛吕",
    },
    {
        "宗戚名称": "刘章", "宗戚原名": "刘章", "宗戚类型": "同姓藩王",
        "册封之君": "汉高祖", "政权": "西汉", "受封时间": "-187", "卒年": "-177",
        "标签": "城阳景王",
    },
]


def _norm_id_from_emperor(eid: str) -> str:
    return eid.replace("DW_", "ZJ_", 1) if eid.startswith("DW_") else f"ZJ_{eid}"


def _emperor_to_zongqi(row: dict, emperor_id_map: Dict[str, str]) -> dict:
    name = (row.get("帝王名称") or "").strip()
    enfeoff = ENFEOFFING_EMPEROR.get(name, "")
    eid = (row.get("帝王ID") or "").strip()
    zj_id = _norm_id_from_emperor(eid) if eid else ""
    enfeoff_id = emperor_id_map.get(enfeoff, "")
    orig = (row.get("帝王原名") or "").strip()
    if orig in ("武",) and name == "梁孝王刘武":
        orig = "刘武"
    return {
        "宗戚ID": zj_id,
        "宗戚名称": name,
        "宗戚原名": orig,
        "宗戚类型": "同姓藩王",
        "册封之君": enfeoff,
        "册封之君ID": enfeoff_id,
        "政权": row.get("政权", "西汉"),
        "政权ID": row.get("政权ID", ""),
        "朝代": row.get("朝代", "西汉"),
        "朝代ID": row.get("朝代ID", ""),
        "文明": row.get("文明", "华夏"),
        "文明ID": row.get("文明ID", "HX"),
        "受封时间": row.get("即位时间", ""),
        "卒年": row.get("退位时间", ""),
        "标签": row.get("标签", ""),
    }


def _build_zongqi_stub(stub: dict, emperor_id_map: Dict[str, str]) -> dict:
    name = stub["宗戚名称"]
    enfeoff = stub["册封之君"]
    py = re.sub(r"[^A-Z0-9]", "", name.upper())[:20] or "UNKNOWN"
    zj_id = f"ZJ_HX_XIHAN_XIHAN_{py}"
    return {
        "宗戚ID": zj_id,
        "宗戚名称": name,
        "宗戚原名": stub.get("宗戚原名", name),
        "宗戚类型": stub.get("宗戚类型", "同姓藩王"),
        "册封之君": enfeoff,
        "册封之君ID": emperor_id_map.get(enfeoff, ""),
        "政权": stub.get("政权", "西汉"),
        "政权ID": "ZQ_HX_XIHAN_XIHAN",
        "朝代": "西汉",
        "朝代ID": "CD_HX_XIHAN",
        "文明": "华夏",
        "文明ID": "HX",
        "受封时间": stub.get("受封时间", ""),
        "卒年": stub.get("卒年", ""),
        "标签": stub.get("标签", ""),
    }


def migrate_emperor_files() -> Tuple[List[dict], List[dict]]:
    with open(DATA_EMPEROR, encoding="utf-8") as f:
        emperors: List[dict] = json.load(f)

    emperor_id_map = {
        (r.get("帝王名称") or "").strip(): (r.get("帝王ID") or "").strip()
        for r in emperors
        if (r.get("帝王名称") or "").strip()
    }

    move_names: Set[str] = set(VASSAL_STANDARD_NAMES)
    zongqi_rows: List[dict] = []
    seen_zj: Set[str] = set()
    kept: List[dict] = []

    for row in emperors:
        name = (row.get("帝王名称") or "").strip()
        regime = (row.get("政权") or "").strip()
        should_move = (
            name in move_names
            or regime in ("荆", "梁")
        )
        if should_move:
            zj = _emperor_to_zongqi(row, emperor_id_map)
            zj_key = zj["宗戚名称"]
            if zj_key not in seen_zj:
                zongqi_rows.append(zj)
                seen_zj.add(zj_key)
        else:
            kept.append(row)

    for stub in EXTRA_ZONGQI_STUBS:
        if stub["宗戚名称"] not in seen_zj:
            zongqi_rows.append(_build_zongqi_stub(stub, emperor_id_map))
            seen_zj.add(stub["宗戚名称"])

    zongqi_rows.sort(key=lambda r: r.get("宗戚名称", ""))

    for path in (DATA_EMPEROR, REF_EMPEROR):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(kept, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for path in (DATA_ZONGQI, REF_ZONGQI):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(zongqi_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return kept, zongqi_rows


def _load_zongqi_index() -> Tuple[Dict[str, dict], Dict[str, str]]:
    path = DATA_ZONGQI if DATA_ZONGQI.exists() else REF_ZONGQI
    with open(path, encoding="utf-8") as f:
        rows = json.load(f)
    by_name: Dict[str, dict] = {}
    alias: Dict[str, str] = {}
    for r in rows:
        std = (r.get("宗戚名称") or "").strip()
        if std:
            by_name[std] = r
        orig = (r.get("宗戚原名") or "").strip()
        if orig:
            alias[orig] = std
    alias.update(VASSAL_ALIASES)
    return by_name, alias


def _resolve_vassal_std(name: str, alias: Dict[str, str], zq_index: Dict[str, dict]) -> Optional[str]:
    n = name.strip()
    if n in zq_index:
        return n
    if n in alias:
        return alias[n]
    return None


def _is_vassal_entry(name: str, alias: Dict[str, str], zq_index: Dict[str, dict]) -> bool:
    return _resolve_vassal_std(name, alias, zq_index) is not None


def migrate_skeleton_file(
    fp: Path,
    zq_index: Dict[str, dict],
    alias: Dict[str, str],
    emperor_id_map: Dict[str, str],
) -> int:
    with open(fp, encoding="utf-8") as f:
        data = json.load(f)

    changed = 0

    def patch_obj(obj: dict, *, is_entry: bool) -> None:
        nonlocal changed
        cat = (obj.get("史略分类") or obj.get("category") or "").strip()
        name = (obj.get("史略名称") or obj.get("name") or "").strip()

        if cat == "宫眷":
            key = "史略分类" if "史略分类" in obj else "category"
            obj[key] = "宗戚"
            changed += 1
            cat = "宗戚"

        if cat in ("君王", "文臣", "武将") and _is_vassal_entry(name, alias, zq_index):
            std = _resolve_vassal_std(name, alias, zq_index)
            if not std:
                return
            zq = zq_index[std]
            enfeoff = zq.get("册封之君") or ENFEOFFING_EMPEROR.get(std, "")
            enfeoff_id = zq.get("册封之君ID") or emperor_id_map.get(enfeoff, "")

            if is_entry:
                obj["史略分类"] = "宗戚"
                if std != name:
                    obj["史略名称"] = std
                obj["四级帝王坐标"] = enfeoff
                obj["帝王ID"] = enfeoff_id
                obj["宗戚ID"] = zq.get("宗戚ID", "")
                z5 = obj.get("五级细坐标") or ""
                if z5:
                    obj["五级细坐标"] = z5.replace("·君王·", "·宗戚·").replace("·宫眷·", "·宗戚·")
                af = obj.get("_auto_filled")
                if isinstance(af, dict):
                    af["_坐标主轴说明"] = (
                        f"{std}为{enfeoff}所封同姓藩王，四级帝王坐标挂册封之君{enfeoff}。"
                    )
            else:
                obj["category"] = "宗戚"
                if std != name:
                    obj["name"] = std
            changed += 1
        elif cat == "宫眷":
            z5 = obj.get("五级细坐标") or ""
            if z5 and "·宫眷·" in z5:
                obj["五级细坐标"] = z5.replace("·宫眷·", "·宗戚·")
                changed += 1

    for entry in data.get("entries") or []:
        patch_obj(entry, is_entry=True)

    for seg in data.get("segment_attribution") or []:
        for owner in seg.get("owners") or []:
            patch_obj(owner, is_entry=False)

    for block in data.get("blocks") or []:
        patch_obj(block, is_entry=False)

    for p in data.get("protagonists") or []:
        patch_obj(p, is_entry=False)

    if changed:
        fp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return changed


def migrate_all_skeletons(emperor_id_map: Dict[str, str]) -> int:
    zq_index, alias = _load_zongqi_index()
    total = 0
    patterns = [
        SK_DIR.glob("*_skeleton.json"),
        MID_DIR.glob("*_blocks.json"),
        MID_DIR.glob("*_protagonists.json"),
    ]
    for gen in patterns:
        for fp in sorted(gen):
            total += migrate_skeleton_file(fp, zq_index, alias, emperor_id_map)
    return total


def main() -> int:
    kept, zongqi = migrate_emperor_files()
    emperor_id_map = {
        (r.get("帝王名称") or "").strip(): (r.get("帝王ID") or "").strip()
        for r in kept
        if (r.get("帝王名称") or "").strip()
    }
    sk_changes = migrate_all_skeletons(emperor_id_map)
    print(json.dumps({
        "emperors_kept": len(kept),
        "zongqi_created": len(zongqi),
        "skeleton_fields_changed": sk_changes,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
