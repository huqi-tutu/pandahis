#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""将朝代知识补全增量条目（默认 GLBL_00621–00634）索引 + 详情 upsert 到线上 DB。"""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DK_BASE = DATA / "06朝代知识补全"
INDEX_MAIN = DATA / "03索引标注条目" / "史略索引_01至02.json"
EMPEROR_JSON = DATA / "01历史坐标数据" / "帝王.json"
TOOLS = ROOT / "tools" / "openclaw-historiography"
TRANSLATE_DIR = TOOLS / "historiography-translate"

if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from import_box_index_json import (  # noqa: E402
    build_box_rows,
    ensure_emperor_refs,
    ensure_schema,
    upsert_boxes,
)

sys.path.insert(0, str(TRANSLATE_DIR))
from lib.remote_sync import sync_translate_detail  # noqa: E402

DEFAULT_ID_MIN = 621
DEFAULT_ID_MAX = 634

JUNWANG_EMPEROR_ID: dict[str, str] = {
    "炎帝": "DW_HX_WUDI_WUDI_YANDI",
    "少昊": "DW_HX_WUDI_WUDI_SHAOHAO",
}

PERSON_CATEGORIES = frozenset({"君王", "宗戚", "文臣", "武将", "后妃", "宦官", "方士", "其他人物"})


def parse_year(raw: str | int | None) -> int | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s or s == "-":
        return None
    if s.startswith("约"):
        s = s[1:]
    try:
        return int(s)
    except ValueError:
        return None


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def glbl_num(entry_id: str) -> int | None:
    parts = str(entry_id).split("_")
    if len(parts) < 2:
        return None
    try:
        return int(parts[1])
    except ValueError:
        return None


def build_emperor_name_index() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for row in load_json(EMPEROR_JSON):
        name = str(row.get("帝王名称", "")).strip()
        if name:
            out[name] = row
    return out


def validate_enriched_entries(entries: list[dict]) -> tuple[list[str], list[str]]:
    missing_peak: list[str] = []
    missing_tag: list[str] = []
    for e in entries:
        eid = str(e.get("史略ID", ""))
        if e.get("峰值年") is None:
            missing_peak.append(eid)
        cat = str(e.get("史略分类", ""))
        if cat in PERSON_CATEGORIES:
            tag = str(e.get("人物标签", "") or "").strip()
            auto = e.get("_auto_filled") or {}
            if not tag and not auto.get("_人物标签留空"):
                missing_tag.append(eid)
    return missing_peak, missing_tag


def load_incremental_entries(id_min: int, id_max: int) -> list[dict]:
    entries: list[dict] = []
    index_dir = DK_BASE / "索引条目"
    for path in sorted(index_dir.glob("*.json")):
        doc = load_json(path)
        for e in doc.get("entries") or []:
            num = glbl_num(str(e.get("史略ID", "")))
            if num is not None and id_min <= num <= id_max:
                entries.append(e)
    entries.sort(key=lambda x: str(x.get("史略ID", "")))
    return entries


def normalize_entry(entry: dict, emperors: dict[str, dict]) -> dict:
    e = deepcopy(entry)
    e.setdefault("母本著作", "朝代补全")
    e.setdefault("来源著作", ["朝代补全"])
    e.setdefault("来源条目数", 1)
    e.setdefault("段落域数", 0)
    e.setdefault("paragraphs", [])
    e.setdefault("史略来源", "模型补全")

    name = str(e.get("史略名称", "")).strip()
    cat = str(e.get("史略分类", "")).strip()

    if cat == "君王" and not e.get("帝王ID"):
        e["四级帝王坐标"] = name
        e["帝王ID"] = JUNWANG_EMPEROR_ID.get(name, "")

    emp_name = str(e.get("四级帝王坐标") or "").strip()
    emp_row = emperors.get(emp_name)
    if emp_row and not e.get("帝王ID"):
        e["帝王ID"] = emp_row["帝王ID"]
        e["四级帝王坐标"] = emp_row["帝王名称"]

    if emp_row:
        if e.get("史略开始年") is None:
            e["史略开始年"] = parse_year(emp_row.get("即位时间"))
        if e.get("史略结束年") is None:
            e["史略结束年"] = parse_year(emp_row.get("退位时间"))

    if e.get("史略开始年") is None:
        e["史略开始年"] = parse_year(e.get("峰值年"))
    if e.get("史略结束年") is None:
        e["史略结束年"] = e.get("史略开始年")

    if e.get("史略开始年") is None:
        dynasty = str(e.get("朝代ID", ""))
        e["史略开始年"] = -2600 if dynasty == "CD_HX_WUDI" else -2000
    if e.get("史略结束年") is None:
        e["史略结束年"] = e["史略开始年"]

    e.setdefault("四级帝王坐标", emp_name or name if cat == "君王" else "")
    if not e.get("帝王ID"):
        if cat == "君王":
            e["帝王ID"] = JUNWANG_EMPEROR_ID.get(name, f"STUB_{e['史略ID']}")
        elif emp_row:
            e["帝王ID"] = emp_row["帝王ID"]
        else:
            e["帝王ID"] = f"STUB_{e['史略ID']}"

    return e


