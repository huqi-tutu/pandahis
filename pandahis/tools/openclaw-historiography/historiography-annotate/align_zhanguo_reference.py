#!/usr/bin/env python3
"""对齐战国诸侯：补政权.json 国别行，修正帝王.json 政权/ID，并校验两表一致。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

SKILL = Path(__file__).resolve().parent
if str(SKILL) not in sys.path:
    sys.path.insert(0, str(SKILL))

from coordinate_index import (  # noqa: E402
    EMPEROR_JSON,
    REGIME_JSON,
    build_regime_pair_index,
    emperor_row_name,
    lookup_regime_row,
    make_emperor_id,
    make_regime_id,
)
from regime_resolve import ensure_regime_coord_chain  # noqa: E402

# 战国国别政权补录（(朝代, 政权) 唯一）
ZHANGUO_REGIME_ROWS: List[dict] = [
    {"政权": "齐", "开始时间": "-403", "结束时间": "-221"},
    {"政权": "楚", "开始时间": "-403", "结束时间": "-223"},
    {"政权": "燕", "开始时间": "-403", "结束时间": "-222"},
    {"政权": "秦", "开始时间": "-403", "结束时间": "-207"},
    {"政权": "鲁", "开始时间": "-403", "结束时间": "-256"},
    {"政权": "蔡", "开始时间": "-403", "结束时间": "-447"},
    {"政权": "宋", "开始时间": "-403", "结束时间": "-286"},
    {"政权": "晋", "开始时间": "-403", "结束时间": "-376"},
    {"政权": "越", "开始时间": "-403", "结束时间": "-306"},
    # 卫/魏拼音同为 WEI，战国·卫 用独立 ID
    {"政权": "卫", "开始时间": "-403", "结束时间": "-209", "政权ID": "ZQ_HX_ZHANGUO_WEIGUO"},
]

NATION_PREFIX_RULES: List[Tuple[str, str]] = [
    ("田齐", "齐"),
    ("齐", "齐"),
    ("楚", "楚"),
    ("燕", "燕"),
    ("赵", "赵"),
    ("韩", "韩"),
    ("魏", "魏"),
    ("秦", "秦"),
    ("周", "东周"),
    ("鲁", "鲁"),
    ("蔡", "蔡"),
    ("卫", "卫"),
    ("宋", "宋"),
    ("晋", "晋"),
    ("越", "越"),
]


def _norm_key(key: str) -> str:
    return key.lstrip("\ufeff").strip()


def _load_rows(path: Path) -> List[dict]:
    with open(path, encoding="utf-8-sig") as f:
        return [{_norm_key(k): v for k, v in raw.items()} for raw in json.load(f)]


def _save_rows(path: Path, rows: List[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
        f.write("\n")


def infer_zhanguo_nation(emperor_name: str) -> Optional[str]:
    name = (emperor_name or "").strip()
    if name in ("王无彊", "越王无彊"):
        return "越"
    for prefix, nation in sorted(NATION_PREFIX_RULES, key=lambda x: -len(x[0])):
        if name.startswith(prefix):
            return nation
    return None


def supplement_zhanguo_regimes(
    regime_path: Path,
    *,
    dry_run: bool = False,
) -> Tuple[int, List[str]]:
    rows = _load_rows(regime_path)
    pair = {(r.get("朝代", "").strip(), r.get("政权", "").strip()) for r in rows}
    logs: List[str] = []
    added = 0

    for draft in ZHANGUO_REGIME_ROWS:
        regime = draft["政权"]
        dynasty = "战国"
        key = (dynasty, regime)
        if key in pair:
            continue
        row = {
            "政权": regime,
            "朝代": dynasty,
            "朝代ID": "CD_HX_ZHANGUO",
            "dynasty_zy": dynasty,
            "文明": "华夏",
            "文明ID": "HX",
            "开始时间": draft.get("开始时间", "-403"),
            "结束时间": draft.get("结束时间", "-221"),
        }
        if draft.get("政权ID"):
            row["政权ID"] = draft["政权ID"]
        ensure_regime_coord_chain(row)
        if draft.get("政权ID"):
            row["政权ID"] = draft["政权ID"]
        rows.append(row)
        pair.add(key)
        added += 1
        logs.append(f"补录政权 ({dynasty}, {regime}) → {row.get('政权ID')}")

    if added and not dry_run:
        _save_rows(regime_path, rows)
    return added, logs


def realign_zhanguo_emperors(
    emperor_path: Path,
    regime_path: Path,
    *,
    dry_run: bool = False,
) -> Tuple[int, List[str]]:
    emp_rows = _load_rows(emperor_path)
    reg_rows = _load_rows(regime_path)
    pair_index = build_regime_pair_index(
        records=[
            {
                "regime": (r.get("政权") or "").strip(),
                "regime_id": (r.get("政权ID") or "").strip(),
                "dynasty": (r.get("朝代") or "").strip(),
                "dynasty_id": (r.get("朝代ID") or "").strip(),
                "civilization": (r.get("文明") or "").strip(),
                "civilization_id": (r.get("文明ID") or "").strip(),
            }
            for r in reg_rows
        ]
    )
    logs: List[str] = []
    patched = 0

    for row in emp_rows:
        dynasty = (row.get("朝代") or "").strip()
        regime = (row.get("政权") or "").strip()
        if dynasty != "战国" or regime != "战国":
            continue
        emperor = emperor_row_name(row)
        nation = infer_zhanguo_nation(emperor)
        if not nation:
            logs.append(f"跳过（无法推断国别）: {emperor}")
            continue

        old_regime = regime
        old_rid = (row.get("政权ID") or "").strip()
        old_eid = (row.get("帝王ID") or "").strip()

        row["政权"] = nation
        reg_row = lookup_regime_row("战国", nation, pair_index=pair_index)
        if not reg_row:
            logs.append(f"跳过（政权表无行）: {emperor} → 战国/{nation}")
            continue
        row["政权ID"] = reg_row.get("regime_id") or row.get("政权ID")

        civ_id = (row.get("文明ID") or "HX").strip()
        dynasty_id = (row.get("朝代ID") or "CD_HX_ZHANGUO").strip()
        regime_id = (row.get("政权ID") or "").strip()
        if emperor and civ_id and dynasty_id and regime_id:
            row["帝王ID"] = make_emperor_id(civ_id, dynasty_id, regime_id, emperor)

        if (
            row.get("政权") != old_regime
            or row.get("政权ID") != old_rid
            or row.get("帝王ID") != old_eid
        ):
            patched += 1
            logs.append(
                f"{emperor}: 政权 {old_regime}→{row['政权']}, "
                f"政权ID {old_rid}→{row.get('政权ID')}, "
                f"帝王ID {old_eid}→{row.get('帝王ID')}"
            )

    if patched and not dry_run:
        _save_rows(emperor_path, emp_rows)
    return patched, logs


def sync_emperor_ids_from_regime_table(
    emperor_path: Path,
    regime_path: Path,
    *,
    dry_run: bool = False,
) -> Tuple[int, List[str]]:
    """凡 (朝代,政权) 能在政权表命中，则同步 政权ID / 帝王ID。"""
    emp_rows = _load_rows(emperor_path)
    reg_rows = _load_rows(regime_path)
    records = [
        {
            "regime": (r.get("政权") or "").strip(),
            "regime_id": (r.get("政权ID") or "").strip(),
            "dynasty": (r.get("朝代") or "").strip(),
            "dynasty_id": (r.get("朝代ID") or "").strip(),
            "civilization": (r.get("文明") or "").strip(),
            "civilization_id": (r.get("文明ID") or "").strip(),
        }
        for r in reg_rows
    ]
    pair_index = build_regime_pair_index(records=records)
    logs: List[str] = []
    patched = 0

    for row in emp_rows:
        emperor = emperor_row_name(row)
        dynasty = (row.get("朝代") or "").strip()
        regime = (row.get("政权") or "").strip()
        reg_row = lookup_regime_row(dynasty, regime, pair_index=pair_index)
        if not reg_row:
            continue
        old_rid = (row.get("政权ID") or "").strip()
        old_eid = (row.get("帝王ID") or "").strip()
        new_rid = (reg_row.get("regime_id") or "").strip()
        if new_rid:
            row["政权ID"] = new_rid
        civ_id = (row.get("文明ID") or reg_row.get("civilization_id") or "HX").strip()
        dynasty_id = (row.get("朝代ID") or reg_row.get("dynasty_id") or "").strip()
        regime_id = (row.get("政权ID") or "").strip()
        if emperor and civ_id and dynasty_id and regime_id:
            row["帝王ID"] = make_emperor_id(civ_id, dynasty_id, regime_id, emperor)
        if row.get("政权ID") != old_rid or row.get("帝王ID") != old_eid:
            patched += 1
            logs.append(
                f"{emperor} ({dynasty}/{regime}): "
                f"政权ID {old_rid}→{row.get('政权ID')}, "
                f"帝王ID {old_eid}→{row.get('帝王ID')}"
            )

    if patched and not dry_run:
        _save_rows(emperor_path, emp_rows)
    return patched, logs


def verify_reference_alignment(
    emperor_path: Path,
    regime_path: Path,
) -> List[str]:
    emp_rows = _load_rows(emperor_path)
    reg_rows = _load_rows(regime_path)
    pair_index = build_regime_pair_index(
        records=[
            {
                "regime": (r.get("政权") or "").strip(),
                "regime_id": (r.get("政权ID") or "").strip(),
                "dynasty": (r.get("朝代") or "").strip(),
                "dynasty_id": (r.get("朝代ID") or "").strip(),
                "civilization": (r.get("文明") or "").strip(),
                "civilization_id": (r.get("文明ID") or "").strip(),
            }
            for r in reg_rows
        ]
    )
    issues: List[str] = []

    for row in emp_rows:
        emperor = emperor_row_name(row)
        dynasty = (row.get("朝代") or "").strip()
        regime = (row.get("政权") or "").strip()
        if not dynasty or not regime:
            issues.append(f"帝王「{emperor}」缺朝代/政权")
            continue
        reg_row = lookup_regime_row(dynasty, regime, pair_index=pair_index)
        if not reg_row:
            issues.append(
                f"帝王「{emperor}」({dynasty}/{regime}) 在政权.json 无对应行"
            )
            continue
        rid = (row.get("政权ID") or "").strip()
        expect = (reg_row.get("regime_id") or "").strip()
        if rid and expect and rid != expect:
            issues.append(
                f"帝王「{emperor}」政权ID {rid} ≠ 政权表 {expect}"
            )
        civ_id = (row.get("文明ID") or "HX").strip()
        dynasty_id = (row.get("朝代ID") or "").strip()
        regime_id = expect or rid
        if emperor and civ_id and dynasty_id and regime_id:
            expect_eid = make_emperor_id(civ_id, dynasty_id, regime_id, emperor)
            eid = (row.get("帝王ID") or "").strip()
            if eid and eid != expect_eid:
                issues.append(
                    f"帝王「{emperor}」帝王ID {eid} ≠ 期望 {expect_eid}"
                )
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="对齐战国诸侯 reference 数据")
    parser.add_argument("--emperor", type=Path, default=EMPEROR_JSON)
    parser.add_argument("--regime", type=Path, default=REGIME_JSON)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    if args.verify_only:
        issues = verify_reference_alignment(args.emperor, args.regime)
        if issues:
            print(f"❌ 仍有 {len(issues)} 条不一致:")
            for msg in issues[:40]:
                print(f"  - {msg}")
            if len(issues) > 40:
                print(f"  ... 另有 {len(issues) - 40} 条")
            return 1
        print("✅ 帝王.json 与 政权.json 已对齐")
        return 0

    reg_n, reg_logs = supplement_zhanguo_regimes(args.regime, dry_run=args.dry_run)
    emp_n, emp_logs = realign_zhanguo_emperors(
        args.emperor, args.regime, dry_run=args.dry_run
    )
    sync_n, sync_logs = sync_emperor_ids_from_regime_table(
        args.emperor, args.regime, dry_run=args.dry_run
    )
    print(f"政权.json 补录: {reg_n} 行")
    for ln in reg_logs:
        print(f"  {ln}")
    print(f"帝王.json 战国政权名修正: {emp_n} 条")
    for ln in emp_logs:
        print(f"  {ln}")
    print(f"帝王.json ID 同步: {sync_n} 条")
    for ln in sync_logs[:20]:
        print(f"  {ln}")
    if len(sync_logs) > 20:
        print(f"  ... 另有 {len(sync_logs) - 20} 条")

    if args.dry_run:
        print("\n(dry-run，未写盘)")
        return 0

    issues = verify_reference_alignment(args.emperor, args.regime)
    zhanguo_issues = [
        m for m in issues
        if "战国" in m or any(k in m for k in ("齐威王", "楚怀王", "燕昭王", "秦惠王"))
    ]
    if zhanguo_issues:
        print(f"\n⚠️ 战国相关仍有 {len(zhanguo_issues)} 条待查（前 10 条）:")
        for msg in zhanguo_issues[:10]:
            print(f"  - {msg}")
        return 1
    if issues:
        print(f"\nℹ️ 全库另有 {len(issues)} 条非战国对齐项（五代十国等），战国部分已通过")
    print("\n✅ 帝王.json 与 政权.json 战国诸侯已对齐")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
