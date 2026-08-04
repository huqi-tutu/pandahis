#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
线上史略详情 SSOT：仅 11新标注条目翻译 + 06朝代知识补全。

- 不读取 04史料翻译（V1 详情留本地）
- 不触碰 box_graph_* / box_critique / box_relic（任务关系、评述、见证）
- 未来新增翻译：写入 data/11新标注条目翻译/ 后运行本模块同步
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools" / "openclaw-historiography"
TRANSLATE_DIR = TOOLS / "historiography-translate"

if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
if str(TRANSLATE_DIR) not in sys.path:
    sys.path.insert(0, str(TRANSLATE_DIR))

from paths_config import histograph_paths  # noqa: E402
from lib.remote_sync import (  # noqa: E402
    encode_source_original_json,
    ensure_schema,
    upsert_translate_detail,
    _ensure_detail_source_column,
    _connect,
)


def find_json_by_id(directory: Path, entry_id: str) -> Path | None:
    """在目录（含一层子目录）中按史略 ID 查找详情 JSON。"""
    if not directory.is_dir():
        return None
    matches = sorted(directory.glob(f"{entry_id}_*.json"))
    if not matches:
        matches = sorted(directory.glob(f"**/{entry_id}_*.json"))
    if matches:
        return matches[0]
    direct = directory / f"{entry_id}.json"
    return direct if direct.is_file() else None


def row_from_detail_json(path: Path, *, detail_source: str) -> dict | None:
    data = json.loads(path.read_text(encoding="utf-8"))
    detail = str(data.get("翻译详情") or "").strip()
    if not detail:
        return None
    box_id = str(data.get("史略ID") or path.stem.split("_", 1)[0]).strip()
    citation = data.get("原文出处")
    return {
        "box_id": box_id,
        "translate_detail": detail,
        "source_original_json": encode_source_original_json(data.get("史料原文")),
        "source_citation": (
            str(citation).strip() if isinstance(citation, str) and citation.strip() else None
        ),
        "detail_source": detail_source,
    }


def build_online_detail_rows(
    online_ids: set[str] | None = None,
    *,
    dir_11: Path | None = None,
    dir_06_detail: Path | None = None,
    agg_06: Path | None = None,
) -> tuple[list[dict], dict]:
    """
    合并线上详情：11（translate）优先，06（compose）兜底。
    online_ids 为 None 时不按索引过滤（全量扫描 11+06）。
    """
    paths = histograph_paths()
    dir_11 = dir_11 or paths["data"] / "11新标注条目翻译"
    dir_06_detail = dir_06_detail or paths["dynasty_knowledge_details"]
    agg_06 = agg_06 or paths["dynasty_knowledge_detail_aggregate"]

    merged: dict[str, dict] = {}
    stats = {"v11": 0, "v06_file": 0, "v06_agg": 0, "missing_in_index": 0}

    candidate_ids: set[str]
    if online_ids is not None:
        candidate_ids = online_ids
    else:
        candidate_ids = set()
        for p in dir_11.glob("GLBL_*.json"):
            candidate_ids.add(p.name.split("_", 1)[0])
        for p in dir_06_detail.glob("GLBL_*.json"):
            candidate_ids.add(p.name.split("_", 1)[0])
        if agg_06.is_file():
            agg = json.loads(agg_06.read_text(encoding="utf-8"))
            for item in agg.get("entries") or []:
                eid = str(item.get("史略ID") or "").strip()
                if eid:
                    candidate_ids.add(eid)

    for eid in sorted(candidate_ids):
        if online_ids is not None and eid not in online_ids:
            continue
        row = None
        p11 = find_json_by_id(dir_11, eid)
        if p11:
            row = row_from_detail_json(p11, detail_source="translate")
            if row:
                stats["v11"] += 1
        if not row:
            p06 = find_json_by_id(dir_06_detail, eid)
            if p06:
                row = row_from_detail_json(p06, detail_source="compose")
                if row:
                    stats["v06_file"] += 1
        if row:
            merged[eid] = row

    if agg_06.is_file():
        agg = json.loads(agg_06.read_text(encoding="utf-8"))
        for item in agg.get("entries") or []:
            eid = str(item["史略ID"]).strip()
            if online_ids is not None and eid not in online_ids:
                continue
            if eid in merged:
                continue
            detail = str(item.get("翻译详情") or "").strip()
            if not detail:
                continue
            merged[eid] = {
                "box_id": eid,
                "translate_detail": detail,
                "source_original_json": encode_source_original_json(item.get("史料原文")),
                "source_citation": (
                    str(item["原文出处"]).strip() if item.get("原文出处") else None
                ),
                "detail_source": "compose",
            }
            stats["v06_agg"] += 1

    if online_ids is not None:
        stats["missing_in_index"] = len(online_ids) - len(merged)

    return [merged[k] for k in sorted(merged)], stats


def sync_online_details(
    online_ids: set[str] | None = None,
    *,
    dry_run: bool = False,
) -> tuple[bool, str, dict]:
    """
    Upsert 11+06 详情；删除线上不在允许集合内的 historical_box_detail（含 V1/04 残留）。
    仅操作 historical_box_detail，不触碰评述/见证/关系子表。
    """
    rows, stats = build_online_detail_rows(online_ids)
    allowed_ids = [row["box_id"] for row in rows]

    if dry_run:
        return (
            True,
            f"dry-run: 详情 {len(rows)} 条（11={stats['v11']} 06文件={stats['v06_file']} "
            f"06汇总={stats['v06_agg']}），将 prune 非 11/06 详情",
            stats,
        )

    conn = _connect()
    try:
        with conn.cursor() as cursor:
            ensure_schema(cursor)
            _ensure_detail_source_column(cursor)
            for row in rows:
                upsert_translate_detail(
                    cursor,
                    row["box_id"],
                    row["translate_detail"],
                    row.get("source_original_json"),
                    row.get("source_citation"),
                    detail_source=row.get("detail_source"),
                )
            deleted = 0
            if allowed_ids:
                placeholders = ", ".join(["%s"] * len(allowed_ids))
                cursor.execute(
                    f"DELETE FROM historical_box_detail WHERE box_id NOT IN ({placeholders})",
                    allowed_ids,
                )
                deleted = cursor.rowcount
            else:
                cursor.execute("DELETE FROM historical_box_detail")
                deleted = cursor.rowcount
            cursor.execute("SELECT COUNT(*) AS cnt FROM historical_box_detail")
            final = cursor.fetchone()["cnt"]
        conn.commit()
        msg = (
            f"详情 upsert {len(rows)} 条（11={stats['v11']} 06={stats['v06_file'] + stats['v06_agg']}），"
            f"删除非 11/06 详情 {deleted} 条，当前 historical_box_detail 共 {final} 条"
        )
        return True, msg, stats
    except Exception as exc:
        conn.rollback()
        return False, str(exc), stats
    finally:
        conn.close()


def load_online_ids(index_path: Path) -> set[str]:
    entries = json.loads(index_path.read_text(encoding="utf-8"))
    if isinstance(entries, dict):
        entries = entries.get("entries") or []
    return {str(e["史略ID"]).strip() for e in entries}
