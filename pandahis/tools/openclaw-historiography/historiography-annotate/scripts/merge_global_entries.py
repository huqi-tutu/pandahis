#!/usr/bin/env python3
"""合并 01史记 + 02汉书 skeleton 条目 → 全局史略索引（GLBL_*）。

规则 SSOT：reference/标注索引条目合并规则.md

⚠️ 全量 merge 会按排序重新编号全部 GLBL ID，禁止用于已发布索引的修复。
   已发布数据须用 repair_*.py 外科手术式修复，见合并规则 §九。

用法:
  python3 merge_global_entries.py
  python3 merge_global_entries.py --dry-run
"""

from __future__ import annotations

import argparse
import copy
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

GROUP_KEYWORDS = ("儒林", "酷吏", "游侠", "货殖", "佞幸", "循吏")

# 硬编码异名归一（merge_key）；宗戚异名见 _load_zongqi_aliases()
NAME_ALIASES: Dict[str, str] = {
    "项籍": "项羽",
    "陈涉": "陈胜",
    "蜀卓氏": "卓氏",
    "滕公（夏侯婴）": "夏侯婴",
}

COPY_FIELDS = [
    "史略名称",
    "史略简介",
    "原文字句",
    "史略分类",
    "主要史料出处",
    "优先级",
    "优先级判定理由",
    "史略开始年",
    "史略结束年",
    "峰值年",
    "峰值原因",
    "峰值类型",
    "峰值置信度",
    "人物标签",
    "人物标签判定理由",
    "人物标签置信度",
    "一级文明坐标",
    "二级朝代坐标",
    "三级政权坐标",
    "四级帝王坐标",
    "文明ID",
    "朝代ID",
    "政权ID",
    "帝王ID",
    "宗戚ID",
    "五级细坐标",
    "六级段落锚点",
    "原文出处",
]

# 从 skeleton _auto_filled 提取考订子键 → GLBL 顶层「考订依据」（与 fill_fields --finalize 保留集一致）
AUDIT_FROM_AUTO: Dict[str, str] = {
    "_年LLM依据": "年",
    "_坐标主轴说明": "坐标主轴",
    "年规则": "年规则",
    "年规则备注": "年规则备注",
}


def _extract_kaoding_yiju(main_entry: dict) -> Dict[str, str] | None:
    """母本 skeleton 的 _auto_filled 只提取人读考订说明，不拷贝过程/重复字段。"""
    auto = main_entry.get("_auto_filled") or {}
    if not auto:
        return None
    out: Dict[str, str] = {}
    for src_key, dst_key in AUDIT_FROM_AUTO.items():
        val = auto.get(src_key)
        if val not in (None, ""):
            out[dst_key] = str(val).strip()
    return out or None


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _load_zongqi_aliases() -> Dict[str, str]:
    """宗戚原名/全称 → 宗戚名称；SSOT: reference/宗戚别名.json + data/宗戚.json。"""
    out: Dict[str, str] = {}
    alias_path = Path(__file__).resolve().parents[1] / "reference" / "宗戚别名.json"
    if alias_path.is_file():
        cfg = json.loads(alias_path.read_text(encoding="utf-8"))
        for alias, canonical in (cfg.get("global") or {}).items():
            a, c = str(alias).strip(), str(canonical).strip()
            if a and c:
                out[a] = c
    zj_path = _repo_root() / "data" / "01历史坐标数据" / "宗戚.json"
    if zj_path.is_file():
        for row in json.loads(zj_path.read_text(encoding="utf-8")):
            canon = str(row.get("宗戚名称") or "").strip()
            given = str(row.get("宗戚原名") or "").strip()
            if canon:
                out.setdefault(canon, canon)
            if given and canon:
                out.setdefault(given, canon)
    return out


_ZONGQI_ALIASES: Dict[str, str] | None = None


def _zongqi_alias_map() -> Dict[str, str]:
    global _ZONGQI_ALIASES
    if _ZONGQI_ALIASES is None:
        _ZONGQI_ALIASES = _load_zongqi_aliases()
    return _ZONGQI_ALIASES


def _canonical_name(name: str) -> str:
    n = (name or "").strip()
    if not n:
        return n
    if n in NAME_ALIASES:
        return NAME_ALIASES[n]
    return _zongqi_alias_map().get(n, n)


