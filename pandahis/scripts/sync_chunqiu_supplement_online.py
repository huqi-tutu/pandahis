#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""春秋事略/典制/论著补全（GLBL_00986–01020）→ 全局索引 + MySQL。"""

from __future__ import annotations

import argparse
import json
import os
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DK_BASE = DATA / "06朝代知识补全"
INDEX_MAIN = DATA / "03索引标注条目" / "史略索引_01至02.json"
EMPEROR_JSON = DATA / "01历史坐标数据" / "帝王.json"
TOOLS = ROOT / "tools/openclaw-historiography"
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
from sync_zhanguo_dynasty_online import (  # noqa: E402
    load_index_entries,
    parse_year,
    save_index_entries,
)

sys.path.insert(0, str(TRANSLATE_DIR))
from lib.remote_sync import sync_translate_detail  # noqa: E402

CHUNQIU_DYNASTY_ID = "CD_HX_CHUNQIU"
DEFAULT_ID_MIN = 986
DEFAULT_ID_MAX = 1020


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def glbl_num(entry_id: str) -> int | None:
    parts = str(entry_id).split("_")
    if len(parts) < 2:
        return None
    try:
        return int(parts[1])
    except ValueError:
        return None


def load_chunqiu_supplement_entries(id_min: int, id_max: int) -> list[dict]:
    path = DK_BASE / "索引条目" / "春秋_事略典制论著.json"
    doc = load_json(path)
    rows = [
        e
        for e in doc.get("entries") or []
        if (n := glbl_num(str(e.get("史略ID", "")))) is not None and id_min <= n <= id_max
    ]
    rows.sort(key=lambda x: str(x.get("史略ID", "")))
    return rows


def build_chunqiu_emperor_index() -> tuple[dict[str, dict], dict[str, dict]]:
    rows = [
        r
        for r in load_emperor_rows(EMPEROR_JSON)
        if str(r.get("朝代ID", "")).strip() == CHUNQIU_DYNASTY_ID
    ]
    return build_emperor_indexes(rows)


def normalize_entry(
    entry: dict,
    emperors_by_name: dict[str, dict],
    emperors_by_id: dict[str, dict],
) -> dict:
    e = deepcopy(entry)
    e.setdefault("一级文明坐标", "华夏")
    e.setdefault("二级朝代坐标", "春秋")
    e.setdefault("文明ID", "HX")
    e.setdefault("朝代ID", CHUNQIU_DYNASTY_ID)
    e.setdefault("母本著作", "朝代补全")
    e.setdefault("来源著作", ["朝代补全"])
    e.setdefault("来源条目数", 1)
    e.setdefault("段落域数", 0)
    e.setdefault("paragraphs", [])
    e.setdefault("史略来源", "模型补全")

    name = str(e.get("史略名称", "")).strip()
    cat = str(e.get("史略分类", "")).strip()

    emp_name = str(e.get("四级帝王坐标") or "").strip()
    emp_row = emperors_by_name.get(emp_name)
    e, _ = align_junji_entry_years(
        e, by_name=emperors_by_name, by_id=emperors_by_id, force=True
    )

    if e.get("峰值年") is None:
        e["峰值年"] = parse_year(e.get("史略开始年")) or parse_year(e.get("建议年份"))
    if e.get("史略开始年") is None:
        e["史略开始年"] = e.get("峰值年")
    if e.get("史略结束年") is None:
        e["史略结束年"] = e.get("史略开始年")

    if not str(e.get("帝王ID") or "").strip() and emp_row:
        e["帝王ID"] = emp_row["帝王ID"]
    if not emp_name and emp_row:
        e["四级帝王坐标"] = emp_row["帝王名称"]

    e.setdefault("五级细坐标", f"春秋·{cat or '条目'}·{name}")
    e.setdefault("母本史略ID", f"DYKN_春秋_{e.get('史略ID', '')}")
    return e


def merge_into_main_index(entries: list[dict]) -> tuple[int, int]:
    main_entries, doc, fmt = load_index_entries(INDEX_MAIN)
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
    save_index_entries(INDEX_MAIN, main_entries, doc, fmt)
    return added, updated


def load_supplement_details(entry_ids: set[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for f in sorted((DK_BASE / "详情").glob("GLBL_*.json")):
        parts = f.stem.split("_")
        if len(parts) < 2:
            continue
        eid = f"{parts[0]}_{parts[1]}"
        if eid not in entry_ids:
            continue
        text = str(load_json(f).get("翻译详情") or "").strip()
        if text:
            out[eid] = text
    return out


def connect_mysql():
    import pymysql

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
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=15,
        read_timeout=300,
        write_timeout=300,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="春秋知识补全入库")
    parser.add_argument("--id-min", type=int, default=DEFAULT_ID_MIN)
    parser.add_argument("--id-max", type=int, default=DEFAULT_ID_MAX)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    raw = load_chunqiu_supplement_entries(args.id_min, args.id_max)
    if not raw:
        print(f"未找到 GLBL_{args.id_min:05d}–{args.id_max:05d} 春秋补全条目")
        return 1

    emperors_by_name, emperors_by_id = build_chunqiu_emperor_index()
    entries = [normalize_entry(e, emperors_by_name, emperors_by_id) for e in raw]
    entry_ids = {str(e["史略ID"]) for e in entries}
    details = load_supplement_details(entry_ids)

    missing_detail = sorted(entry_ids - set(details))
    if missing_detail:
        print(
            f"❌ 缺详情 {len(missing_detail)}/{len(entries)} 条，请先 compose-detail："
            f" {', '.join(missing_detail[:5])}{'…' if len(missing_detail) > 5 else ''}"
        )
        return 1

    if args.dry_run:
        print(f"[dry-run] 将 merge {len(entries)} 条，详情 {len(details)} 条")
        return 0

    added, updated = merge_into_main_index(entries)
    print(f"✅ 全局索引 merge: 新增 {added}，更新 {updated}（共 {len(entries)} 条）")

    rows, skipped = build_box_rows(entries)
    if skipped:
        print(f"⚠️ build_box_rows 跳过 {len(skipped)} 条: {', '.join(skipped[:5])}")

    conn = connect_mysql()
    try:
        with conn.cursor() as cursor:
            ensure_schema(cursor)
            stats = ensure_emperor_refs(cursor, rows, EMPEROR_JSON)
            if stats:
                print("帝王 FK:", stats)
            n = upsert_boxes(cursor, rows)
            conn.commit()
        print(f"✅ historical_box upsert: {n} 条")

        ok_n = 0
        for eid, text in sorted(details.items()):
            ok, msg = sync_translate_detail(eid, text, dry_run=False)
            if not ok:
                print(f"❌ {eid} detail: {msg}", file=sys.stderr)
                return 1
            ok_n += 1
        print(f"✅ historical_box_detail upsert: {ok_n} 条")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
