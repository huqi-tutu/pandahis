#!/usr/bin/env python3
"""降级 GLBL × 本地翻译 × 线上详情 交叉表（只读）。"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
AUDIT_JSON = ROOT / "data" / "05工作流中间产物" / "薄标注待补全" / "glbl_thickness_audit.json"
TRANSLATE_DIR = ROOT / "data" / "04史料翻译"
AGGREGATE_JSON = TRANSLATE_DIR / "史略翻译_汇总.json"
COMMENTARY_DIR = ROOT / "data" / "08评述"
WITNESS_DIR = ROOT / "data" / "09见证"
OUT_JSON = ROOT / "data" / "05工作流中间产物" / "薄标注待补全" / "downgrade_cross_table.json"
OUT_MD = ROOT / "data" / "05工作流中间产物" / "薄标注待补全" / "降级条目_翻译上线交叉表.md"

TOOLS = ROOT / "tools" / "openclaw-historiography"
TRANSLATE_LIB = TOOLS / "historiography-translate" / "lib"
if str(TRANSLATE_LIB) not in sys.path:
    sys.path.insert(0, str(TRANSLATE_LIB))


def resolve_output_path(entry_id: str, base: Path, entry_name: str = "") -> Path:
    import re

    unsafe = re.compile(r'[/\\:*?"<>|\n\r\t]')
    safe = re.sub(r"\s+", "", unsafe.sub("", (entry_name or "").strip())) or "未命名"
    canonical = base / f"{entry_id}_{safe}.json"
    if entry_name and canonical.is_file():
        return canonical
    matches = sorted(base.glob(f"{entry_id}_*.json"))
    if matches:
        return matches[0]
    legacy = base / f"{entry_id}.json"
    return legacy if legacy.is_file() else canonical


def _load_env() -> None:
    env_file = TOOLS / ".env"
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def _translation_status(eid: str, name: str) -> dict[str, Any]:
    fp = resolve_output_path(eid, TRANSLATE_DIR, name)
    in_aggregate = False
    detail_chars = 0
    if AGGREGATE_JSON.is_file():
        agg_doc = json.loads(AGGREGATE_JSON.read_text(encoding="utf-8"))
        agg_rows = agg_doc.get("entries") if isinstance(agg_doc, dict) else agg_doc
        if isinstance(agg_rows, list):
            for row in agg_rows:
                if isinstance(row, dict) and str(row.get("史略ID")) == eid:
                    in_aggregate = True
                    break
    if fp.is_file():
        doc = json.loads(fp.read_text(encoding="utf-8"))
        text = str(doc.get("翻译详情") or doc.get("母本顺译") or "").strip()
        detail_chars = len(text)
        return {
            "local_translate_file": str(fp.relative_to(ROOT)),
            "in_aggregate": in_aggregate,
            "translate_chars": detail_chars,
            "has_translation": bool(text),
        }
    return {
        "local_translate_file": None,
        "in_aggregate": in_aggregate,
        "translate_chars": 0,
        "has_translation": in_aggregate,
    }


def _has_sidecar(eid: str, directory: Path) -> bool:
    if not directory.is_dir():
        return False
    return bool(list(directory.glob(f"{eid}_*.json")))


def _query_online(ids: list[str]) -> dict[str, dict[str, Any]]:
    _load_env()
    try:
        import pymysql
    except ImportError:
        return {i: {"online_box": None, "online_detail": None, "error": "pymysql missing"} for i in ids}

    if not ids:
        return {}

    conn = pymysql.connect(
        host=os.environ.get("MYSQL_HOST", "49.235.165.220"),
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        user=os.environ.get("MYSQL_USER", "histomap_admin"),
        password=os.environ.get("MYSQL_PASSWORD", "pandahis#666"),
        database=os.environ.get("MYSQL_DB", "histomap"),
        charset="utf8mb4",
        connect_timeout=15,
        read_timeout=120,
        write_timeout=120,
        cursorclass=pymysql.cursors.DictCursor,
    )
    out: dict[str, dict[str, Any]] = {i: {"online_box": False, "online_detail": False} for i in ids}
    try:
        placeholders = ",".join(["%s"] * len(ids))
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT id, title, category_key FROM historical_box WHERE id IN ({placeholders})",
                ids,
            )
            for row in cur.fetchall():
                bid = str(row["id"])
                out[bid]["online_box"] = True
                out[bid]["online_name"] = row.get("title")
                out[bid]["online_category"] = row.get("category_key")

            cur.execute(
                f"""
                SELECT box_id,
                       CHAR_LENGTH(COALESCE(translate_detail, '')) AS detail_len
                FROM historical_box_detail
                WHERE box_id IN ({placeholders})
                """,
                ids,
            )
            for row in cur.fetchall():
                bid = str(row["box_id"])
                out[bid]["online_detail"] = int(row.get("detail_len") or 0) > 0
                out[bid]["online_detail_chars"] = int(row.get("detail_len") or 0)
    finally:
        conn.close()
    return out


def build_cross_table() -> dict[str, Any]:
    audit = json.loads(AUDIT_JSON.read_text(encoding="utf-8"))
    rows_in = [e for e in audit.get("entries") or [] if e.get("verdict") == "downgrade_recommended"]
    rows_in.sort(key=lambda x: (x.get("source_han_chars_total") or 0, x.get("史略ID") or ""))

    ids = [str(r["史略ID"]) for r in rows_in]
    online = _query_online(ids)

    rows: list[dict[str, Any]] = []
    for r in rows_in:
        eid = str(r["史略ID"])
        name = str(r.get("史略名称") or "")
        tr = _translation_status(eid, name)
        on = online.get(eid, {})
        has_commentary = _has_sidecar(eid, COMMENTARY_DIR)
        has_witness = _has_sidecar(eid, WITNESS_DIR)

        local = tr["has_translation"]
        live = bool(on.get("online_detail"))
        box = bool(on.get("online_box"))

        if live:
            exposure = "已上线详情"
        elif local:
            exposure = "仅本地翻译"
        elif box:
            exposure = "仅索引上线"
        else:
            exposure = "未触达"

        rows.append(
            {
                "史略ID": eid,
                "史略名称": name,
                "史略分类": r.get("史略分类"),
                "朝代": r.get("二级朝代坐标") or r.get("朝代ID"),
                "source_han_chars": r.get("source_han_chars_total"),
                "has_local_translation": local,
                "translate_file": tr.get("local_translate_file"),
                "translate_chars": tr.get("translate_chars"),
                "in_aggregate": tr.get("in_aggregate"),
                "online_box": box,
                "online_detail": live,
                "online_detail_chars": on.get("online_detail_chars", 0),
                "has_commentary": has_commentary,
                "has_witness": has_witness,
                "exposure": exposure,
                "recommended_action": r.get("recommended_action"),
            }
        )

    summary = {
        "total": len(rows),
        "local_translation": sum(1 for x in rows if x["has_local_translation"]),
        "online_detail": sum(1 for x in rows if x["online_detail"]),
        "online_box_only": sum(1 for x in rows if x["online_box"] and not x["online_detail"]),
        "commentary": sum(1 for x in rows if x["has_commentary"]),
        "witness": sum(1 for x in rows if x["has_witness"]),
        "fully_untouched": sum(1 for x in rows if x["exposure"] == "未触达"),
    }

    return {
        "schema": "downgrade_cross_table/v1",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_audit": str(AUDIT_JSON),
        "summary": summary,
        "entries": rows,
    }


def render_md(report: dict[str, Any]) -> str:
    s = report["summary"]
    lines = [
        "# 降级条目 × 翻译 × 上线 交叉表",
        "",
        f"- 生成时间：{report['generated_at']}",
        f"- 来源审计：`glbl_thickness_audit.json`（30 条 downgrade_recommended）",
        "",
        "## 汇总",
        "",
        f"| 指标 | 数量 |",
        f"|------|------|",
        f"| 建议降级总数 | {s['total']} |",
        f"| 已有本地翻译 | {s['local_translation']} |",
        f"| 线上已有详情 | {s['online_detail']} |",
        f"| 仅索引上线（无详情） | {s['online_box_only']} |",
        f"| 有评述 | {s['commentary']} |",
        f"| 有见证 | {s['witness']} |",
        f"| 完全未触达 | {s['fully_untouched']} |",
        "",
        "## 明细",
        "",
        "| GLBL | 名称 | 分类 | 原文字 | 本地翻译 | 译文字数 | 线上索引 | 线上详情 | 触达状态 |",
        "|------|------|------|--------|----------|----------|----------|----------|----------|",
    ]
    for r in report["entries"]:
        loc = "✅" if r["has_local_translation"] else "—"
        box = "✅" if r["online_box"] else "—"
        det = "✅" if r["online_detail"] else "—"
        lines.append(
            f"| {r['史略ID']} | {r['史略名称']} | {r['史略分类']} | {r['source_han_chars']} | "
            f"{loc} | {r['translate_chars'] or '—'} | {box} | {det} | {r['exposure']} |"
        )

    lines.extend(
        [
            "",
            "## 处置优先级建议",
            "",
            "1. **已上线详情**：优先评估是否下线详情或保留旧内容 + 禁止增量更新；后续用朝代补全新 GLBL 替换。",
            "2. **仅本地翻译**：可删本地译稿或归档；不必 sync 线上。",
            "3. **仅索引上线**：historical_box 有条但无 detail，小程序可能显示空框——优先补全或下架索引。",
            "4. **未触达**：直接走朝代补全候选，成本最低。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    if not AUDIT_JSON.is_file():
        print(f"❌ 缺少审计文件: {AUDIT_JSON}", file=sys.stderr)
        return 1

    report = build_cross_table()
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_MD.write_text(render_md(report), encoding="utf-8")

    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"\n✅ JSON → {OUT_JSON}")
    print(f"✅ MD   → {OUT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
