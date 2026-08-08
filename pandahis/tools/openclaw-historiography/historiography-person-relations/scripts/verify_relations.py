#!/usr/bin/env python3
"""Validate person-relation JSON files under data/07人物关系/."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

VALID_CATEGORIES = {"家庭", "同僚", "敌对", "师徒", "好友"}
LEGACY_CATEGORIES = {"君臣", "外敌", "师从"}
VALID_LEVELS = {"一级", "二级", "三级", "四级"}
LEVEL_NUM = {"一级": 1, "二级": 2, "三级": 3, "四级": 4}
PARENT_FIELDS = [
    ("二级", "所属一级关系"),
    ("三级", "所属一级关系"),
    ("三级", "所属二级关系"),
    ("四级", "所属一级关系"),
    ("四级", "所属二级关系"),
    ("四级", "所属三级关系"),
]
REQUIRED_FIELDS = [
    "关联史略名称",
    "关系ID",
    "关系类别",
    "关系层级",
    "关系节点标题",
    "关系简述",
]
def load_records(path: Path) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("root must be a JSON array")
    return raw


def verify_file(path: Path, *, strict: bool) -> list[str]:
    errors: list[str] = []
    warns: list[str] = []

    try:
        records = load_records(path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return [f"CRITICAL {path}: {exc}"]

    if not records:
        warns.append(f"WARN {path}: empty array")
        return errors + warns

    subjects = {str(r.get("关联史略名称", "")).strip() for r in records}
    subjects.discard("")
    if len(subjects) != 1:
        errors.append(f"CRITICAL {path}: 关联史略名称 must be single value, got {subjects!r}")

    expected_name = next(iter(subjects), "")
    if expected_name and path.name != f"{expected_name}关系表.json":
        warns.append(
            f"WARN {path}: filename {path.name!r} != {expected_name}关系表.json"
        )

    seen_ids: set[str] = set()
    nodes_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}

    for idx, rec in enumerate(records):
        loc = f"{path}#[{idx}] id={rec.get('关系ID', '?')}"

        for field in REQUIRED_FIELDS:
            val = rec.get(field)
            if val is None or (isinstance(val, str) and not val.strip()):
                errors.append(f"CRITICAL {loc}: missing {field}")

        if "上级连接线标题" not in rec:
            errors.append(f"CRITICAL {loc}: missing 上级连接线标题")

        cat = str(rec.get("关系类别", "")).strip()
        if cat in LEGACY_CATEGORIES:
            if strict:
                errors.append(
                    f"CRITICAL {loc}: legacy 关系类别 {cat!r}; "
                    "use 家庭/同僚/敌对/师徒/好友"
                )
            else:
                warns.append(f"INFO {loc}: legacy 关系类别 {cat!r}")
        elif cat not in VALID_CATEGORIES:
            errors.append(f"CRITICAL {loc}: invalid 关系类别 {cat!r}")

        node_kind = str(rec.get("节点类型", "")).strip()
        if node_kind == "二级分类" and str(rec.get("关系层级", "")).strip() != "一级":
            errors.append(f"CRITICAL {loc}: 二级分类 hub must be 关系层级=一级")

        level = str(rec.get("关系层级", "")).strip()
        if level not in VALID_LEVELS:
            if level == "五级":
                errors.append(f"CRITICAL {loc}: 五级 forbidden; max 四级")
            else:
                errors.append(f"CRITICAL {loc}: invalid 关系层级 {level!r}")

        rid = str(rec.get("关系ID", "")).strip()
        if rid:
            if rid in seen_ids:
                errors.append(f"CRITICAL {loc}: duplicate 关系ID {rid!r}")
            seen_ids.add(rid)

        title = str(rec.get("关系节点标题", "")).strip()
        if title and level in VALID_LEVELS:
            cat_key = cat if cat in VALID_CATEGORIES else str(rec.get("关系类别", "")).strip()
            key = (title, level, cat_key)
            if key in nodes_by_key:
                msg = f"CRITICAL {loc}: duplicate node ({title!r}, {level}, {cat_key!r})" if strict else (
                    f"WARN {loc}: duplicate node ({title!r}, {level}, {cat_key!r})"
                )
                (errors if strict else warns).append(msg)
            nodes_by_key[key] = rec

        if rec.get("所属四级关系"):
            errors.append(f"CRITICAL {loc}: 所属四级关系 forbidden (max depth 四级)")

        if level in VALID_LEVELS:
            n = LEVEL_NUM[level]
            for lv, field in PARENT_FIELDS:
                if LEVEL_NUM[lv] != n:
                    continue
                val = rec.get(field)
                has = val is not None and str(val).strip() != ""
                if n == 1 and has:
                    errors.append(f"CRITICAL {loc}: 一级 must not have {field}")
                if n > 1 and not has:
                    errors.append(f"CRITICAL {loc}: {level} requires {field}")

        summary = str(rec.get("关系简述", "")).strip()
        if summary and len(summary) < 8:
            warns.append(f"WARN {loc}: 关系简述 very short")

        if not rec.get("record_id"):
            warns.append(f"WARN {loc}: missing record_id (optional for new files)")

    # chain consistency: each 所属*关系 must reference an existing node at the prior level
    for idx, rec in enumerate(records):
        loc = f"{path}#[{idx}]"
        level = str(rec.get("关系层级", "")).strip()
        if level not in VALID_LEVELS or LEVEL_NUM[level] < 2:
            continue
        parent_fields_ordered = [
            "所属一级关系",
            "所属二级关系",
            "所属三级关系",
        ]
        for i, pf in enumerate(parent_fields_ordered[: LEVEL_NUM[level] - 1]):
            ptitle = str(rec.get(pf, "")).strip()
            if not ptitle:
                continue
            parent_level = ["一级", "二级", "三级"][i]
            parent_found = any(
                str(r.get("关系节点标题", "")).strip() == ptitle
                and str(r.get("关系层级", "")).strip() == parent_level
                for r in records
            )
            if not parent_found:
                errors.append(
                    f"CRITICAL {loc}: parent {ptitle!r} at {parent_level} not found"
                )

    return errors + warns


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify person relation JSON files")
    parser.add_argument(
        "paths",
        nargs="+",
        help="JSON file or directory (data/07人物关系/)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Reject legacy 君臣/外敌/师从 and require new category names",
    )
    args = parser.parse_args()

    files: list[Path] = []
    for p in args.paths:
        path = Path(p)
        if path.is_dir():
            files.extend(sorted(path.glob("*关系表.json")))
        elif path.is_file():
            files.append(path)
        else:
            print(f"CRITICAL path not found: {path}", file=sys.stderr)
            return 1

    if not files:
        print("CRITICAL no *关系表.json files found", file=sys.stderr)
        return 1

    all_msgs: list[str] = []
    critical = 0
    for f in files:
        msgs = verify_file(f, strict=args.strict)
        all_msgs.extend(msgs)
        critical += sum(1 for m in msgs if m.startswith("CRITICAL"))

    for m in all_msgs:
        print(m)

    if critical:
        print(f"\nFAILED: {critical} critical issue(s) in {len(files)} file(s)", file=sys.stderr)
        return 1

    print(f"\nOK: {len(files)} file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
