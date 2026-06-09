#!/usr/bin/env python3
"""
从 prd/历史图谱.xlsx 导出 MySQL 语句：historical_unit、historical_box、
box_graph_node、box_graph_edge、box_critique、box_relic。
用法：python xlsx_export_mysql.py [--out PATH]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent.parent
sys.path.insert(0, str(_SCRIPT_DIR))

from import_home_xlsx import PRD_REGIONS, parse_units_and_boxes  # noqa: E402

REGION_TO_L1 = {r["id"]: i + 1 for i, r in enumerate(PRD_REGIONS)}


def q(s: str | None) -> str:
    if s is None:
        return "NULL"
    return "'" + str(s).replace("\\", "\\\\").replace("'", "''") + "'"


def box_status(excel_status: str) -> int:
    t = (excel_status or "").strip()
    if "下架" in t or "禁用" in t:
        return 0
    return 1


def kind_to_type(k: str) -> str:
    return {"person": "person", "event": "event", "org": "org", "work": "work", "place": "place"}.get(k, "event")


def chunk_list(xs: list[str], size: int):
    for i in range(0, len(xs), size):
        yield xs[i : i + size]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", type=Path, default=None, help="默认 prd/历史图谱.xlsx")
    ap.add_argument("--out", type=Path, default=_REPO_ROOT / "deploy" / "xlsx-import-histomap.sql")
    ap.add_argument(
        "--stmts-json",
        type=Path,
        default=_REPO_ROOT / "deploy" / "xlsx-import-histomap.stmts.json",
        help="逐条可执行 SQL 的 JSON 数组（供脚本/MCP 顺序执行）",
    )
    args = ap.parse_args()

    xlsx = args.xlsx
    if xlsx is None:
        xlsx = _REPO_ROOT / "prd" / "历史图谱.xlsx"
        if not xlsx.is_file():
            xlsx = _REPO_ROOT / "prd" / "历史图谱 - 首页数据.xlsx"
    if not xlsx.is_file():
        raise SystemExit(f"未找到 Excel: {xlsx}")

    units, boxes = parse_units_and_boxes(xlsx)
    stmts: list[str] = ["SET NAMES utf8mb4;", "USE histomap;"]

    box_ids = [b["id"] for b in boxes]

    for part in ("box_graph_edge", "box_critique", "box_relic", "box_graph_node"):
        for ch in chunk_list(box_ids, 120):
            inn = ",".join(q(bid) for bid in ch)
            stmts.append(f"DELETE FROM {part} WHERE box_id IN ({inn});")
    for ch in chunk_list(box_ids, 120):
        inn = ",".join(q(bid) for bid in ch)
        stmts.append(f"DELETE FROM historical_box WHERE id IN ({inn});")

    uvals: list[str] = []
    for u in units:
        l1 = REGION_TO_L1.get(u["civilizationId"], 1)
        era = (u.get("eraText") or "").strip()
        if len(era) > 64:
            era = era[:64]
        dyn = (u.get("dynastyName") or "").strip()
        if len(dyn) > 64:
            dyn = dyn[:64]
        name = (u.get("name") or "")[:128]
        summary = u.get("summary") or ""
        core = "[]"
        uvals.append(
            f"({q(u['id'])},{q(name)},{q(dyn)},{q(era)},{l1},"
            f"{int(u['startYear'])},{int(u['endYear'])},{int(u['durationYears'])},"
            f"{q(core)},{q(summary)},1)"
        )

    def emit_chunked_insert(
        table_cols: str,
        values_rows: list[str],
        chunk_size: int,
        suffix: str,
    ) -> None:
        for i in range(0, len(values_rows), chunk_size):
            chunk = values_rows[i : i + chunk_size]
            body = ",\n".join(chunk)
            if suffix:
                stmts.append(f"INSERT INTO {table_cols} VALUES\n{body}\n{suffix};")
            else:
                stmts.append(f"INSERT INTO {table_cols} VALUES\n{body};")

    unit_suffix = (
        "ON DUPLICATE KEY UPDATE name=VALUES(name), dynasty_name=VALUES(dynasty_name), "
        "era_name=VALUES(era_name), civilization_l1_id=VALUES(civilization_l1_id), "
        "start_year=VALUES(start_year), end_year=VALUES(end_year), duration_years=VALUES(duration_years), "
        "core_topics_json=VALUES(core_topics_json), summary=VALUES(summary), status=VALUES(status)"
    )
    emit_chunked_insert(
        "historical_unit (id, name, dynasty_name, era_name, civilization_l1_id, "
        "start_year, end_year, duration_years, core_topics_json, summary, status)",
        uvals,
        120,
        unit_suffix,
    )

    bvals: list[str] = []
    for b in boxes:
        title = (b.get("title") or b["id"])[:128]
        cat = (b.get("categoryKey") or "shilue")[:16]
        sy = int(b["startYear"])
        ey = int(b["endYear"])
        imp = int(b.get("importanceLevel") or 3)
        st = box_status(str(b.get("excelStatus") or ""))
        detail_md = "\n\n".join(b.get("detail") or [])
        if len(detail_md) > 60000:
            detail_md = detail_md[:60000]
        bvals.append(
            f"({q(b['id'])},{q(b['unitId'])},{q(title)},{q(cat)},{sy},{ey},{imp},{st},"
            f"{q(detail_md)},{q('{}')})"
        )

    box_suffix = (
        "ON DUPLICATE KEY UPDATE unit_id=VALUES(unit_id), title=VALUES(title), category_key=VALUES(category_key), "
        "start_year=VALUES(start_year), end_year=VALUES(end_year), importance_level=VALUES(importance_level), "
        "status=VALUES(status), detail_md=VALUES(detail_md), original_ref_json=VALUES(original_ref_json)"
    )
    emit_chunked_insert(
        "historical_box (id, unit_id, title, category_key, start_year, end_year, "
        "importance_level, status, detail_md, original_ref_json)",
        bvals,
        12,
        box_suffix,
    )

    # graph nodes (batch insert)
    nrows: list[str] = []
    for b in boxes:
        bid = b["id"]
        g = b.get("graph") or {}
        for node in g.get("nodes") or []:
            nk = (node.get("key") or "")[:64]
            nt = kind_to_type(str(node.get("kind") or "event"))[:16]
            nm = (node.get("name") or "")[:64]
            nrows.append(f"({q(bid)},{q(nk)},{q(nt)},{q(nm)},{q('{}')})")

    if nrows:
        emit_chunked_insert(
            "box_graph_node (box_id, node_key, node_type, name, extra_json)",
            nrows,
            150,
            "ON DUPLICATE KEY UPDATE node_type=VALUES(node_type), name=VALUES(name), extra_json=VALUES(extra_json)",
        )

    erows: list[str] = []
    for b in boxes:
        bid = b["id"]
        g = b.get("graph") or {}
        for e in g.get("edges") or []:
            fk = (e.get("from") or "")[:64]
            tk = (e.get("to") or "")[:64]
            lb = (e.get("label") or "")[:32]
            erows.append(f"({q(bid)},{q(fk)},{q(tk)},{q(lb)})")

    if erows:
        emit_chunked_insert(
            "box_graph_edge (box_id, from_node_key, to_node_key, label)",
            erows,
            200,
            "",
        )

    crows: list[str] = []
    for b in boxes:
        bid = b["id"]
        for i, c in enumerate(b.get("critiques") or []):
            author = (c.get("author") or "")[:64]
            era_t = (c.get("eraText") or "")[:64]
            content = c.get("content") or ""
            src = (c.get("source") or "")[:256]
            crows.append(f"({q(bid)},{q(author)},{q(era_t)},NULL,{q(content)},{q(src)},{i + 1})")

    if crows:
        emit_chunked_insert(
            "box_critique (box_id, author, era_text, year_value, content, source, sort_order)",
            crows,
            200,
            "",
        )

    rrows: list[str] = []
    for b in boxes:
        bid = b["id"]
        for i, r in enumerate(b.get("relics") or []):
            nm = (r.get("name") or "")[:128]
            desc = r.get("description") or ""
            mus = (r.get("museum") or "")[:128]
            rrows.append(f"({q(bid)},{q(nm)},NULL,{q(desc)},{q(mus)},{i + 1})")

    if rrows:
        emit_chunked_insert(
            "box_relic (box_id, name, image_url, description, museum, sort_order)",
            rrows,
            200,
            "",
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    header = f"-- Auto-generated from {xlsx.name}\n-- Statements: {len(stmts)}\n\n"
    text = header + "\n\n".join(stmts) + "\n"
    args.out.write_text(text, encoding="utf-8")
    args.stmts_json.write_text(json.dumps(stmts, ensure_ascii=False, indent=0), encoding="utf-8")
    print(
        f"wrote {args.out} + {args.stmts_json} "
        f"({len(units)} units, {len(boxes)} boxes, {len(stmts)} SQL statements, {len(text)} bytes sql)"
    )


if __name__ == "__main__":
    main()