def merge_into_main_index(entries: list[dict]) -> tuple[int, int]:
    doc = load_json(INDEX_MAIN)
    main_entries: list[dict] = doc.get("entries") or []
    by_id = {str(e.get("史略ID", "")): i for i, e in enumerate(main_entries)}
    added, updated = 0, 0
    for e in entries:
        eid = str(e["史略ID"])
        if eid in by_id:
            main_entries[by_id[eid]] = e
            updated += 1
        else:
            main_entries.append(e)
            by_id[eid] = len(main_entries) - 1
            added += 1
    doc["entries"] = main_entries
    save_json(INDEX_MAIN, doc)
    return added, updated


def load_incremental_details(id_min: int, id_max: int) -> dict[str, str]:
    out: dict[str, str] = {}
    for f in sorted((DK_BASE / "详情").glob("GLBL_*.json")):
        parts = f.stem.split("_")
        if len(parts) < 2:
            continue
        try:
            num = int(parts[1])
        except ValueError:
            continue
        if not (id_min <= num <= id_max):
            continue
        eid = f"{parts[0]}_{parts[1]}"
        doc = load_json(f)
        text = str(doc.get("翻译详情") or "").strip()
        if text:
            out[eid] = text
    return out


def connect_mysql():
    import pymysql
    import os

    env_file = TOOLS / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

    return pymysql.connect(
        host=os.environ.get("MYSQL_HOST", "49.235.165.220"),
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        user=os.environ.get("MYSQL_USER", "histomap_admin"),
        password=os.environ.get("MYSQL_PASSWORD", "pandahis#666"),
        database=os.environ.get("MYSQL_DB", "histomap"),
        charset="utf8mb4",
        autocommit=False,
        connect_timeout=15,
        read_timeout=300,
        write_timeout=300,
        cursorclass=pymysql.cursors.DictCursor,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="增量朝代知识补全 → 线上 DB")
    parser.add_argument("--id-min", type=int, default=DEFAULT_ID_MIN)
    parser.add_argument("--id-max", type=int, default=DEFAULT_ID_MAX)
    args = parser.parse_args()

    emperors = build_emperor_name_index()
    raw_entries = load_incremental_entries(args.id_min, args.id_max)
    if not raw_entries:
        print(f"未找到 GLBL_{args.id_min:05d}–{args.id_max:05d} 索引条目")
        return 1

    missing_peak, missing_tag = validate_enriched_entries(raw_entries)
    if missing_peak:
        print(
            f"⚠️ 缺峰值年 {len(missing_peak)} 条: "
            f"{', '.join(missing_peak[:8])}{'…' if len(missing_peak) > 8 else ''}"
        )
    if missing_tag:
        print(
            f"⚠️ 缺人物标签 {len(missing_tag)} 条: "
            f"{', '.join(missing_tag[:8])}{'…' if len(missing_tag) > 8 else ''}"
        )

    entries = [normalize_entry(e, emperors) for e in raw_entries]
    added, updated = merge_into_main_index(entries)
    print(
        f"本地索引合并: 新增 {added}，更新 {updated} "
        f"（共 {len(entries)} 条 GLBL_{args.id_min:05d}–{args.id_max:05d}）"
    )

    rows = build_box_rows(entries)
    details = load_incremental_details(args.id_min, args.id_max)
    print(f"待同步详情: {len(details)} 条（索引 {len(entries)} 条）")

    conn = connect_mysql()
    try:
        with conn.cursor() as cursor:
            ensure_schema(cursor)
            emperor_stats = ensure_emperor_refs(cursor, rows, EMPEROR_JSON)
            if emperor_stats:
                print("帝王 FK 预处理:", emperor_stats)
            box_n = upsert_boxes(cursor, rows)
            print(f"historical_box upsert: {box_n} 条")

        conn.commit()

        detail_ok = 0
        for eid, text in sorted(details.items()):
            ok, msg = sync_translate_detail(eid, text, dry_run=False)
            if not ok:
                print(f"  ❌ {eid}: {msg}", file=sys.stderr)
                return 1
            detail_ok += 1
        print(f"historical_box_detail upsert: {detail_ok} 条")
    except Exception as exc:
        conn.rollback()
        print(f"失败: {exc}", file=sys.stderr)
        raise
    finally:
        conn.close()

    missing = [e["史略ID"] for e in entries if e["史略ID"] not in details]
    if missing:
        print(f"⚠️ 有索引暂无详情: {', '.join(missing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
