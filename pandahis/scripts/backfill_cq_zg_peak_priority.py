#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""补全春秋/战国线上索引缺失的峰值年与优先级。

硬约束：
  1. 仅处理「优先级缺失」或「峰值年缺失」的条目；已有字段不重跑。
  2. 同名（或已知别名）已有完整条目时，对齐字段，不二次 LLM。
  3. 数据源仅限：线上索引 / V2 索引 / 06朝代知识补全 / 01历史坐标；
     禁止读取 V1（03索引标注条目、04史料翻译、史略索引_01至02*）。

用法：
  python3 scripts/backfill_cq_zg_peak_priority.py --dry-run
  python3 scripts/backfill_cq_zg_peak_priority.py
  python3 scripts/backfill_cq_zg_peak_priority.py --no-llm   # 仅去重对齐+年份兜底
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
ONLINE = DATA / "12线上史略索引" / "史略索引_online.json"
V2_INDEX = DATA / "10新标注条目" / "史略索引_史记汉书.json"
CQ_PERSON_06 = DATA / "06朝代知识补全" / "索引条目" / "春秋_人物.json"
EMPEROR_JSON = DATA / "01历史坐标数据" / "帝王.json"
REPORT_DIR = DATA / "05工作流中间产物" / "春秋战国补全"
FORBIDDEN_V1_GLOBS = (
    "03索引标注条目",
    "04史料翻译",
    "史略索引_01至02",
)

TOOLS = ROOT / "tools" / "openclaw-historiography"
ANNOTATE = TOOLS / "historiography-annotate"
DK_SCRIPTS = TOOLS / "historiography-dynasty-knowledge" / "scripts"

for _p in (str(TOOLS), str(ANNOTATE), str(DK_SCRIPTS), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_env = TOOLS / ".env"
if _env.is_file():
    for line in _env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip())

# 别名：缺口名 → 已有完整条目名（仅用于对齐，不读 V1）
NAME_ALIASES: dict[str, str] = {
    "魏公子无忌": "魏无忌",
}

TARGET_DYNASTIES = frozenset({"春秋", "战国"})
PLACEHOLDER_YEARS = frozenset({-2000, -2600})

PEAK_KEYS = ("峰值年", "峰值原因", "峰值类型", "峰值置信度")
PRI_KEYS = ("优先级", "优先级判定理由")


def _log(msg: str) -> None:
    print(msg, flush=True)


def _assert_no_v1_paths() -> None:
    """运行期自检：脚本未引入 V1 路径常量。"""
    for name, val in list(globals().items()):
        if not isinstance(val, Path):
            continue
        s = str(val)
        for bad in FORBIDDEN_V1_GLOBS:
            if bad in s:
                raise SystemExit(f"禁止触及 V1 路径: {name}={s}")


def atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def load_list_or_entries(path: Path) -> tuple[Any, list[dict], str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return raw, raw, "list"
    if isinstance(raw, dict) and isinstance(raw.get("entries"), list):
        return raw, raw["entries"], "entries"
    raise SystemExit(f"不支持的索引格式: {path}")


def save_list_or_entries(path: Path, container: Any, entries: list[dict], mode: str) -> None:
    if mode == "list":
        atomic_write_json(path, entries)
        return
    container["entries"] = entries
    atomic_write_json(path, container)


def has_priority(entry: dict) -> bool:
    return str(entry.get("优先级") or "").strip() in {"P0", "P1", "P2", "P3"}


def has_peak(entry: dict) -> bool:
    return entry.get("峰值年") is not None


def is_placeholder_year(entry: dict) -> bool:
    sy = entry.get("史略开始年")
    ey = entry.get("史略结束年")
    return sy in PLACEHOLDER_YEARS or ey in PLACEHOLDER_YEARS


def clear_placeholder_years(entry: dict) -> bool:
    changed = False
    for key in ("史略开始年", "史略结束年"):
        if entry.get(key) in PLACEHOLDER_YEARS:
            entry[key] = None
            changed = True
    if changed:
        af = dict(entry.get("_auto_filled") or {})
        af.pop("_年兜底级别", None)
        af.pop("_年兜底依据", None)
        entry["_auto_filled"] = af
    return changed


def merge_auto(dst: dict, src: dict, keys: tuple[str, ...]) -> None:
    src_af = src.get("_auto_filled") or {}
    if not isinstance(src_af, dict):
        return
    dst_af = dict(dst.get("_auto_filled") or {})
    for k in keys:
        if k in src_af:
            dst_af[k] = src_af[k]
    dst["_auto_filled"] = dst_af


def copy_enrichment(dst: dict, src: dict, *, note: str) -> dict[str, str]:
    """从已齐条目对齐峰值/优先级；返回实际写入的字段。"""
    wrote: dict[str, str] = {}
    if not has_peak(dst) and has_peak(src):
        for k in PEAK_KEYS:
            if k in src:
                dst[k] = deepcopy(src[k])
        merge_auto(
            dst,
            src,
            ("_峰值指纹", "_峰值兜底级别", "_峰值LLM依据", "_峰值待审"),
        )
        af = dict(dst.get("_auto_filled") or {})
        af["_峰值对齐来源"] = src.get("史略ID")
        af["_峰值对齐说明"] = note
        dst["_auto_filled"] = af
        wrote["peak"] = str(src.get("史略ID"))
    if not has_priority(dst) and has_priority(src):
        for k in PRI_KEYS:
            if k in src:
                dst[k] = deepcopy(src[k])
        # 理由点名目标名
        name = str(dst.get("史略名称") or "").strip()
        reason = str(dst.get("优先级判定理由") or "")
        if name and name not in reason:
            dst["优先级判定理由"] = f"{name}：对齐自{src.get('史略名称')}（{src.get('史略ID')}）—" + reason
        merge_auto(
            dst,
            src,
            ("_优先级指纹", "_优先级朝代全局", "_优先级待审"),
        )
        af = dict(dst.get("_auto_filled") or {})
        af["_优先级对齐来源"] = src.get("史略ID")
        af["_优先级对齐说明"] = note
        af["_优先级朝代全局"] = True
        dst["_auto_filled"] = af
        wrote["priority"] = str(src.get("史略ID"))
    return wrote


def find_complete_sibling(
    entry: dict,
    by_name: dict[str, list[dict]],
) -> dict | None:
    name = str(entry.get("史略名称") or "").strip()
    eid = str(entry.get("史略ID") or "")
    candidates: list[dict] = []
    for n in (name, NAME_ALIASES.get(name, "")):
        if not n:
            continue
        for other in by_name.get(n, []):
            if other.get("史略ID") == eid:
                continue
            if has_priority(other) and has_peak(other):
                candidates.append(other)
    if not candidates:
        return None
    # 优先同朝、史料提取
    candidates.sort(
        key=lambda e: (
            0 if e.get("二级朝代坐标") == entry.get("二级朝代坐标") else 1,
            0 if e.get("史略来源") == "史料提取" else 1,
            str(e.get("史略ID")),
        )
    )
    return candidates[0]


def collect_gaps(entries: list[dict]) -> list[dict]:
    gaps = []
    for e in entries:
        if e.get("二级朝代坐标") not in TARGET_DYNASTIES:
            continue
        if has_priority(e) and has_peak(e) and not is_placeholder_year(e):
            continue
        if not has_priority(e) or not has_peak(e) or is_placeholder_year(e):
            gaps.append(e)
    return gaps


def repair_years(gaps: list[dict], emperors: list[dict]) -> list[str]:
    from dynasty_supplement_lib import apply_person_years_for_entry  # noqa: WPS433

    notes: list[str] = []
    for e in gaps:
        if clear_placeholder_years(e):
            notes.append(f"{e.get('史略ID')} 清除占位年 -2000/-2600")
        if e.get("史略开始年") is not None and e.get("史略结束年") is not None:
            continue
        fixed, changes = apply_person_years_for_entry(e, emperors)
        e.clear()
        e.update(fixed)
        notes.extend(changes)
    return notes


def patch_source_index(
    path: Path,
    updated_by_id: dict[str, dict],
    *,
    field_keys: tuple[str, ...],
) -> int:
    if not path.is_file():
        return 0
    container, entries, mode = load_list_or_entries(path)
    n = 0
    for i, e in enumerate(entries):
        eid = str(e.get("史略ID") or "")
        src = updated_by_id.get(eid)
        if not src:
            continue
        changed = False
        for k in field_keys:
            if k == "_auto_filled":
                continue
            if src.get(k) != e.get(k):
                e[k] = deepcopy(src.get(k))
                changed = True
        # merge auto meta
        src_af = src.get("_auto_filled") or {}
        if isinstance(src_af, dict) and src_af:
            af = dict(e.get("_auto_filled") or {})
            af.update(src_af)
            e["_auto_filled"] = af
            changed = True
        if changed:
            entries[i] = e
            n += 1
    if n:
        save_list_or_entries(path, container, entries, mode)
    return n


def main() -> int:
    parser = argparse.ArgumentParser(description="春秋/战国峰值与优先级缺口补全")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-llm", action="store_true", help="跳过 LLM，仅对齐与年份兜底")
    parser.add_argument("--online", type=Path, default=ONLINE)
    args = parser.parse_args()

    _assert_no_v1_paths()
    if not args.online.is_file():
        raise SystemExit(f"缺少线上索引: {args.online}")

    online_container, online, online_mode = load_list_or_entries(args.online)
    by_id = {str(e["史略ID"]): e for e in online}
    by_name: dict[str, list[dict]] = {}
    for e in online:
        by_name.setdefault(str(e.get("史略名称") or ""), []).append(e)

    gaps = collect_gaps(online)
    _log(f"目标朝缺口（缺P/缺峰值/占位年）: {len(gaps)}")
    _log(
        "  春秋 "
        + str(sum(1 for e in gaps if e.get("二级朝代坐标") == "春秋"))
        + " / 战国 "
        + str(sum(1 for e in gaps if e.get("二级朝代坐标") == "战国"))
    )

    report: dict[str, Any] = {
        "schema": "cq-zg-peak-priority-backfill/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "online": str(args.online),
            "v2": str(V2_INDEX),
            "cq_person_06": str(CQ_PERSON_06),
            "emperors": str(EMPEROR_JSON),
            "forbidden": list(FORBIDDEN_V1_GLOBS),
        },
        "gap_ids_before": [e["史略ID"] for e in gaps],
        "aligned_from_sibling": [],
        "year_repairs": [],
        "llm_peak_stats": {},
        "llm_priority_stats": {},
        "gap_ids_after": [],
        "source_patches": {},
    }

    # 1) 同名/别名已齐 → 对齐，禁止重复 LLM
    for e in gaps:
        sib = find_complete_sibling(e, by_name)
        if not sib:
            continue
        note = f"同实体已有完整条目 {sib.get('史略ID')}（{sib.get('史略名称')}），对齐避免重复补全"
        wrote = copy_enrichment(e, sib, note=note)
        if wrote:
            report["aligned_from_sibling"].append(
                {
                    "target": e.get("史略ID"),
                    "target_name": e.get("史略名称"),
                    "source": sib.get("史略ID"),
                    "source_name": sib.get("史略名称"),
                    "fields": wrote,
                }
            )
            _log(f"  ↪ 对齐 {e.get('史略ID')} {e.get('史略名称')} ← {sib.get('史略ID')} {wrote}")

    # 2) 郑定公双缺口：若稍后 LLM 填好 extract，再对齐到补全条
    # （先年份修复）

    emperors = json.loads(EMPEROR_JSON.read_text(encoding="utf-8"))
    year_notes = repair_years(gaps, emperors)
    report["year_repairs"] = year_notes
    _log(f"年份修复: {len(year_notes)} 条记录")

    # 仍缺峰值 / 优先级的子集
    still_peak = [e for e in gaps if not has_peak(e)]
    still_pri = [e for e in gaps if not has_priority(e)]
    _log(f"对齐+年份后仍缺峰值: {len(still_peak)}；仍缺优先级: {len(still_pri)}")

    if args.dry_run:
        report["dry_run"] = True
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        out = REPORT_DIR / f"dry_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        atomic_write_json(out, report)
        _log(f"dry-run 报告: {out}")
        return 0

    if not args.no_llm:
        from peak_year import annotate as annotate_peak  # noqa: WPS433
        from dynasty_priority import annotate as annotate_priority  # noqa: WPS433

        # 严格子集：只把「仍缺峰值/仍缺优先级」的条目交给 LLM。
        # 注意：dynasty_priority.is_fresh 要求 _优先级朝代全局+指纹，
        # 已有 P 但缺元数据的条目若整朝送入会被误重判，故绝不能整朝传入。
        peak_targets = [e for e in gaps if not has_peak(e)]
        pri_targets = [e for e in gaps if not has_priority(e)]

        def _ckpt() -> None:
            save_list_or_entries(args.online, online_container, online, online_mode)

        _log(f"🤖 峰值年 LLM（仅 {len(peak_targets)} 条无峰值）…")
        peak_stats = annotate_peak(
            peak_targets,
            use_llm=True,
            force=False,
            on_batch_done=_ckpt,
        )
        report["llm_peak_stats"] = peak_stats
        _log(f"  peak stats: {peak_stats}")
        _ckpt()

        # 郑定公：extract → 补全条再对齐一次
        extract_ding = by_id.get("GLBL_01120")
        supp_ding = by_id.get("GLBL_01031")
        if extract_ding and supp_ding and has_peak(extract_ding) and has_priority(extract_ding):
            wrote = copy_enrichment(
                supp_ding,
                extract_ding,
                note="郑定公双挂：以史料提取条为准对齐补全条",
            )
            if wrote:
                report["aligned_from_sibling"].append(
                    {
                        "target": "GLBL_01031",
                        "source": "GLBL_01120",
                        "fields": wrote,
                        "note": "郑定公双挂对齐",
                    }
                )

        # 对齐后刷新仍缺优先级列表
        pri_targets = [e for e in gaps if not has_priority(e)]
        _log(f"🤖 优先级 LLM（仅 {len(pri_targets)} 条无优先级）…")
        for did, dname in (
            ("CD_HX_CHUNQIU", "春秋"),
            ("CD_HX_ZHANGUO", "战国"),
        ):
            subset = [e for e in pri_targets if e.get("朝代ID") == did]
            if not subset:
                report["llm_priority_stats"][dname] = {"entries": 0, "skipped": "none_missing"}
                continue
            stats = annotate_priority(
                subset,
                use_llm=True,
                force=False,
                dynasty_id=did,
                on_batch_done=_ckpt,
            )
            report["llm_priority_stats"][dname] = stats
            _log(f"  {dname} priority stats: {stats}")
        _ckpt()
    else:
        save_list_or_entries(args.online, online_container, online, online_mode)

    # 回写 SSOT：06 春秋人物 + V2（不碰 V1）
    updated = {str(e["史略ID"]): e for e in gaps}
    # 也包含可能被 LLM 改到的同朝条目？仅回写原本缺口 ID，避免误扩
    field_keys = (
        "史略开始年",
        "史略结束年",
        *PEAK_KEYS,
        *PRI_KEYS,
        "_auto_filled",
    )
    n06 = patch_source_index(CQ_PERSON_06, updated, field_keys=field_keys)
    n_v2 = patch_source_index(V2_INDEX, updated, field_keys=field_keys)
    report["source_patches"] = {"春秋_人物_06": n06, "v2_index": n_v2}
    _log(f"回写 06春秋人物: {n06}；V2索引: {n_v2}")

    after = collect_gaps(online)
    # 占位年已清且有 P+peak 的不算缺口
    after = [
        e
        for e in after
        if (not has_priority(e)) or (not has_peak(e)) or is_placeholder_year(e)
    ]
    report["gap_ids_after"] = [
        {
            "id": e["史略ID"],
            "name": e.get("史略名称"),
            "dynasty": e.get("二级朝代坐标"),
            "miss_priority": not has_priority(e),
            "miss_peak": not has_peak(e),
            "years": [e.get("史略开始年"), e.get("史略结束年")],
        }
        for e in after
    ]
    _log(f"完成后仍缺口: {len(after)}")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORT_DIR / f"backfill_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    atomic_write_json(out, report)
    _log(f"✅ 报告: {out}")
    return 0 if not after else 0  # 残留交报告，不失败退出


if __name__ == "__main__":
    raise SystemExit(main())