def _parse_skeleton_path(fp: Path) -> Tuple[str, str, str]:
    m = re.match(r"(\d{2}[^_]+)_(\d{3})_(.+?)_skeleton\.json", fp.name)
    if not m:
        raise ValueError(f"无法解析: {fp.name}")
    work_code, vol, title = m.groups()
    work = "01史记" if work_code.startswith("01") else "02汉书"
    return work, vol, title


def _vol_type(rec: dict) -> Tuple[str, int]:
    vn = rec["vol_name"]
    if any(k in vn for k in GROUP_KEYWORDS):
        return "群像传", 2
    if "纪" in vn and "传" not in vn:
        return "纪", 4
    if rec.get("protagonist_count", 99) == 1 and ("传" in vn or "世家" in vn):
        return "专传", 4
    if "传" in vn or "世家" in vn:
        return "合传", 3
    return "合传", 3


def _load_sources(data_root: Path, work_glob: str) -> List[dict]:
    out: List[dict] = []
    for fp in sorted(data_root.glob(work_glob)):
        work, vol, _title = _parse_skeleton_path(fp)
        data = json.loads(fp.read_text(encoding="utf-8"))
        meta = {
            "volume": data.get("volume", ""),
            "source_file": data.get("source_file", fp.name.replace("_skeleton.json", ".txt")),
            "原文路径": data.get("原文路径", ""),
            "protagonist_count": data.get("protagonist_count") or len(data.get("entries") or []),
        }
        for entry in data.get("entries") or []:
            name = (entry.get("史略名称") or "").strip()
            if not name:
                continue
            cat = entry.get("史略分类", "")
            if isinstance(cat, list):
                cat = "/".join(cat)
            out.append(
                {
                    "work": work,
                    "work_ord": 1 if work.startswith("01") else 2,
                    "vol": vol,
                    "vol_name": meta["volume"],
                    "name": name,
                    "canonical": _canonical_name(name),
                    "cat": str(cat).strip(),
                    "eid": entry.get("史略ID", ""),
                    "entry": entry,
                    "meta": meta,
                    "skeleton_path": str(fp),
                }
            )
    return out


def _rank_sources(sources: List[dict]) -> List[dict]:
    scored = []
    for s in sources:
        vt, pri = _vol_type({**s, "vol_name": s["vol_name"], "protagonist_count": s["meta"]["protagonist_count"]})
        scored.append((pri, s["work_ord"], s["vol"], s["eid"], vt, s))
    scored.sort(key=lambda x: (-x[0], x[1], x[2], x[3]))
    return [x[5] for x in scored]


def _paragraph_blocks(src: dict, role: str) -> List[dict]:
    blocks: List[dict] = []
    work, vol = src["work"], src["vol"]
    entry = src["entry"]
    meta = src["meta"]
    paras = entry.get("paragraphs") or []
    if not paras:
        return blocks
    for pg in paras:
        blocks.append(
            {
                "work": work,
                "vol": vol,
                "volume": pg.get("volume") or meta["volume"],
                "paragraph_from": int(pg["paragraph_from"]),
                "paragraph_to": int(pg["paragraph_to"]),
                "source_file": meta["source_file"],
                "index_file": f"段落索引/{work}_{vol}.json",
                "source_entry_id": src["eid"],
                "role": role,
            }
        )
    return blocks


def _merge_anchor(sources: List[dict]) -> str:
    parts: List[str] = []
    for src in sources:
        for pg in src["entry"].get("paragraphs") or []:
            a, b = int(pg["paragraph_from"]), int(pg["paragraph_to"])
            parts.append(f"P{a}" if a == b else f"P{a}-P{b}")
    return ",".join(parts)


