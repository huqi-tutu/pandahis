#!/usr/bin/env python3
"""V2 skeleton 合并 → 后汉书×三国志全局索引（增量 GLBL）。

规则 SSOT：reference/标注索引条目合并规则.md §十（03至04）

- 数据源：data/10新标注条目/03后汉书_* + 04三国志_* skeleton
- 产出：data/10新标注条目/史略索引_03至04.json（新 GLBL 数组）
- 扩挂清单：data/10新标注条目/史略索引_03至04_扩挂清单.json
- 不覆盖 data/10新标注条目/史略索引_史记汉书.json
- GLBL 从既有最大编号 +1 起分配

用法:
  python3 merge_v2_03_to_04.py --dry-run
  python3 merge_v2_03_to_04.py
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import sys

_ANNOTATE_DIR = Path(__file__).resolve().parents[1]
if str(_ANNOTATE_DIR) not in sys.path:
    sys.path.insert(0, str(_ANNOTATE_DIR))

from merge_global_entries import (  # noqa: E402
    CROSS_INDEX_EXPAND_TARGETS,
    _build_glbl_entry,
    _load_sources,
    _rank_sources,
    _vol_type,
)
from source_thickness import (  # noqa: E402
    apply_thickness_mub_swap,
    build_deferred_record,
    should_defer_glbl,
)

# 蕃祚跨朝代分条：与史记汉书已合并的西汉条目同名时，后汉/三国仍新建
FANZUO_DYNASTY_SEPARATE_FROM_MASTER: Dict[str, set[str]] = {
    "西南夷": {"西汉", "秦"},  # GLBL_00558 西汉、GLBL_00984 秦 → 后汉东汉另立
    "西羌": {"秦"},  # GLBL_00983 秦朝代补全 → 后汉东汉另立
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _glbl_num(gid: str) -> int:
    m = re.match(r"GLBL_(\d+)", gid or "")
    return int(m.group(1)) if m else 999999


def _infer_dynasty_bucket(work: str, entry: dict) -> str:
    """合并分组用朝代桶（蕃祚跨书双挂时 03+04 内不拆；跨既有索引按朝代拆）。"""
    for field in ("二级朝代坐标", "朝代"):
        val = str(entry.get(field) or "").strip()
        if val:
            return val
    if work.startswith("03"):
        return "东汉"
    if work.startswith("04"):
        return "三国"
    if work.startswith("01") or work.startswith("02"):
        return "西汉"
    return work


def _merge_group_key(s: dict) -> Tuple:
    name = s["canonical"]
    if s["cat"] == "蕃祚":
        # 03×04 内同名蕃祚双挂（东夷、鲜卑）；跨朝代与主索引冲突在产出阶段处理
        return ("蕃祚", name)
    return ("人物", name)


def _load_master_index(path: Path) -> List[dict]:
    if not path.is_file():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _master_names_by_dynasty(master: List[dict]) -> Dict[Tuple[str, str], List[dict]]:
    """(史略名称, 二级朝代坐标) → 条目列表"""
    out: Dict[Tuple[str, str], List[dict]] = defaultdict(list)
    for e in master:
        name = str(e.get("史略名称") or "").strip()
        dynasty = str(e.get("二级朝代坐标") or "").strip()
        if name:
            out[(name, dynasty)].append(e)
    return out


def _should_expand_not_create(name: str, cat: str, dynasty: str, master: List[dict]) -> str | None:
    """若应扩挂既有 GLBL，返回目标 GLBL_ID；否则 None。"""
    if name in CROSS_INDEX_EXPAND_TARGETS:
        return CROSS_INDEX_EXPAND_TARGETS[name]
    if cat != "蕃祚":
        return None
    blocked = FANZUO_DYNASTY_SEPARATE_FROM_MASTER.get(name, set())
    if dynasty in blocked:
        return None
    # 同朝代蕃祚已在主索引（史料提取）→ 扩挂
    for e in master:
        if e.get("史略来源") != "史料提取":
            continue
        if str(e.get("史略名称") or "").strip() != name:
            continue
        md = str(e.get("二级朝代坐标") or "").strip()
        if md == dynasty or (not md and dynasty):
            return str(e.get("史略ID") or "")
    return None


def _build_expand_record(glbl_id: str, group: List[dict], ranked: List[dict]) -> dict:
    return {
        "target_glbl_id": glbl_id,
        "史略名称": group[0]["name"],
        "史略分类": group[0]["cat"],
        "action": "append_source_entries",
        "new_sources": [
            {
                "史略ID": s["eid"],
                "role": "补充",
                "work": s["work"],
                "vol": s["vol"],
                "主要史料出处": (s["entry"].get("主要史料出处") or ""),
            }
            for s in ranked
        ],
        "paragraphs_to_append": [
            block
            for s in ranked
            for block in (
                [
                    {
                        "work": s["work"],
                        "vol": s["vol"],
                        "volume": pg.get("volume") or s["vol_name"],
                        "paragraph_from": int(pg["paragraph_from"]),
                        "paragraph_to": int(pg["paragraph_to"]),
                        "source_file": s["meta"]["source_file"],
                        "index_file": f"段落索引/{s['work']}_{s['vol']}.json",
                        "source_entry_id": s["eid"],
                        "role": "补充",
                    }
                    for pg in (s["entry"].get("paragraphs") or [])
                ]
            )
        ],
    }


def _preview_row(glbl_id: str, ranked: List[dict], group: List[dict]) -> dict:
    main = ranked[0]
    vt_main, _ = _vol_type(
        {
            **main,
            "vol_name": main["vol_name"],
            "protagonist_count": main["meta"]["protagonist_count"],
            "volume_texture": main.get("volume_texture"),
        }
    )
    supp_parts = []
    for s in ranked[1:]:
        vt, _ = _vol_type(
            {
                **s,
                "vol_name": s["vol_name"],
                "protagonist_count": s["meta"]["protagonist_count"],
                "volume_texture": s.get("volume_texture"),
            }
        )
        supp_parts.append(f"{s['work']}{s['vol']}({vt})")
    return {
        "GLBL": glbl_id,
        "名称": group[0]["name"],
        "分类": group[0]["cat"],
        "母本": f"{main['work']}{main['vol']}({vt_main})",
        "补充": "; ".join(supp_parts) if supp_parts else "—",
        "来源数": len(group),
    }


def merge(*, dry_run: bool = False) -> dict:
    root = _repo_root()
    v2_root = root / "data" / "10新标注条目"
    master_path = v2_root / "史略索引_史记汉书.json"
    out_path = v2_root / "史略索引_03至04.json"
    expand_path = v2_root / "史略索引_03至04_扩挂清单.json"
    preview_md = v2_root / "合并预判" / "03至04跨著作主补预判表.md"
    preview_json = v2_root / "合并预判" / "03至04_merge_preview.json"
    thin_path = root / "data" / "05工作流中间产物" / "薄标注待补全" / "registry_v2_03至04.json"

    sources = _load_sources(v2_root, "03后汉书_*") + _load_sources(v2_root, "04三国志_*")
    master = _load_master_index(master_path)
    used_ids = {str(e.get("史略ID")) for e in master if e.get("史略ID")}
    max_num = max((_glbl_num(i) for i in used_ids if i.startswith("GLBL_")), default=0)
    glbl_seq = max_num

    groups: Dict[Tuple, List[dict]] = defaultdict(list)
    for s in sources:
        groups[_merge_group_key(s)].append(s)

    entries: List[dict] = []
    expands: List[dict] = []
    deferred: List[dict] = []
    preview_rows: List[dict] = []
    multi = 0
    cross = 0
    expand_count = 0

    for _key, group in sorted(groups.items(), key=lambda x: (x[1][0]["cat"], x[1][0]["name"])):
        ranked = apply_thickness_mub_swap(_rank_sources(group))
        defer, total_chars, reason = should_defer_glbl(ranked)
        if defer:
            deferred.append(build_deferred_record(ranked, total_chars=total_chars, reason=reason))
            continue

        name = group[0]["name"]
        cat = group[0]["cat"]
        dynasty = _infer_dynasty_bucket(ranked[0]["work"], ranked[0]["entry"])
        expand_target = _should_expand_not_create(name, cat, dynasty, master)
        if expand_target:
            expands.append(_build_expand_record(expand_target, group, ranked))
            expand_count += 1
            preview_rows.append({**_preview_row(expand_target, ranked, group), "动作": "扩挂"})
            continue

        while True:
            glbl_seq += 1
            glbl_id = f"GLBL_{glbl_seq:05d}"
            if glbl_id not in used_ids:
                break
        used_ids.add(glbl_id)

        ent = _build_glbl_entry(glbl_id, group, ranked=ranked)
        entries.append(ent)
        preview_rows.append({**_preview_row(glbl_id, ranked, group), "动作": "新建"})

        if len(group) > 1:
            multi += 1
        if len({g["work"] for g in group}) > 1:
            cross += 1

    entries.sort(key=lambda e: _glbl_num(e.get("史略ID", "")))
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    stats = {
        "output_path": str(out_path),
        "expand_path": str(expand_path),
        "preview_md": str(preview_md),
        "master_index": str(master_path),
        "master_preserved": True,
        "generated_at": generated_at,
        "total_new_entries": len(entries),
        "expand_pending": len(expands),
        "thin_deferred": len(deferred),
        "multi_source": multi,
        "cross_work": cross,
        "source_skeleton_entries": len(sources),
        "glbl_id_range": (
            f"{entries[0]['史略ID']}..{entries[-1]['史略ID']}" if entries else None
        ),
    }

    if not dry_run:
        preview_md.parent.mkdir(parents=True, exist_ok=True)
        thin_path.parent.mkdir(parents=True, exist_ok=True)

        out_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        expand_path.write_text(
            json.dumps(
                {
                    "schema": "index_expand_manifest/v1",
                    "generated_at": generated_at,
                    "target_master": str(master_path),
                    "entry_count": len(expands),
                    "entries": expands,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        thin_path.write_text(
            json.dumps(
                {
                    "schema": "thin_annotation_deferred/v2_03至04",
                    "source": "10新标注条目/03-04",
                    "generated_at": generated_at,
                    "threshold_han_chars": 100,
                    "entry_count": len(deferred),
                    "entries": deferred,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        preview_json.write_text(
            json.dumps({"generated_at": generated_at, "rows": preview_rows}, ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )

        lines = [
            "# 03后汉书 × 04三国志 跨著作主补预判表",
            "",
            f"- 生成时间：{generated_at}",
            f"- 新索引：`史略索引_03至04.json`（**{len(entries)}** 条新 GLBL）",
            f"- 扩挂清单：`史略索引_03至04_扩挂清单.json`（**{len(expands)}** 条待并入史记汉书索引）",
            f"- 厚度门拒收：**{len(deferred)}**",
            f"- 源 skeleton 条目：{len(sources)}",
            f"- 跨著作合并：**{cross}**",
            "",
            "## 新建 GLBL（跨著作节选）",
            "",
            "| GLBL | 名称 | 分类 | 母本 | 补充 |",
            "|------|------|------|------|------|",
        ]
        shown = 0
        for row in preview_rows:
            if row.get("动作") != "新建" or row.get("补充") == "—":
                continue
            lines.append(
                f"| {row['GLBL']} | {row['名称']} | {row['分类']} | {row['母本']} | {row['补充']} |"
            )
            shown += 1
            if shown >= 50:
                lines.append("| … | | | | |")
                break
        lines.extend(
            [
                "",
                "## 扩挂既有 GLBL",
                "",
                "| 目标 GLBL | 名称 | 新增补充源 |",
                "|-----------|------|------------|",
            ]
        )
        for ex in expands:
            supp = "; ".join(f"{s['work']}{s['vol']}" for s in ex.get("new_sources", []))
            lines.append(f"| {ex['target_glbl_id']} | {ex['史略名称']} | {supp} |")
        preview_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return stats


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    stats = merge(dry_run=args.dry_run)
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    if not args.dry_run:
        print(f"\n✅ 已写入 {stats['output_path']}")
        if stats.get("expand_pending"):
            print(f"📎 扩挂清单 {stats['expand_path']}（{stats['expand_pending']} 条）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
