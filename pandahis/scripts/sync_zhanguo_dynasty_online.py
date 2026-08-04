#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""战国朝代知识补全：并入全局索引 + historical_box / detail upsert（不 prune 全库）。"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from copy import deepcopy
from datetime import datetime, timezone
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

ZHANGUO_DYNASTY_ID = "CD_HX_ZHANGUO"
PERSON_CATEGORIES = frozenset(
    {"君王", "诸侯", "宗戚", "文臣", "武将", "后妃", "宦官", "方士", "其他人物", "蕃祚", "庶众"}
)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_index_entries(path: Path) -> tuple[list[dict], dict | list, str]:
    doc = load_json(path)
    if isinstance(doc, list):
        return doc, doc, "list"
    entries = list(doc.get("entries") or [])
    return entries, doc, "dict"


def save_index_entries(path: Path, entries: list[dict], doc: dict | list, fmt: str) -> None:
    if fmt == "list":
        save_json(path, entries)
    else:
        doc["entries"] = entries
        save_json(path, doc)


def parse_year(raw) -> int | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s or s in ("-", "—", "null"):
        return None
    if s.startswith("约"):
        s = s[1:]
    try:
        return int(s)
    except ValueError:
        return None


def load_zhanguo_supplement_entries() -> list[dict]:
    entries: list[dict] = []
    for name in ("战国_事略典制论著.json", "战国_人物.json"):
        path = DK_BASE / "索引条目" / name
        if path.is_file():
            entries.extend(load_json(path).get("entries") or [])
    entries.sort(key=lambda x: str(x.get("史略ID", "")))
    return entries


def build_zhanguo_emperor_index() -> tuple[dict[str, dict], dict[str, dict]]:
    rows = [
        r
        for r in load_emperor_rows(EMPEROR_JSON)
        if str(r.get("朝代ID", "")).strip() == ZHANGUO_DYNASTY_ID
    ]
    return build_emperor_indexes(rows)


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


def normalize_entry(
    entry: dict,
    emperors_by_name: dict[str, dict],
    emperors_by_id: dict[str, dict],
) -> dict:
    e = deepcopy(entry)
    e.setdefault("一级文明坐标", "华夏")
    e.setdefault("二级朝代坐标", "战国")
    e.setdefault("文明ID", "HX")
    e.setdefault("朝代ID", ZHANGUO_DYNASTY_ID)
    e.setdefault("母本著作", "朝代补全")
    e.setdefault("来源著作", ["朝代补全"])
    e.setdefault("来源条目数", 1)
    e.setdefault("段落域数", 0)
    e.setdefault("paragraphs", [])
    e.setdefault("史略来源", "模型补全")

    name = str(e.get("史略名称", "")).strip()
    cat = str(e.get("史略分类", "")).strip()

    if cat in ("君王", "诸侯") and not str(e.get("四级帝王坐标") or "").strip():
        e["四级帝王坐标"] = name

    emp_name = str(e.get("四级帝王坐标") or "").strip()
    emp_row = emperors_by_name.get(emp_name)

    e, _ = align_junji_entry_years(
        e,
        by_name=emperors_by_name,
        by_id=emperors_by_id,
        force=True,
    )

    if e.get("史略开始年") is None:
        e["史略开始年"] = parse_year(e.get("峰值年")) or parse_year(e.get("史略结束年"))
    if e.get("史略结束年") is None:
        e["史略结束年"] = parse_year(e.get("史略开始年"))

    # 蕃祚等缺年条目兜底
    if e.get("史略开始年") is None and e.get("史略结束年") is not None:
        end = int(e["史略结束年"])
        e["史略开始年"] = end - 300 if end < 0 else end
    if e.get("史略结束年") is None and e.get("史略开始年") is not None:
        e["史略结束年"] = e["史略开始年"]

    # 个别蕃祚缺年兜底（义渠等）
    _FANZHU_YEARS: dict[str, tuple[int, int]] = {
        "义渠": (-361, -272),
    }
    if name in _FANZHU_YEARS and (
        e.get("史略开始年") is None or e.get("史略结束年") is None
    ):
        s, t = _FANZHU_YEARS[name]
        e["史略开始年"] = s
        e["史略结束年"] = t

    if not str(e.get("帝王ID") or "").strip():
        if emp_row:
            e["帝王ID"] = emp_row["帝王ID"]
            e["四级帝王坐标"] = emp_row["帝王名称"]
        else:
            e["帝王ID"] = f"STUB_{e['史略ID']}"

    eid = str(e.get("史略ID", ""))
    e.setdefault("母本史略ID", f"DYKN_战国_{eid}")
    return e


