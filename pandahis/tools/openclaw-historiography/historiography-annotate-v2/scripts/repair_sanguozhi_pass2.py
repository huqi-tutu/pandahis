#!/usr/bin/env python3
"""三国志标注第二轮人工口径。

033 蜀汉后主 → 蜀后主（对齐帝王表 / 小程序）
021 王粲只取 P2–P5
045 杨戏 P10–P66；廖化 P8–P9（P9 与宗预双挂）；糜芳 P67
049 新增笮融 P4
042 只保留杜琼、谯周、郤正
048 吴末帝 → 吴乌程侯
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
_ANNOTATE = _ROOT / "historiography-annotate"
_V2 = Path(__file__).resolve().parent
for p in (_ROOT, _ANNOTATE, _V2):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

os.environ["HIST_ANNOTATE_TRACK"] = "v2"

from paths_config import histograph_paths  # noqa: E402
from repair_sanguozhi_entry_scope import (  # noqa: E402
    WORK,
    _dump,
    _load,
    _paths,
    _row_map,
    rebuild,
    set_block,
    set_exclude,
    upsert_protagonist,
)
from v2_expand_to_skeleton import (  # noqa: E402
    _blocks_path,
    _load_index,
    build_mechanical_blocks,
    expand_to_skeleton,
)

EMPEROR_PATHS = (
    _ANNOTATE / "reference" / "帝王.json",
    histograph_paths()["data"] / "01历史坐标数据" / "帝王.json",
)
ALIAS_PATH = _ANNOTATE / "reference" / "帝王别名.json"


def rename_emperor(old: str, new: str) -> None:
    for path in EMPEROR_PATHS:
        if not path.is_file():
            print(f"  skip missing {path}")
            continue
        rows = json.loads(path.read_text(encoding="utf-8-sig"))
        n = 0
        for row in rows:
            if (row.get("帝王名称") or "").strip() == old:
                row["帝王名称"] = new
                n += 1
        if n:
            path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"  帝王.json {path.name}: {old} → {new} ×{n}")


def patch_alias_shuhouzhu() -> None:
    cfg = json.loads(ALIAS_PATH.read_text(encoding="utf-8"))
    global_map = cfg.setdefault("global", {})
    global_map.pop("蜀后主", None)
    global_map["蜀汉后主"] = "蜀后主"
    global_map["后主"] = "蜀后主"
    global_map["刘禅"] = "蜀后主"
    ALIAS_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("  帝王别名已改：标准名蜀后主")


def rename_in_primary(primary: dict, old: str, new: str) -> None:
    for row in primary.get("paragraphs") or []:
        if (row.get("primary_subject") or "").strip() == old:
            row["primary_subject"] = new
        if (row.get("co_owner") or "").strip() == old:
            row["co_owner"] = new


def rename_in_manifest(manifest: dict, old: str, new: str) -> None:
    for p in manifest.get("protagonists") or []:
        if (p.get("name") or "").strip() == old:
            p["name"] = new


def set_dual(primary: dict, pid: int, primary_name: str, co_owner: str) -> None:
    row = _row_map(primary)[pid]
    row["primary_subject"] = primary_name
    row["co_owner"] = co_owner
    row["disposition"] = "block"
    row.pop("exclude_reason", None)


def repair_033() -> None:
    vol = "033"
    _pf, mf = _paths(vol)
    manifest = _load(mf)
    rename_in_manifest(manifest, "蜀汉后主", "蜀后主")
    _dump(mf, manifest)
    index = _load_index(WORK, vol)
    draft = build_mechanical_blocks(manifest, index, WORK)
    _dump(_blocks_path(WORK, vol), draft)
    out = expand_to_skeleton(WORK, vol)
    print(f"  skeleton → {out}")


def repair_021() -> None:
    vol = "021"
    pf, mf = _paths(vol)
    primary = _load(pf)
    set_block(primary, range(2, 6), "王粲")
    set_exclude(primary, range(6, 17), "世系链")
    primary["method"] = "manual_repair"
    _dump(pf, primary)
    rebuild(vol)


def repair_045() -> None:
    vol = "045"
    pf, mf = _paths(vol)
    primary = _load(pf)
    manifest = _load(mf)
    upsert_protagonist(
        manifest,
        name="廖化",
        category="武将",
        rationale="关羽主簿，诈死归蜀，官至右车骑将军；本卷夹于宗预传中，独立开传。",
        after="宗预",
    )
    upsert_protagonist(
        manifest,
        name="糜芳",
        category="武将",
        rationale="《季汉辅臣赞》末「古之奔臣」条，糜芳字子方，南郡太守，叛迎孙权。",
        after="杨戏",
    )
    set_block(primary, [7], "宗预")
    set_block(primary, [8], "廖化")
    set_dual(primary, 9, "廖化", "宗预")
    set_block(primary, range(10, 67), "杨戏")
    set_block(primary, [67], "糜芳")
    primary["method"] = "manual_repair"
    _dump(pf, primary)
    _dump(mf, manifest)
    rebuild(vol)


def repair_049() -> None:
    vol = "049"
    pf, mf = _paths(vol)
    primary = _load(pf)
    manifest = _load(mf)
    upsert_protagonist(
        manifest,
        name="笮融",
        category="武将",
        rationale="刘繇传中「笮融者」独立开传，督广陵彭城运漕、大起浮图，后为刘繇所破。",
        after="刘繇",
    )
    set_block(primary, [4], "笮融")
    primary["method"] = "manual_repair"
    _dump(pf, primary)
    _dump(mf, manifest)
    rebuild(vol)


def repair_042() -> None:
    vol = "042"
    pf, mf = _paths(vol)
    primary = _load(pf)
    manifest = _load(mf)
    manifest["protagonists"] = [
        {
            "name": "杜琼",
            "category": "文臣",
            "rationale": "字伯瑜，任安弟子，太常；本卷独立开传，儒学占候。",
        },
        {
            "name": "谯周",
            "category": "文臣",
            "rationale": "字允南，劝后主降魏，儒学史学长传。",
        },
        {
            "name": "郤正",
            "category": "文臣",
            "rationale": "字令先，文章讽谏长传。",
        },
    ]
    set_exclude(primary, list(range(2, 7)) + list(range(8, 14)), "世系链")
    set_block(primary, [7], "杜琼")
    set_block(primary, range(14, 23), "谯周")
    set_block(primary, range(23, 34), "郤正")
    primary["method"] = "manual_repair"
    _dump(pf, primary)
    _dump(mf, manifest)
    rebuild(vol)


def repair_048() -> None:
    vol = "048"
    pf, mf = _paths(vol)
    primary = _load(pf)
    manifest = _load(mf)
    rename_in_manifest(manifest, "吴末帝", "吴乌程侯")
    rename_in_primary(primary, "吴末帝", "吴乌程侯")
    primary["method"] = "manual_repair"
    _dump(pf, primary)
    _dump(mf, manifest)
    rebuild(vol)


def main() -> int:
    repairs = {
        "033": repair_033,
        "021": repair_021,
        "045": repair_045,
        "049": repair_049,
        "042": repair_042,
        "048": repair_048,
    }
    vols = sys.argv[1:] or list(repairs)
    for vol in vols:
        if vol in ("emperor", "alias"):
            continue
        vol = vol.zfill(3)
        if vol not in repairs:
            print(f"跳过未知卷 {vol}", file=sys.stderr)
            continue
        print(f"== {WORK} {vol}")
        repairs[vol]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
