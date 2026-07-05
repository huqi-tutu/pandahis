#!/usr/bin/env python3
"""批量修复汉书卷 001–010：补三字段 + 重推断事略/典制年代。"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

SKILL = Path(__file__).resolve().parent
if str(SKILL) not in sys.path:
    sys.path.insert(0, str(SKILL))

from detail_coords import DETAIL_FIELDS, fill_all_detail_coords
from emperor_resolve import build_emperor_info_index, work_id_from_skeleton
from fill_fields import merge_all_entries
from lib_config import paths
from shilue_year_resolve import emperor_accession_year, is_shilue_year_placeholder

_cfg = paths()
HIST = _cfg["annotations"]
BACKUP = HIST / "_backup_hanshu_001_010"
REPORT = _cfg["audit"] / "02汉书_001_010_修复报告.md"

VOLS = tuple(f"{n:03d}" for n in range(1, 11))


def snapshot_years(data: dict) -> dict:
    out = {}
    for e in data.get("entries") or []:
        eid = e.get("史略ID", "")
        out[eid] = (
            e.get("史略分类"),
            e.get("史略开始年"),
            e.get("史略结束年"),
            {f: e.get(f) for f in DETAIL_FIELDS},
        )
    return out


def count_placeholders(data: dict, eidx: dict) -> int:
    n = 0
    for e in data.get("entries") or []:
        if e.get("史略分类") not in ("事略", "典制"):
            continue
        s, en = e.get("史略开始年"), e.get("史略结束年")
        if not isinstance(s, int) or not isinstance(en, int):
            continue
        acc, reign_end, _ = emperor_accession_year(e, eidx)
        if is_shilue_year_placeholder(s, en, acc, reign_end, data=data, entry=e):
            n += 1
    return n


def main() -> int:
    BACKUP.mkdir(parents=True, exist_ok=True)
    eidx = build_emperor_info_index()
    lines = [
        "# 汉书 001–010 批量修复报告",
        "",
        f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## 修复项",
        "- 补全：原文出处、五级细坐标、六级段落锚点",
        "- 事略/典制：清除卷级占位年，据原文纪年重推断",
        "",
        "## 分卷结果",
        "",
        "| 卷 | 条目数 | 修复前占位年 | 修复后占位年 | 三字段 |",
        "|---|---:|---:|---:|---|",
    ]

    total_before = total_after = 0
    changed_years: list[str] = []

    for vol in VOLS:
        paths = sorted(HIST.glob(f"02汉书_{vol}_*_skeleton.json"))
        if not paths:
            lines.append(f"| {vol} | — | — | — | 文件不存在 |")
            continue
        path = paths[0]
        with open(path, encoding="utf-8") as f:
            before = json.load(f)
        before_snap = snapshot_years(before)
        before_ph = count_placeholders(before, eidx)

        # 备份
        bak = BACKUP / path.name
        if not bak.exists():
            shutil.copy2(path, bak)

        data = json.loads(json.dumps(before))
        work_id = work_id_from_skeleton(data, str(path))
        merge_all_entries(
            data.get("entries") or [],
            data=data,
            json_path=str(path),
            emperor_index=eidx,
            work_id=work_id,
        )
        fill_all_detail_coords(data, work_id=work_id, json_path=str(path))

        after_ph = count_placeholders(data, eidx)
        total_before += before_ph
        total_after += after_ph

        missing_detail = sum(
            1
            for e in data.get("entries") or []
            if any(not (e.get(f) or "").strip() for f in DETAIL_FIELDS)
        )
        detail_ok = "✅" if missing_detail == 0 else f"缺 {missing_detail}"

        lines.append(
            f"| {vol} | {len(data.get('entries') or [])} | {before_ph} | {after_ph} | {detail_ok} |"
        )

        for e in data.get("entries") or []:
            eid = e.get("史略ID", "")
            if eid not in before_snap:
                continue
            old = before_snap[eid]
            new = (
                e.get("史略分类"),
                e.get("史略开始年"),
                e.get("史略结束年"),
                {f: e.get(f) for f in DETAIL_FIELDS},
            )
            if old[1:3] != new[1:3] and e.get("史略分类") in ("事略", "典制"):
                changed_years.append(
                    f"- `{eid}` {e.get('史略名称')}：{old[1]}～{old[2]} → {new[1]}～{new[2]}"
                )

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")

    lines.extend(
        [
            "",
            f"**合计占位年**：修复前 {total_before} → 修复后 {total_after}",
            "",
            "## 年代变更明细（事略/典制）",
            "",
        ]
    )
    if changed_years:
        lines.extend(changed_years[:80])
        if len(changed_years) > 80:
            lines.append(f"\n… 另有 {len(changed_years) - 80} 条未列出")
    else:
        lines.append("（无年代变更）")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(REPORT.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
