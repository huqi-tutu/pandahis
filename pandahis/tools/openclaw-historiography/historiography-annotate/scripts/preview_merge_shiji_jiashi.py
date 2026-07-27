#!/usr/bin/env python3
"""世家卷 031–060 增量 merge 预判（保留既有 GLBL ID，不全量重排）。

用法:
  python3 preview_merge_shiji_jiashi.py
  python3 preview_merge_shiji_jiashi.py --json
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

_ANNOTATE_DIR = Path(__file__).resolve().parents[1]
if str(_ANNOTATE_DIR) not in sys.path:
    sys.path.insert(0, str(_ANNOTATE_DIR))

from merge_global_entries import (  # noqa: E402
    NAME_ALIASES,
    _canonical_name,
    _load_zongqi_aliases,
    _parse_skeleton_path,
)
from source_thickness import count_source_chars, should_defer_glbl  # noqa: E402

JIASHI_VOLS = {f"{i:03d}" for i in range(31, 61)}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _load_jiashi_skeleton_sources(data_root: Path) -> List[dict]:
    out: List[dict] = []
    for fp in sorted(data_root.glob("01史记_*_skeleton.json")):
        work, vol, _ = _parse_skeleton_path(fp)
        if vol not in JIASHI_VOLS:
            continue
        data = json.loads(fp.read_text(encoding="utf-8"))
        meta = {
            "volume": data.get("volume", ""),
            "source_file": data.get("source_file", ""),
            "protagonist_count": data.get("protagonist_count") or len(data.get("entries") or []),
        }
        for entry in data.get("entries") or []:
            name = (entry.get("史略名称") or "").strip()
            if not name:
                continue
            cat = entry.get("史略分类", "")
            if isinstance(cat, list):
                cat = "/".join(cat)
            eid = entry.get("史略ID", "")
            out.append(
                {
                    "work": work,
                    "vol": vol,
                    "vol_name": meta["volume"],
                    "name": name,
                    "canonical": _canonical_name(name),
                    "cat": str(cat).strip(),
                    "eid": eid,
                    "entry": entry,
                    "meta": meta,
                    "skeleton_path": str(fp),
                }
            )
    return out


def _entry_chars(src: dict, para_cache: dict) -> int:
    work, vol = src["work"], src["vol"]
    key = (work, vol)
    if key not in para_cache:
        idx_path = _repo_root() / "data" / "03索引标注条目" / "段落索引" / f"{work}_{vol}.json"
        idx = json.loads(idx_path.read_text(encoding="utf-8"))
        para_cache[key] = {int(r["id"]): r.get("text", "") for r in idx.get("paragraphs") or []}
    para = para_cache[key]
    total = 0
    for pg in src["entry"].get("paragraphs") or []:
        for pid in range(int(pg["paragraph_from"]), int(pg["paragraph_to"]) + 1):
            total += count_source_chars(para.get(pid, ""))
    return total


def _anchor_str(entry: dict) -> str:
    parts: List[str] = []
    for pg in entry.get("paragraphs") or []:
        a, b = int(pg["paragraph_from"]), int(pg["paragraph_to"])
        parts.append(f"P{a}" if a == b else f"P{a}-P{b}")
    return ",".join(parts)


def _glbl_jiashi_paras(ent: dict) -> List[dict]:
  return [
      p for p in ent.get("paragraphs") or []
      if p.get("work") == "01史记" and str(p.get("vol", "")).zfill(3) in JIASHI_VOLS
  ]


def _glbl_has_hanshu(ent: dict) -> bool:
    return any(p.get("work") == "02汉书" for p in ent.get("paragraphs") or [])


def _find_glbl_match(
    glbl_entries: List[dict],
    canonical: str,
    cat: str,
) -> List[dict]:
    matches = []
    for ent in glbl_entries:
        name = _canonical_name((ent.get("史略名称") or "").strip())
        ec = ent.get("史略分类")
        if isinstance(ec, list):
            ec = "/".join(ec)
        ec = str(ec or "").strip()
        if name == canonical and ec == cat:
            matches.append(ent)
    return matches


def _max_glbl_num(entries: List[dict]) -> int:
    mx = 0
    for ent in entries:
        eid = ent.get("史略ID", "")
        m = re.match(r"GLBL_(\d+)", eid or "")
        if m:
            mx = max(mx, int(m.group(1)))
    return mx


def build_preview() -> dict[str, Any]:
    data_root = _repo_root() / "data" / "03索引标注条目"
    glbl_path = data_root / "史略索引_01至02.json"
    glbl_doc = json.loads(glbl_path.read_text(encoding="utf-8"))
    glbl_entries: List[dict] = glbl_doc.get("entries") or []

    sources = _load_jiashi_skeleton_sources(data_root)
    para_cache: dict = {}

    # group skeleton by merge key (may have multiple blocks same person in 060)
    sk_groups: Dict[Tuple[str, str], List[dict]] = defaultdict(list)
    for s in sources:
        sk_groups[(s["canonical"], s["cat"])].append(s)

    update: List[dict] = []
    create: List[dict] = []
    thin: List[dict] = []
    cross_update: List[dict] = []

    matched_glbl_ids: set[str] = set()

    for (canonical, cat), group in sorted(sk_groups.items(), key=lambda x: (x[0][1], x[0][0])):
        chars = sum(_entry_chars(s, para_cache) for s in group)
        defer, _, reason = should_defer_glbl(group)  # uses merge structure; patch chars
        # should_defer uses count_source_dict_chars which needs full structure - our group items match
        if chars < 100:
            thin.append(
                {
                    "canonical": canonical,
                    "cat": cat,
                    "display_name": group[0]["name"],
                    "chars": chars,
                    "sources": [
                        {"vol": s["vol"], "eid": s["eid"], "anchor": _anchor_str(s["entry"])}
                        for s in group
                    ],
                    "reason": reason or "thin_source_total_under_100",
                }
            )
            continue

        matches = _find_glbl_match(glbl_entries, canonical, cat)
        anchor = ",".join(_anchor_str(s["entry"]) for s in group)
        vols = sorted({s["vol"] for s in group})
        rec = {
            "canonical": canonical,
            "cat": cat,
            "display_name": group[0]["name"],
            "chars": chars,
            "vols": vols,
            "eids": [s["eid"] for s in group],
            "anchor_new": anchor,
            "n_blocks": len(group),
        }

        if matches:
            ent = matches[0]
            gid = ent.get("史略ID", "")
            matched_glbl_ids.add(gid)
            old_j = _glbl_jiashi_paras(ent)
            old_anchor = ",".join(
                f"P{p['paragraph_from']}" if p["paragraph_from"] == p["paragraph_to"]
                else f"P{p['paragraph_from']}-P{p['paragraph_to']}"
                for p in old_j
            )
            rec["glbl_id"] = gid
            rec["anchor_old"] = old_anchor or "—"
            rec["changed"] = old_anchor != anchor
            rec["has_hanshu"] = _glbl_has_hanshu(ent)
            if rec["has_hanshu"]:
                cross_update.append(rec)
            else:
                update.append(rec)
        else:
            create.append(rec)

    # obsolete: GLBL with jiashi paras but not matched
    obsolete: List[dict] = []
    for ent in glbl_entries:
        gid = ent.get("史略ID", "")
        if gid in matched_glbl_ids:
            continue
        jiashi_paras = _glbl_jiashi_paras(ent)
        if not jiashi_paras:
            continue
        name = ent.get("史略名称", "")
        ec = ent.get("史略分类", "")
        key = (_canonical_name(name), str(ec or "").strip())
        if key not in sk_groups:
            obsolete.append(
                {
                    "glbl_id": gid,
                    "name": name,
                    "cat": ec,
                    "anchor_old": ",".join(
                        f"P{p['paragraph_from']}-P{p['paragraph_to']}"
                        if p["paragraph_from"] != p["paragraph_to"]
                        else f"P{p['paragraph_from']}"
                        for p in jiashi_paras
                    ),
                    "has_hanshu": _glbl_has_hanshu(ent),
                    "vols": sorted({str(p.get("vol", "")).zfill(3) for p in jiashi_paras}),
                }
            )

    next_glbl = _max_glbl_num(glbl_entries) + 1

    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "scope": "01史记 卷031–060 世家",
        "skeleton_entries": len(sources),
        "merge_groups": len(sk_groups),
        "summary": {
            "update_same_glbl": len(update),
            "update_cross_hanshu": len(cross_update),
            "create_new_glbl": len(create),
            "thin_deferred": len(thin),
            "obsolete_glbl": len(obsolete),
            "next_glbl_seq": next_glbl,
            "glbl_after_net": len(glbl_entries) - len(obsolete) + len(create),
        },
        "update": sorted(update, key=lambda x: x["glbl_id"]),
        "cross_update": sorted(cross_update, key=lambda x: x["glbl_id"]),
        "create": sorted(create, key=lambda x: (x["cat"], x["canonical"])),
        "thin": sorted(thin, key=lambda x: (x["cat"], x["canonical"])),
        "obsolete": sorted(obsolete, key=lambda x: x["glbl_id"]),
    }


def _md_table(headers: List[str], rows: List[List[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def render_markdown(p: dict[str, Any]) -> str:
    s = p["summary"]
    lines = [
        "# 史记世家卷 031–060 增量 Merge 预判表",
        "",
        f"- 生成时间：{p['generated_at']}",
        f"- 范围：{p['scope']}",
        f"- skeleton 条目：{p['skeleton_entries']}（合并键分组：{p['merge_groups']}）",
        "",
        "## 一、总览",
        "",
        _md_table(
            ["动作", "条数", "说明"],
            [
                ["更新 GLBL（仅史记侧）", str(s["update_same_glbl"]), "保留原 GLBL ID，刷新段落锚点"],
                ["更新 GLBL（含汉书补充）", str(s["update_cross_hanshu"]), "保留 ID + 汉书段落不动，只改史记母本段"],
                ["新增 GLBL", str(s["create_new_glbl"]), f"从 GLBL_{s['next_glbl_seq']:05d} 起分配新号"],
                ["厚度门拒收", str(s["thin_deferred"]), "写入薄标注注册表，不产 GLBL"],
                ["淘汰旧 GLBL", str(s["obsolete_glbl"]), "旧索引有、新 skeleton 无（或归一后不匹配）"],
                ["净增 GLBL", str(s["create_new_glbl"] - s["obsolete_glbl"]), f"预估全局 {p.get('_current_total', '—')} → {s['glbl_after_net']}"],
            ],
        ),
        "",
        "> **禁止**全量 `merge_global_entries.py`；执行时须保留既有 GLBL ID（见合并规则 §九）。",
        "",
    ]

    def section(title: str, items: List[dict], cols: List[Tuple[str, str]], limit: int = 999):
        lines.append(f"## {title}")
        lines.append("")
        lines.append(f"共 **{len(items)}** 条。")
        lines.append("")
        if not items:
            lines.append("（无）")
            lines.append("")
            return
        headers = [c[1] for c in cols]
        rows = []
        for it in items[:limit]:
            rows.append([str(it.get(c[0], "")) for c in cols])
        lines.append(_md_table(headers, rows))
        if len(items) > limit:
            lines.append("")
            lines.append(f"… 另有 {len(items) - limit} 条，见 JSON 附件。")
        lines.append("")

    section(
        "二、更新（保留 GLBL · 仅史记）",
        p["update"],
        [
            ("glbl_id", "GLBL"),
            ("display_name", "名称"),
            ("cat", "分类"),
            ("vols", "卷"),
            ("anchor_old", "旧锚点"),
            ("anchor_new", "新锚点"),
            ("chars", "字数"),
        ],
        limit=50,
    )

    section(
        "三、更新（跨著作 · 史记母本 + 汉书补充）",
        p["cross_update"],
        [
            ("glbl_id", "GLBL"),
            ("display_name", "名称"),
            ("cat", "分类"),
            ("anchor_old", "旧史记锚点"),
            ("anchor_new", "新史记锚点"),
            ("chars", "史记字数"),
        ],
    )

    section(
        "四、新增 GLBL",
        p["create"],
        [
            ("display_name", "名称"),
            ("cat", "分类"),
            ("vols", "卷"),
            ("anchor_new", "锚点"),
            ("chars", "字数"),
        ],
        limit=60,
    )

    section(
        "五、厚度门拒收（<100 字）",
        [
            {
                **t,
                "vol_eids": "; ".join(
                    f"{s['vol']}·{s['anchor']}" for s in t.get("sources", [])
                ),
            }
            for t in p["thin"]
        ],
        [
            ("display_name", "名称"),
            ("cat", "分类"),
            ("chars", "字数"),
            ("vol_eids", "卷·锚点"),
        ],
        limit=50,
    )

    section(
        "六、淘汰旧 GLBL",
        p["obsolete"],
        [
            ("glbl_id", "GLBL"),
            ("name", "名称"),
            ("cat", "分类"),
            ("vols", "卷"),
            ("anchor_old", "旧锚点"),
            ("has_hanshu", "含汉书"),
        ],
    )

    return "\n".join(lines)


def main() -> int:
    preview = build_preview()
    data_root = _repo_root() / "data" / "03索引标注条目"
    glbl_path = data_root / "史略索引_01至02.json"
    glbl_doc = json.loads(glbl_path.read_text(encoding="utf-8"))
    preview["_current_total"] = len(glbl_doc.get("entries") or [])
    preview["summary"]["glbl_after_net"] = (
        preview["_current_total"]
        - preview["summary"]["obsolete_glbl"]
        + preview["summary"]["create_new_glbl"]
    )

    out_dir = data_root / "合并预判"
    out_dir.mkdir(exist_ok=True)
    md_path = out_dir / "史记世家031-060增量merge预判表.md"
    json_path = out_dir / "史记世家031-060增量merge预判.json"

    md_path.write_text(render_markdown(preview) + "\n", encoding="utf-8")
    json_path.write_text(json.dumps(preview, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if "--json" in sys.argv:
        print(json.dumps(preview["summary"], ensure_ascii=False, indent=2))
    else:
        print(render_markdown(preview))
        print(f"\n✅ 已写入:\n  {md_path}\n  {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
