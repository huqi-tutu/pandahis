#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量剥离见证「文物介绍」中的内部层级术语（不重跑 LLM）。

策略（宽表述 + 优先剥码）：
  1. 优先删掉 A+/A层/C层 等代号，保留原文已有的说明性短名
  2. A+/本人造物 用宽表述「本人直接遗存」（含作品/用器/工程），禁止窄化为「用器」
  3. 只动读者可见的 `文物介绍` / `box_relic.description`
  4. `优先级判定理由` 默认不动（规则允许内部保留分层代号）

用法：
  python3 scrub_witness_jargon.py              # dry-run 统计
  python3 scrub_witness_jargon.py --apply      # 写本地 JSON + 线上 DB
  python3 scrub_witness_jargon.py --apply --local-only
  python3 scrub_witness_jargon.py --apply --db-only
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[3]  # pandahis/pandahis
WITNESS_DIR = ROOT / "data" / "09见证"
MID = ROOT / "data" / "05工作流中间产物" / "评述见证补全"
sys.path.insert(0, str(SCRIPT_DIR.parent.parent / "historiography-translate"))

# 长词优先。原则：
# - 「属X层 + 官方短名」→ 只剥「X层」，留短名（最安全）
# - 裸代号 → 展开为官方短名的白话（与 SSOT 分层表对齐）
# - A+/本人造物 → 「本人直接遗存」（宽表述，不写死「用器」）
RULES: list[tuple[re.Pattern[str], str, str]] = [
    # --- 完整套话：只剥代号 ---
    (re.compile(r"属D层后世纪念"), "属后世纪念", "属D层后世纪念"),
    (re.compile(r"属C层专属空间见证"), "属专属空间见证", "属C层专属空间见证"),
    (re.compile(r"属C层专属空间"), "属专属空间", "属C层专属空间"),
    (re.compile(r"C层专属空间"), "专属空间", "C层专属空间"),
    (re.compile(r"属A层直接实物"), "属直接实物", "属A层直接实物"),
    (re.compile(r"属A[+＋]本人造物"), "属本人直接遗存", "属A+本人造物"),
    (re.compile(r"为A[+＋]级本人造物"), "为本人直接遗存", "为A+级本人造物"),
    (re.compile(r"为A[+＋]本人造物"), "为本人直接遗存", "为A+本人造物"),
    (re.compile(r"A[+＋]级本人造物"), "本人直接遗存", "A+级本人造物"),
    (re.compile(r"A[+＋]本人造物"), "本人直接遗存", "A+本人造物"),
    (re.compile(r"属典型A[+＋]层见证"), "属本人直接遗存的见证", "属典型A+层见证"),
    (re.compile(r"属典型A[+＋]层"), "属本人直接遗存", "属典型A+层"),
    (re.compile(r"属典型A[+＋]"), "属本人直接遗存", "属典型A+"),
    (re.compile(r"典型A[+＋]层见证"), "本人直接遗存的见证", "典型A+层见证"),
    (re.compile(r"最高等级的本人造物见证"), "最直接的本人遗存见证", "最高等级的本人造物见证"),
    (re.compile(r"最高等级的本人造物"), "最直接的本人遗存", "最高等级的本人造物"),
    (re.compile(r"本人造物见证"), "本人直接遗存的见证", "本人造物见证"),
    (re.compile(r"本人造物"), "本人直接遗存", "本人造物"),
    # --- 见证力口吻（非分层，但读者可见）---
    (re.compile(r"见证力属于"), "证据上属于", "见证力属于"),
    (re.compile(r"见证力属"), "证据上属", "见证力属"),
    (re.compile(r"具有极高的见证力"), "证据关系十分直接", "具有极高的见证力"),
    (re.compile(r"见证力极高"), "证据十分直接", "见证力极高"),
    (re.compile(r"见证力有限"), "证据有限", "见证力有限"),
    (re.compile(r"其见证力在于"), "其价值在于", "其见证力在于"),
    (re.compile(r"见证力"), "证据效力", "见证力"),
    # --- B 层已带短名：剥括号/代号 ---
    (re.compile(r"早期存在性物证（B层）"), "早期存在性物证", "早期存在性物证（B层）"),
    (re.compile(r"属于典型的B层存在性实物"), "属于早期存在性实物", "属于典型的B层存在性实物"),
    (re.compile(r"B层存在性实物"), "早期存在性实物", "B层存在性实物"),
    (re.compile(r"B层存在性物证"), "早期存在性物证", "B层存在性物证"),
    (re.compile(r"（[A-F]层）"), "", "（X层）"),
    # --- 裸「属X层」：展开为官方短名白话 ---
    (re.compile(r"属A[+＋]层"), "属本人直接遗存", "属A+层"),
    (re.compile(r"属A层"), "属直接实物", "属A层"),
    (re.compile(r"属B层"), "属早期存在性物证", "属B层"),
    (re.compile(r"属C层"), "属专属空间", "属C层"),
    (re.compile(r"属D层"), "属后世纪念", "属D层"),
    (re.compile(r"属E层"), "属证据较弱的关联", "属E层"),
    (re.compile(r"属F层"), "属后世诗文", "属F层"),
    # --- 残留裸代号：优先删除（前后文通常已有说明）---
    (re.compile(r"A[+＋]层"), "", "A+层"),
    (re.compile(r"A[+＋]级"), "", "A+级"),
    (re.compile(r"(?<![A-Za-z])A[+＋](?![A-Za-z0-9])"), "", "A+"),
    (re.compile(r"(?<![A-Za-z])A层"), "", "A层"),
    (re.compile(r"(?<![A-Za-z])B层"), "", "B层"),
    (re.compile(r"(?<![A-Za-z])C层"), "", "C层"),
    (re.compile(r"(?<![A-Za-z])D层"), "", "D层"),
    (re.compile(r"(?<![A-Za-z])E层"), "", "E层"),
    (re.compile(r"(?<![A-Za-z])F层"), "", "F层"),
]

