"""政权名解析与 reference JSON 自动对齐（SSOT：政权.json）。"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from coordinate_index import (
    EMPEROR_JSON,
    REGIME_JSON,
    build_dynasty_index_from_json,
    build_regime_index,
    emperor_row_name,
    load_emperor_records,
    make_regime_id,
    resolve_civilization_id,
)
from emperor_resolve import infer_civilization_for_dynasty

SKILL_DIR = Path(__file__).resolve().parent

# 政权.json 三级坐标链（对应标注一/二/三级坐标）
REGIME_COORD_ROW_KEYS = ("文明", "朝代", "政权")


def _regime_coord_chain_complete(row: dict) -> bool:
    for f in REGIME_COORD_ROW_KEYS:
        v = (row.get(f) or "").strip()
        if not v or v == "-":
            return False
    return True


def ensure_regime_coord_chain(
    row: dict,
    hints: Optional[dict] = None,
    *,
    dynasty_index: Optional[Dict[str, dict]] = None,
) -> bool:
    """补全政权行坐标链（文明/朝代/政权）。"""
    from coordinate_index import build_dynasty_index_from_json

    hints = hints or {}
    di = dynasty_index if dynasty_index is not None else build_dynasty_index_from_json()
    changed = False

    regime = (row.get("政权") or "").strip()
    dynasty = (row.get("朝代") or row.get("dynasty_zy") or hints.get("朝代") or "").strip()
    civ = (row.get("文明") or hints.get("文明") or "").strip()

    if not dynasty:
        dynasty = "春秋"
    if not civ:
        civ = infer_civilization_for_dynasty(dynasty, di) or "华夏"

    for key, val in (("朝代", dynasty), ("文明", civ)):
        cur = (row.get(key) or "").strip()
        if val and val != "-" and cur in ("", "-"):
            row[key] = val
            changed = True
    if dynasty and (row.get("dynasty_zy") or "").strip() in ("", "-"):
        row["dynasty_zy"] = dynasty
        changed = True

    di = di if dynasty_index is not None else build_dynasty_index_from_json()
    dinfo = di.get(dynasty) or {}
    civ_id = (row.get("文明ID") or resolve_civilization_id(civ)).strip()
    dynasty_id = (row.get("朝代ID") or dinfo.get("dynasty_id") or "").strip()
    if civ_id and row.get("文明ID") != civ_id:
        row["文明ID"] = civ_id
        changed = True
    if dynasty_id and row.get("朝代ID") != dynasty_id:
        row["朝代ID"] = dynasty_id
        changed = True
    regime = (row.get("政权") or "").strip()
    if regime and civ_id and dynasty_id and dynasty:
        rid = make_regime_id(civ_id, dynasty_id, dynasty, regime)
        if row.get("政权ID") != rid:
            row["政权ID"] = rid
            changed = True
    return changed


def repair_regime_json_coord_chains(
    rows: List[dict],
    *,
    dynasty_index: Optional[Dict[str, dict]] = None,
) -> Tuple[int, List[str]]:
    patched = 0
    logs: List[str] = []
    for row in rows:
        regime = (row.get("政权") or "").strip()
        if not regime:
            continue
        if _regime_coord_chain_complete(row):
            continue
        if ensure_regime_coord_chain(row, dynasty_index=dynasty_index):
            patched += 1
            logs.append(
                f"修补政权「{regime}」→ {row.get('文明')}/{row.get('朝代')}"
            )
    return patched, logs


def canonical_regime(
    regime: str,
    dynasty: str = "",
    regime_index: Optional[Dict[str, dict]] = None,
) -> str:
    """
    将标注/帝王表中的政权名规范为政权.json 标准名。

    规则（SSOT = 政权.json，按 朝代+政权 精确匹配）：
    - (朝代, 政权) 已在表中 → 用该行政权名
    - 「春秋·鲁」类：若「鲁」在表中且朝代与二级朝代/前缀一致 → 用「鲁」
    - 「战国·秦」等：若同朝代有短名「秦」→ 用短名
    """
    from coordinate_index import build_regime_pair_index, lookup_regime_row

    regime = (regime or "").strip()
    if not regime:
        return regime

    ri = regime_index if regime_index is not None else build_regime_index()
    pi = build_regime_pair_index()
    dyn = (dynasty or "").strip()

    if dyn:
        hit = lookup_regime_row(dyn, regime, regime_index=ri, pair_index=pi)
        if hit:
            return hit["regime"]

    if regime in ri:
        info = ri[regime]
        reg_dyn = (info.get("dynasty") or "").strip()
        if not dyn or not reg_dyn or reg_dyn == dyn:
            return regime

    if "·" not in regime:
        return regime

    prefix, base = (p.strip() for p in regime.split("·", 1))
    if not base:
        return regime

    if dyn:
        hit = lookup_regime_row(dyn, base, regime_index=ri, pair_index=pi)
        if hit:
            return hit["regime"]

    if base not in ri:
        return regime

    info = ri[base]
    reg_dyn = (info.get("dynasty") or "").strip()

    if not dyn or reg_dyn == dyn or prefix == reg_dyn or prefix == dyn:
        return base
    if not reg_dyn:
        return base
    return regime


def _norm_key(key: str) -> str:
    return key.lstrip("\ufeff").strip()


def _load_emperor_rows(path: Path) -> List[dict]:
    with open(path, encoding="utf-8-sig") as f:
        raw_rows = json.load(f)
    return [{_norm_key(k): v for k, v in raw.items()} for raw in raw_rows]


def normalize_emperor_json_regimes(
    *,
    emperor_path: Optional[Path] = None,
    dry_run: bool = False,
) -> Tuple[int, List[str]]:
    """将帝王.json 中可规范化的「朝代·国」政权名改为政权.json 标准名。"""
    ep = emperor_path or EMPEROR_JSON
    rows = _load_emperor_rows(ep)
    ri = build_regime_index()
    patched = 0
    logs: List[str] = []

    for row in rows:
        old = (row.get("政权") or "").strip()
        if not old:
            continue
        dynasty = (row.get("朝代") or "").strip()
        new = canonical_regime(old, dynasty, ri)
        if new != old:
            row["政权"] = new
            patched += 1
            emperor = emperor_row_name(row) or "?"
            logs.append(f"帝王表「{emperor}」政权 {old} → {new}")

    if patched and not dry_run:
        with open(ep, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
            f.write("\n")

    return patched, logs


def canonicalize_entry_regime_coords(
    entry: dict,
    regime_index: Optional[Dict[str, dict]] = None,
) -> bool:
    """就地规范 skeleton 条目三级政权坐标。"""
    ri = regime_index if regime_index is not None else build_regime_index()
    dynasty = (entry.get("二级朝代坐标") or "").strip()
    old = (entry.get("三级政权坐标") or "").strip()
    if not old:
        return False
    new = canonical_regime(old, dynasty, ri)
    if new == old:
        return False
    entry["三级政权坐标"] = new
    auto = entry.get("_auto_filled")
    if isinstance(auto, dict) and auto.get("三级政权坐标") == old:
        auto["三级政权坐标"] = new
    return True


def auto_normalize_reference_coords(
    data: dict,
    *,
    emperor_path: Optional[Path] = None,
    regime_path: Optional[Path] = None,
    dry_run: bool = False,
) -> Tuple[int, int, int, List[str]]:
    """
    Step4 前自动对齐 reference：
    1) 修补帝王.json 政权别名
    2) 从 skeleton 补录缺失政权到政权.json
    3) 规范本卷 skeleton 三级政权坐标
    """
    logs: List[str] = []
    emp_n, emp_logs = normalize_emperor_json_regimes(
        emperor_path=emperor_path, dry_run=dry_run
    )
    logs.extend(emp_logs)

    reg_n, reg_logs = auto_supplement_regimes_from_skeleton(
        data, regime_path=regime_path, dry_run=dry_run
    )
    logs.extend(reg_logs)

    ri = build_regime_index()
    sk_n = 0
    for entry in data.get("entries", []):
        if canonicalize_entry_regime_coords(entry, ri):
            sk_n += 1
            logs.append(
                f"skeleton [{entry.get('史略ID')}] 政权坐标已规范"
            )

    return emp_n, reg_n, sk_n, logs


def _fmt_regime_year(value: Optional[int]) -> str:
    if value is None:
        return "-"
    return str(value)


def _load_regime_rows(path: Path) -> List[dict]:
    with open(path, encoding="utf-8-sig") as f:
        raw_rows = json.load(f)
    return [{_norm_key(k): v for k, v in raw.items()} for raw in raw_rows]


def collect_regime_hints_from_skeleton(data: dict) -> Dict[str, dict]:
    """从 skeleton 聚合政权名 → 朝代/文明/年份线索。"""
    hints: Dict[str, dict] = {}
    ri = build_regime_index()

    for entry in data.get("entries", []):
        auto = entry.get("_auto_filled") or {}
        dynasty = (entry.get("二级朝代坐标") or auto.get("二级朝代坐标") or "").strip()
        regime = canonical_regime(
            (entry.get("三级政权坐标") or auto.get("三级政权坐标") or "").strip(),
            dynasty,
            ri,
        )
        if not regime:
            continue
        bucket = hints.setdefault(
            regime,
            {
                "dynasties": Counter(),
                "civilizations": Counter(),
                "starts": [],
                "ends": [],
            },
        )
        if dynasty:
            bucket["dynasties"][dynasty] += 1
        civ = (entry.get("一级文明坐标") or auto.get("一级文明坐标") or "").strip()
        if civ:
            bucket["civilizations"][civ] += 1
        for key in ("史略开始年", "史略结束年"):
            val = entry.get(key)
            if isinstance(val, int):
                if key.endswith("开始年"):
                    bucket["starts"].append(val)
                else:
                    bucket["ends"].append(val)

    return hints


def _extend_hints_from_emperors(hints: Dict[str, dict]) -> None:
    """仅用本卷已引用政权，从帝王表补充年代线索（不扫全表）。"""
    if not hints:
        return
    targets = set(hints.keys())
    for info in load_emperor_records():
        regime = (info.get("regime") or "").strip()
        if regime not in targets:
            continue
        bucket = hints[regime]
        dynasty = (info.get("dynasty") or "").strip()
        if dynasty:
            bucket["dynasties"][dynasty] += 1
        civ = (info.get("civilization") or "").strip()
        if civ:
            bucket["civilizations"][civ] += 1
        if info.get("start_year") is not None:
            bucket["starts"].append(info["start_year"])
        if info.get("end_year") is not None:
            bucket["ends"].append(info["end_year"])


def draft_regime_row(regime: str, bucket: dict) -> dict:
    dynasty = (
        bucket["dynasties"].most_common(1)[0][0]
        if bucket["dynasties"]
        else "春秋"
    )
    civ = (
        bucket["civilizations"].most_common(1)[0][0]
        if bucket["civilizations"]
        else infer_civilization_for_dynasty(dynasty)
    )
    civ_id = resolve_civilization_id(civ)
    di = build_dynasty_index_from_json()
    dinfo = di.get(dynasty) or {}
    dynasty_id = dinfo.get("dynasty_id") or ""
    start = min(bucket["starts"]) if bucket["starts"] else None
    end = max(bucket["ends"]) if bucket["ends"] else None
    return {
        "政权": regime,
        "政权ID": make_regime_id(civ_id, dynasty_id, dynasty, regime),
        "朝代": dynasty,
        "朝代ID": dynasty_id,
        "dynasty_zy": dynasty,
        "文明": civ,
        "文明ID": civ_id,
        "开始时间": _fmt_regime_year(start),
        "结束时间": _fmt_regime_year(end),
    }


def auto_supplement_regimes_from_skeleton(
    data: dict,
    *,
    regime_path: Optional[Path] = None,
    dry_run: bool = False,
) -> Tuple[int, List[str]]:
    """标注/skeleton 引用的政权若不在政权.json → 自动补录。"""
    rp = regime_path or REGIME_JSON
    rows = _load_regime_rows(rp)
    existing = {(r.get("政权") or "").strip() for r in rows}

    hints = collect_regime_hints_from_skeleton(data)
    _extend_hints_from_emperors(hints)

    added = 0
    logs: List[str] = []
    for regime in sorted(hints):
        if regime in existing:
            continue
        draft = draft_regime_row(regime, hints[regime])
        ensure_regime_coord_chain(draft)
        if not _regime_coord_chain_complete(draft):
            logs.append(f"跳过政权「{regime}」：坐标链不完整")
            continue
        rows.append(draft)
        existing.add(regime)
        added += 1
        logs.append(
            f"自动补录政权「{regime}」({draft['文明']}/{draft['朝代']} "
            f"{draft['开始时间']}～{draft['结束时间']})"
        )

    chain_n, chain_logs = repair_regime_json_coord_chains(rows)
    if chain_n:
        logs.extend(chain_logs[:8])

    if (added or chain_n) and not dry_run:
        with open(rp, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
            f.write("\n")

    return added + chain_n, logs