def _build_glbl_entry(glbl_id: str, sources: List[dict]) -> dict:
    ranked = _rank_sources(sources)
    main = ranked[0]
    main_entry = main["entry"]

    out: Dict[str, Any] = {"史略ID": glbl_id}
    for field in COPY_FIELDS:
        if field in main_entry and main_entry[field] not in (None, ""):
            out[field] = copy.deepcopy(main_entry[field])

    kaoding = _extract_kaoding_yiju(main_entry)
    if kaoding:
        out["考订依据"] = kaoding

    # 母本字段优先用 main 的 史略名称（非 alias 侧名）
    out["史略名称"] = main_entry.get("史略名称") or main["name"]

    paragraphs: List[dict] = []
    source_entries: List[dict] = []
    merge_sources: List[dict] = []

    for i, src in enumerate(ranked):
        role_entry = "主要" if i == 0 else "补充"
        role_para = "母本" if i == 0 else "补充"
        blocks = _paragraph_blocks(src, role_para)
        paragraphs.extend(blocks)
        source_entries.append({"史略ID": src["eid"], "role": role_entry, "work": src["work"], "vol": src["vol"]})
        merge_sources.append(
            {
                "work": src["work"],
                "史略ID": src["eid"],
                "role": role_entry,
                "主要史料出处": src["entry"].get("主要史料出处", ""),
                "paragraph_count": len(blocks),
            }
        )

    out["paragraphs"] = paragraphs
    out["source_entries"] = source_entries
    out["合并来源"] = merge_sources
    out["来源著作"] = sorted({s["work"] for s in ranked})
    out["来源条目数"] = len(ranked)
    out["段落域数"] = len(paragraphs)
    out["母本著作"] = main["work"]
    out["母本史略ID"] = main["eid"]

    if len(ranked) > 1:
        out["六级段落锚点"] = f"[{_merge_anchor(ranked)}]"

    out["史略来源"] = "史料提取"
    return out


def merge(*, dry_run: bool = False) -> dict:
    data_root = _repo_root() / "data" / "03索引标注条目"
    sources = _load_sources(data_root, "01史记_*") + _load_sources(data_root, "02汉书_*")

    groups: Dict[Tuple[str, str], List[dict]] = defaultdict(list)
    for s in sources:
        key = (s["canonical"], s["cat"])
        groups[key].append(s)

    entries: List[dict] = []
    multi = 0
    cross = 0
    for idx, (_key, group) in enumerate(sorted(groups.items(), key=lambda x: (x[0][1], x[0][0])), start=1):
        glbl_id = f"GLBL_{idx:05d}"
        ent = _build_glbl_entry(glbl_id, group)
        entries.append(ent)
        if len(group) > 1:
            multi += 1
        if len({g["work"] for g in group}) > 1:
            cross += 1

    result = {
        "schema_version": 2,
        "著作": "全局史略索引",
        "source_works": ["01史记", "02汉书"],
        "merge_key": ["史略名称(归一)", "史略分类"],
        "rules_ref": "historiography-annotate/reference/标注索引条目合并规则.md",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_entries": len(entries),
        "merge_stats": {
            "source_skeleton_entries": len(sources),
            "single_source": len(entries) - multi,
            "multi_source": multi,
            "cross_work": cross,
            "paragraph_blocks": sum(e.get("段落域数", 0) for e in entries),
        },
        "entries": entries,
    }

    if not dry_run:
        out_path = data_root / "史略索引_01至02.json"
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        summary_path = data_root / "合并预判" / "01至02合并执行摘要.md"
        summary_path.parent.mkdir(exist_ok=True)
        lines = [
            "# 01史记 × 02汉书 合并执行摘要",
            "",
            f"- 生成时间：{result['generated_at']}",
            f"- 输出：`史略索引_01至02.json`",
            f"- 全局条目：**{len(entries)}**",
            f"- 源 skeleton 条目：{len(sources)}",
            f"- 多源合并：{multi}（跨著作 {cross}）",
            f"- 段落域合计：{result['merge_stats']['paragraph_blocks']}",
            "",
            "## 跨著作合并主题（节选）",
            "",
            "| GLBL | 名称 | 分类 | 母本 | 补充 |",
            "|------|------|------|------|------|",
        ]
        shown = 0
        for e in entries:
            if len(e.get("来源著作", [])) < 2:
                continue
            supp = [x for x in e.get("source_entries", []) if x.get("role") == "补充"]
            supp_s = "; ".join(f"{x['work']}{x['vol']}" for x in supp[:3])
            if len(supp) > 3:
                supp_s += "…"
            lines.append(
                f"| {e['史略ID']} | {e['史略名称']} | {e['史略分类']} | "
                f"{e['母本著作']}{e['source_entries'][0]['vol']} | {supp_s or '—'} |"
            )
            shown += 1
            if shown >= 40:
                lines.append("| … | | | | |")
                break
        summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        result["output_path"] = str(out_path)
        result["summary_path"] = str(summary_path)

    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    stats = merge(dry_run=args.dry_run)
    print(json.dumps({k: v for k, v in stats.items() if k != "entries"}, ensure_ascii=False, indent=2))
    if not args.dry_run:
        print(f"\n✅ 已写入 {stats.get('output_path')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