# 替换后的标点/赘语清理
CLEANUPS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"属属"), "属"),
    (re.compile(r"的的"), "的"),
    (re.compile(r"，，+"), "，"),
    (re.compile(r"。。+"), "。"),
    (re.compile(r"\s{2,}"), " "),
    (re.compile(r"，。"), "。"),
    (re.compile(r"。，"), "。"),
]

RESIDUAL = re.compile(r"A[+＋]|本人造物|[A-F]层|见证力")


def scrub_text(text: str) -> tuple[str, dict[str, int]]:
    out = text or ""
    hits: dict[str, int] = {}
    for pat, repl, name in RULES:
        out, n = pat.subn(repl, out)
        if n:
            hits[name] = hits.get(name, 0) + n
    for pat, repl in CLEANUPS:
        out = pat.sub(repl, out)
    return out.strip(), hits


def merge_hits(dst: dict[str, int], src: dict[str, int]) -> None:
    for k, v in src.items():
        dst[k] = dst.get(k, 0) + v


def iter_local_files() -> list[Path]:
    return sorted(WITNESS_DIR.glob("GLBL_*_见证.json"))


def scrub_local(apply: bool) -> dict:
    changed_files = 0
    changed_rows = 0
    hits: dict[str, int] = {}
    residual_after = 0
    diffs: list[dict] = []
    for path in iter_local_files():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        entries = data.get("entries")
        if not isinstance(entries, list):
            continue
        file_changed = False
        new_entries = []
        for row in entries:
            if not isinstance(row, dict):
                new_entries.append(row)
                continue
            old = str(row.get("文物介绍") or "")
            new, h = scrub_text(old)
            if new != old:
                file_changed = True
                changed_rows += 1
                merge_hits(hits, h)
                diffs.append(
                    {
                        "source": "local",
                        "file": path.name,
                        "box_id": str(row.get("史略ID") or data.get("史略ID") or ""),
                        "box_title": str(row.get("史略名称") or data.get("史略名称") or ""),
                        "relic_id": str(row.get("文物ID") or ""),
                        "name": str(row.get("文物标题") or ""),
                        "rules": h,
                        "before": old,
                        "after": new,
                    }
                )
                if RESIDUAL.search(new):
                    residual_after += 1
                new_entries.append({**row, "文物介绍": new})
            else:
                if RESIDUAL.search(old):
                    residual_after += 1
                new_entries.append(row)
        if file_changed:
            changed_files += 1
            if apply:
                data = {**data, "entries": new_entries}
                path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "changed_files": changed_files,
        "changed_rows": changed_rows,
        "hits": hits,
        "residual_rows_still_matching": residual_after,
        "diffs": diffs,
    }


