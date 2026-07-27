#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""将夏朝朝代知识补全索引 + 已有详情 upsert 到线上 DB（不 prune 全库）。"""

from __future__ import annotations

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

from emperor_year_align import (  # noqa: E402
    align_junji_entry_years,
    build_emperor_indexes,
    load_emperor_rows,
)
from import_box_index_json import (  # noqa: E402
    build_box_rows,
    ensure_emperor_refs,
    ensure_schema,
    upsert_boxes,
)
sys.path.insert(0, str(TRANSLATE_DIR))
from lib.remote_sync import sync_translate_detail  # noqa: E402

XIA_ID_MIN = 586
XIA_ID_MAX = 620
REGIME_XIA = "ZQ_HX_XIA_XIA"
NAME_ALIASES = {"大禹": "禹", "夏桀": "桀", "启": "启"}
PERSON_CATEGORIES = frozenset({"君王", "宗戚", "文臣", "武将", "后妃", "宦官", "方士", "其他人物"})


def validate_enriched_entries(entries: list[dict]) -> tuple[list[str], list[str]]:
    """返回 (缺峰值年, 缺人物标签) 的史略ID 列表。"""
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


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_xia_entries() -> list[dict]:
    entries: list[dict] = []
    for name in ("夏_事略典制论著.json", "夏_人物.json"):
        doc = load_json(DK_BASE / "索引条目" / name)
        entries.extend(doc.get("entries") or [])
    return entries


def build_emperor_index() -> tuple[dict[str, dict], dict[str, dict]]:
    rows = [r for r in load_emperor_rows(EMPEROR_JSON) if str(r.get("朝代ID", "")).strip() == "CD_HX_XIA"]
    return build_emperor_indexes(rows)


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


def normalize_entry(
    entry: dict,
    emperors_by_name: dict[str, dict],
    emperors_by_id: dict[str, dict],
) -> dict:
    e = deepcopy(entry)
    e["朝代ID"] = "CD_HX_XIA"
    e["政权ID"] = REGIME_XIA
    e.setdefault("三级政权坐标", "夏")
    e.setdefault("一级文明坐标", "华夏")
    e.setdefault("二级朝代坐标", "夏")
    e.setdefault("文明ID", "HX")

    name = str(e.get("史略名称", "")).strip()
    cat = str(e.get("史略分类", "")).strip()

    if cat == "君王" and not str(e.get("四级帝王坐标") or "").strip():
        e["四级帝王坐标"] = name

    emp_name = str(e.get("四级帝王坐标") or "").strip()
    if emp_name in NAME_ALIASES:
        emp_name = NAME_ALIASES[emp_name]
        e["四级帝王坐标"] = emp_name
    if not emp_name:
        e["四级帝王坐标"] = "禹"
        emp_name = "禹"
    emp_row = emperors_by_name.get(emp_name)

    e, _ = align_junji_entry_years(
        e,
        by_name=emperors_by_name,
        by_id=emperors_by_id,
        force=True,
    )

    if e.get("史略开始年") is None:
        e["史略开始年"] = parse_year(e.get("史略结束年")) or parse_year(e.get("峰值年")) or -2000
    if e.get("史略结束年") is None:
        e["史略结束年"] = e["史略开始年"]

    if not str(e.get("帝王ID") or "").strip():
        e["帝王ID"] = emp_row["帝王ID"] if emp_row else "DW_HX_XIA_XIA_YU"
    e.setdefault("母本史略ID", f"DYKN_夏_{e['史略ID']}")
    e.setdefault("五级细坐标", f"夏·{cat or '人物'}·{name}")
    e.setdefault("母本著作", "朝代补全")
    e.setdefault("来源著作", ["朝代补全"])
    e.setdefault("来源条目数", 1)
    e.setdefault("段落域数", 0)
    e.setdefault("paragraphs", [])
    e.setdefault("史略来源", "模型补全")
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


def load_xia_details() -> dict[str, str]:
    out: dict[str, str] = {}
    for f in sorted((DK_BASE / "详情").glob("GLBL_*.json")):
        parts = f.stem.split("_")
        if len(parts) < 2:
            continue
        num = int(parts[1])
        if not (XIA_ID_MIN <= num <= XIA_ID_MAX):
            continue
        eid = f"{parts[0]}_{parts[1]}"
        doc = load_json(f)
        text = str(doc.get("翻译详情") or "").strip()
        if text:
            out[eid] = text
    return out


def connect_mysql():
    import pymysql

    env_file = TOOLS / ".env"
    if env_file.is_file():
        import os

        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

    import os

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
    emperors_by_name, emperors_by_id = build_emperor_index()
    raw_entries = load_xia_entries()
    missing_peak, missing_tag = validate_enriched_entries(raw_entries)
    if missing_peak:
        print(f"⚠️ 缺峰值年 {len(missing_peak)} 条: {', '.join(missing_peak[:8])}{'…' if len(missing_peak) > 8 else ''}")
    if missing_tag:
        print(f"⚠️ 缺人物标签 {len(missing_tag)} 条: {', '.join(missing_tag[:8])}{'…' if len(missing_tag) > 8 else ''}")
    entries = [normalize_entry(e, emperors_by_name, emperors_by_id) for e in raw_entries]
    added, updated = merge_into_main_index(entries)
    print(f"本地索引合并: 新增 {added}，更新 {updated}（共 {len(entries)} 条夏朝补全）")

    rows, skipped = build_box_rows(entries)
    details = load_xia_details()
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
                conn.rollback()
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
        print(f"⚠️ 有索引暂无详情（批跑中）: {len(missing)} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