def merge_into_main_index(entries: list[dict], *, dry_run: bool) -> tuple[int, int]:
    main_entries, doc, fmt = load_index_entries(INDEX_MAIN)
    by_id = {str(e.get("史略ID", "")): i for i, e in enumerate(main_entries)}
    added, updated = 0, 0
    for e in entries:
        eid = str(e["史略ID"])
        if eid in by_id:
            updated += 1
            if not dry_run:
                main_entries[by_id[eid]] = e
        else:
            added += 1
            if not dry_run:
                main_entries.append(e)
                by_id[eid] = len(main_entries) - 1
    if not dry_run:
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
        doc = load_json(f)
        text = str(doc.get("翻译详情") or "").strip()
        if text:
            out[eid] = text
    return out


def connect_mysql():
    import os
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
        connect_timeout=15,
        read_timeout=300,
        write_timeout=300,
        cursorclass=pymysql.cursors.DictCursor,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="战国二期补全 → 全局索引 + 线上 DB")
    parser.add_argument("--dry-run", action="store_true", help="只预览合并，不写盘/不写库")
    parser.add_argument("--local-only", action="store_true", help="只合并本地索引，不同步 MySQL")
    parser.add_argument("--no-backup", action="store_true")
    args = parser.parse_args()

    raw_entries = load_zhanguo_supplement_entries()
    if not raw_entries:
        print("未找到战国二期索引条目")
        return 1

    missing_peak, missing_tag = validate_enriched_entries(raw_entries)
    if missing_peak:
        print(
            f"⚠️ 缺峰值年 {len(missing_peak)} 条（不阻断导入）"
        )
    if missing_tag:
        print(
            f"⚠️ 缺人物标签 {len(missing_tag)} 条（不阻断导入）"
        )

    by_name, by_id = build_zhanguo_emperor_index()
    entries = [normalize_entry(e, by_name, by_id) for e in raw_entries]

    still_bad = [
        e["史略ID"]
        for e in entries
        if e.get("史略开始年") is None or e.get("史略结束年") is None
    ]
    if still_bad:
        print(f"❌ 仍缺年份，无法导入: {', '.join(still_bad)}")
        return 1

    if args.dry_run:
        added, updated = merge_into_main_index(entries, dry_run=True)
        rows, skipped = build_box_rows(entries)
        print(f"[dry-run] 索引：新增 {added}，更新 {updated}（共 {len(entries)} 条）")
        print(f"[dry-run] box 行：{len(rows)}，跳过 {len(skipped)}")
        return 0

    if not args.no_backup:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup = INDEX_MAIN.with_name(f"史略索引_01至02.json.bak_{ts}")
        shutil.copy2(INDEX_MAIN, backup)
        print(f"已备份 → {backup.name}")

    added, updated = merge_into_main_index(entries, dry_run=False)
    print(f"✅ 全局索引合并：新增 {added}，更新 {updated}（共 {len(entries)} 条二期）")

    main_entries, _, _ = load_index_entries(INDEX_MAIN)
    zhanguo_total = sum(1 for e in main_entries if e.get("二级朝代坐标") == "战国")
    print(f"校验：全局索引战国条目 = {zhanguo_total}")

    if args.local_only:
        return 0

    entry_ids = {str(e["史略ID"]) for e in entries}
    rows, skipped = build_box_rows(entries)
    if skipped:
        print(f"⚠️ build_box_rows 跳过 {len(skipped)} 条: {', '.join(skipped)}")
    details = load_supplement_details(entry_ids)
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

    missing = sorted(entry_ids - set(details.keys()))
    if missing:
        print(f"⚠️ 有索引暂无详情: {len(missing)} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