def scrub_db(apply: bool) -> dict:
    import pymysql

    # reuse translate defaults
    host = "49.235.165.220"
    port = 3306
    user = "histomap_admin"
    password = "pandahis#666"
    database = "histomap"
    try:
        from lib.remote_sync import mysql_settings  # type: ignore

        s = mysql_settings()
        host, port, user, password, database = (
            s["host"],
            s["port"],
            s["user"],
            s["password"],
            s["database"],
        )
    except Exception:
        pass

    conn = pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        charset="utf8mb4",
        autocommit=False,
    )
    hits: dict[str, int] = {}
    changed = 0
    residual = 0
    diffs: list[dict] = []
    rows: list = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT r.id, r.box_id, r.name, r.description, b.title AS box_title "
                "FROM box_relic r "
                "LEFT JOIN historical_box b ON b.id = r.box_id "
                "WHERE r.description REGEXP %s "
                "ORDER BY r.box_id, r.id",
                (r"A\+|本人造物|[A-F]层|见证力",),
            )
            rows = cur.fetchall()
            for rid, box_id, name, desc, box_title in rows:
                old = desc or ""
                new, h = scrub_text(old)
                if new != old:
                    changed += 1
                    merge_hits(hits, h)
                    diffs.append(
                        {
                            "source": "db",
                            "id": rid,
                            "box_id": box_id,
                            "box_title": box_title or "",
                            "name": name,
                            "rules": h,
                            "before": old,
                            "after": new,
                        }
                    )
                    if apply:
                        cur.execute(
                            "UPDATE box_relic SET description=%s WHERE id=%s",
                            (new, rid),
                        )
                if RESIDUAL.search(new if new != old else old):
                    residual += 1
            if apply:
                conn.commit()
            else:
                conn.rollback()
    finally:
        conn.close()
    return {
        "scanned": len(rows),
        "changed_rows": changed,
        "hits": hits,
        "residual_rows_still_matching": residual,
        "diffs": diffs,
    }


def write_review_md(diffs: list[dict], path: Path, *, mode: str) -> None:
    lines: list[str] = [
        "# 见证文物介绍 · 术语脱敏对照表",
        "",
        f"> 生成模式：`{mode}` · 共 **{len(diffs)}** 条变更",
        ">",
        "> 策略：宽表述 + 优先剥码（不重跑 LLM）。请逐条确认改后整句是否连贯。",
        "",
        "## 审阅勾选",
        "",
        "- [ ] 已通读全部条目",
        "- [ ] 发现不通顺条目（在对应小节下批注）",
        "",
    ]
    for i, d in enumerate(diffs, start=1):
        box_id = d.get("box_id") or ""
        box_title = d.get("box_title") or ""
        name = d.get("name") or ""
        rid = d.get("id") or d.get("relic_id") or ""
        rules = d.get("rules") or {}
        rule_s = "、".join(f"{k}×{v}" for k, v in rules.items()) or "（无规则命中记录）"
        head = f"{box_id}"
        if box_title:
            head += f" · {box_title}"
        head += f" · {name}"
        if rid:
            head += f" （id={rid}）"
        lines.extend(
            [
                f"## {i}. {head}",
                "",
                f"命中规则：{rule_s}",
                "",
                "**改前**",
                "",
                d.get("before") or "",
                "",
                "**改后**",
                "",
                d.get("after") or "",
                "",
                "---",
                "",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="实际写入；默认 dry-run")
    ap.add_argument("--local-only", action="store_true")
    ap.add_argument("--db-only", action="store_true")
    args = ap.parse_args()

    report: dict = {"mode": "apply" if args.apply else "dry-run"}
    if not args.db_only:
        report["local"] = scrub_local(apply=args.apply)
    if not args.local_only:
        report["db"] = scrub_db(apply=args.apply)

    # 审阅文档以线上 DB 变更为准（读者可见）；若仅 local 则用 local
    review_diffs = (report.get("db") or {}).get("diffs") or (report.get("local") or {}).get("diffs") or []
    review_md = MID / "见证术语脱敏_改前改后对照.md"
    write_review_md(review_diffs, review_md, mode=report["mode"])

    # JSON 报告不重复塞全文 diffs（对照表已落盘）
    slim = {
        "mode": report["mode"],
        "local": {
            k: v
            for k, v in (report.get("local") or {}).items()
            if k != "diffs"
        }
        or None,
        "db": {
            k: v
            for k, v in (report.get("db") or {}).items()
            if k != "diffs"
        }
        or None,
        "review_md": str(review_md),
        "review_count": len(review_diffs),
    }
    if slim["local"] is None:
        del slim["local"]
    if slim["db"] is None:
        del slim["db"]

    out = MID / "scrub_witness_jargon_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(slim, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(slim, ensure_ascii=False, indent=2))
    print(f"\nreport → {out}")
    print(f"review → {review_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
