#!/usr/bin/env python3
"""Generate cross-work main/supplementary preview table for 01史记 × 02汉书."""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

GROUP_KEYWORDS = ("儒林", "酷吏", "游侠", "货殖", "佞幸", "循吏")


def _repo_root() -> Path:
    # .../pandahis/pandahis/tools/openclaw-historiography/historiography-annotate/scripts/this_file
    return Path(__file__).resolve().parents[4]


def _load_entries(data_root: Path, glob: str) -> list[dict]:
    recs: list[dict] = []
    for fp in sorted(data_root.glob(glob)):
        m = re.match(r"(\d{2}[^_]+)_(\d{3})_(.+?)_skeleton\.json", fp.name)
        if not m:
            continue
        work_code, vol, title = m.groups()
        work = "01史记" if work_code.startswith("01") else "02汉书"
        work_ord = int(work_code[:2])
        data = json.loads(fp.read_text(encoding="utf-8"))
        vol_name = data.get("volume") or title
        pc = data.get("protagonist_count") or len(data.get("entries") or [])
        for e in data.get("entries") or []:
            name = (e.get("史略名称") or "").strip()
            if not name:
                continue
            cat = e.get("史略分类")
            if isinstance(cat, list):
                cat = "/".join(cat)
            recs.append(
                {
                    "work": work,
                    "work_ord": work_ord,
                    "vol": vol,
                    "vol_name": vol_name,
                    "name": name,
                    "cat": str(cat).strip(),
                    "eid": e.get("史略ID", ""),
                    "protagonist_count": pc,
                }
            )
    return recs


def _vol_type(rec: dict) -> tuple[str, int]:
    vn = rec["vol_name"]
    if any(k in vn for k in GROUP_KEYWORDS):
        return "群像传", 2
    if "纪" in vn and "传" not in vn:
        return "纪", 4
    if "列传" in vn or "世家" in vn:
        if rec["protagonist_count"] == 1:
            return "专传", 4
        return "合传", 3
    if "传" in vn:
        if rec["protagonist_count"] == 1:
            return "专传", 4
        return "合传", 3
    return "合传", 3


def _split_key(rec: dict) -> tuple[str, str]:
    base = re.sub(r"(上|下|之中|之下|之上)$", "", rec["vol_name"])
    base = re.sub(r"第[一二三四五六七八九十百千]+$", "", base)
    return rec["work"], base.strip()


def _fmt_sources(recs: list[dict]) -> str:
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in recs:
        groups[_split_key(r)].append(r)
    parts: list[str] = []
    for _, gl in sorted(groups.items()):
        vols = "+".join(sorted({x["vol"] for x in gl}))
        vt, _ = _vol_type(gl[0])
        w = "史记" if gl[0]["work"].startswith("01") else "汉书"
        parts.append(f"{w}{vols}({vt})")
    return "; ".join(parts)


def generate() -> Path:
    data_root = _repo_root() / "data" / "03索引标注条目"
    out_dir = data_root / "合并预判"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "01至02跨著作主补预判表.md"

    all_recs = _load_entries(data_root, "01史记_*") + _load_entries(data_root, "02汉书_*")
    by_name: dict[str, list[dict]] = defaultdict(list)
    for r in all_recs:
        by_name[r["name"]].append(r)

    cross = {n: rs for n, rs in by_name.items() if len({x["work"] for x in rs}) > 1}
    notes_map = {
        "吕太后": "分类宗戚；纪体先著",
        "张耳": "分类文臣",
        "陈馀": "分类文臣",
        "卢绾": "分类武将",
        "李延年": "分类宦官",
        "魏豹": "分类武将",
        "田儋": "分类武将",
        "韩王信": "分类武将",
        "贾谊": "061已为贾山；补=史记084",
    }

    rows: list[tuple[str, str, str, str, str]] = []
    for name in sorted(cross):
        rs = cross[name]
        scored = [(_vol_type(r)[1], r["work_ord"], r["vol"], r) for r in rs]
        scored.sort(key=lambda x: (-x[0], x[1], x[2]))
        main = scored[0][3]
        mvt, _ = _vol_type(main)
        supp = [s[3] for s in scored[1:]]
        rows.append(
            (
                name,
                "/".join(sorted({r["cat"] for r in rs})),
                f"{main['work']} {main['vol']} {main['vol_name'][:16]}（{mvt}）",
                _fmt_sources(supp) if supp else "—",
                notes_map.get(name, ""),
            )
        )

    lines = [
        "# 01史记 × 02汉书 跨著作主补预判表\n",
        "> 规则 SSOT：`historiography-annotate/reference/标注索引条目合并规则.md`\n",
        f"> 跨著作主题 **{len(rows)}** 个\n",
        "| 史略名称 | 分类 | 主要史料 | 补充史料 | 备注 |",
        "|---------|------|---------|---------|------|",
    ]
    for row in rows:
        lines.append(f"| {' | '.join(row)} |")

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


if __name__ == "__main__":
    path = generate()
    print(f"wrote {path}")
